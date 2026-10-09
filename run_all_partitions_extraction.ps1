# Run a RAM-efficient extraction attempting all possible partitions one by one.
param(
    [string]$OutputXml = "",
    [string]$DeviceLabel = ""
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$Scripts = Join-Path $Root "scripts"
$Dumps = Join-Path $Root "dumps"

New-Item -ItemType Directory -Force -Path $Dumps | Out-Null

if ($DeviceLabel -eq "") {
    $brand = (adb shell getprop ro.product.brand 2>&1).Trim()
    $device = (adb shell getprop ro.product.device 2>&1).Trim()
    if ($device) {
        $DeviceLabel = "${brand}_${device}" -replace '[^\w\-]', '_'
    } else {
        $DeviceLabel = "device"
    }
    Write-Host "Device label: $DeviceLabel"
}

if ($OutputXml -eq "") {
    $OutputXml = Join-Path $Dumps "${DeviceLabel}_Pvt_kb.xml"
}

Write-Host "=== Master MTK Keybox Extraction (RAM Efficient) ===" -ForegroundColor Cyan

# 1. Discover partitions
function Get-DevicePartitions {
    $paths = @(
        "/dev/block/by-name",
        "/dev/block/platform/bootdevice/by-name"
    )
    foreach ($base in $paths) {
        $listing = adb shell "su -c 'ls $base 2>/dev/null'" 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $listing.Trim()) {
            return @{
                Base = $base
                Names = ($listing -split "\s+" | Where-Object { $_ -and $_ -notmatch "^\s*$" } | Sort-Object -Unique)
            }
        }
    }
    return $null
}

$discovered = Get-DevicePartitions
if (-not $discovered) {
    Write-Host "ERROR: Could not list partitions on device. Are you rooted?"
    exit 1
}

$available = @($discovered.Names)
Write-Host "Found $($available.Count) partition(s) on device."

$SkipPartitions = @(
    "boot", "boot_a", "boot_b", "recovery", "recovery_a", "recovery_b",
    "system", "system_a", "system_b", "vendor", "vendor_a", "vendor_b",
    "userdata", "cache", "super", "vbmeta", "vbmeta_a", "vbmeta_b",
    "dtbo", "logo", "lk", "lk_a", "lk_b", "scp", "scp_a", "scp_b",
    "spmfw", "sspm", "mcupm", "gz", "gz_a", "gz_b", "preloader",
    "preloader_a", "preloader_b", "odm", "odm_a", "odm_b", "product"
)

$toDump = @($available | Where-Object { $_ -notin $SkipPartitions })
Write-Host "Candidate partitions: $($toDump.Count)"

$foundValid = $false

foreach ($name in $toDump) {
    Write-Host ""
    Write-Host "--- Processing partition: $name ---" -ForegroundColor Yellow

    $block = "$($discovered.Base)/$name"
    $remote = "/sdcard/_kb_dump_$name.bin"
    $local = Join-Path $Dumps "$name.bin"

    # Dump
    Write-Host "Dumping $name..."
    adb shell "su -c 'dd if=$block of=$remote bs=4096'" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        adb shell "su -c 'dd if=/dev/block/platform/bootdevice/by-name/$name of=$remote bs=4096'" 2>&1 | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        adb shell "su -c 'dd if=/dev/block/by-name/$name of=$remote bs=4096'" 2>&1 | Out-Null
    }

    adb pull $remote $local 2>&1 | Out-Null
    adb shell "rm -f $remote" 2>&1 | Out-Null

    if (-not (Test-Path $local)) {
        Write-Host "Failed to dump $name, skipping."
        continue
    }

    Write-Host "Analyzing $name..."
    python (Join-Path $Scripts "scan_keybox_markers.py")
    python (Join-Path $Scripts "analyze_keybox.py")

    # Attempt XML Extraction
    python (Join-Path $Scripts "extract_keybox_xml.py") -i $local -o $OutputXml
    if ($LASTEXITCODE -eq 0 -and (Test-Path $OutputXml)) {
        Write-Host "Successfully extracted XML from $name!" -ForegroundColor Green

        # Check validity
        $ValidityJson = Join-Path $Dumps "${DeviceLabel}_validity.json"
        python (Join-Path $Scripts "check_keybox_validity.py") -i $OutputXml -o $ValidityJson
        $validExit = $LASTEXITCODE
        if ($validExit -eq 0) {
            Write-Host "Status: VALID (all certificates in date)" -ForegroundColor Green
            $foundValid = $true
        } else {
            Write-Host "Status: INVALID or check failed" -ForegroundColor Yellow
        }
    }

    # Cleanup local dump to save disk space and RAM on subsequent runs
    Write-Host "Cleaning up $local..."
    Remove-Item -Path $local -Force

    if ($foundValid) {
        Write-Host "Valid Keybox found in partition $name! Stopping search." -ForegroundColor Cyan
        break
    }
}

if (-not $foundValid) {
    Write-Host ""
    Write-Host "Finished processing all partitions. No valid keybox found." -ForegroundColor Red
} else {
    Write-Host ""
    Write-Host "Extraction Complete."
    Write-Host "Keybox: $OutputXml"
}
