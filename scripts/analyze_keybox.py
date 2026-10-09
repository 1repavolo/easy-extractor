#!/usr/bin/env python3
"""Report keybox format across all partition dumps."""
import re
import sys
from pathlib import Path


import mmap

def analyze(path: Path) -> dict:
    result = {
        "path": path,
        "att": 0,
        "kb": 0,
        "pem_priv": 0,
        "pem_cert": 0,
        "wv": 0,
        "device_id": None,
        "format": "no keybox markers",
    }
    if not path.exists():
        return result

    size = path.stat().st_size
    if size == 0:
        return result

    def count_pattern(mm, pattern, ignore_case=False):
        count = 0
        idx = 0
        while True:
            if ignore_case:
                # mmap doesn't have an ignore case find, so we do it carefully or use regex on chunks
                # But for 'widevine', we can just search for 'widevine' and 'Widevine'
                idx1 = mm.find(pattern.lower(), idx)
                idx2 = mm.find(pattern.capitalize(), idx)
                if idx1 == -1 and idx2 == -1:
                    break
                elif idx1 == -1:
                    idx = idx2 + len(pattern)
                elif idx2 == -1:
                    idx = idx1 + len(pattern)
                else:
                    idx = min(idx1, idx2) + len(pattern)
                count += 1
            else:
                idx = mm.find(pattern, idx)
                if idx == -1:
                    break
                count += 1
                idx += len(pattern)
        return count

    with path.open("rb") as f:
        try:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            result["att"] = count_pattern(mm, b"<AndroidAttestation>")
            result["kb"] = count_pattern(mm, b"<Keybox")
            result["pem_priv"] = count_pattern(mm, b"BEGIN EC PRIVATE KEY") + count_pattern(mm, b"BEGIN RSA PRIVATE KEY")
            result["pem_cert"] = count_pattern(mm, b"BEGIN CERTIFICATE")
            result["wv"] = count_pattern(mm, b"widevine", ignore_case=True)

            # Find device_id using regex over a chunk if possible, or just scan
            idx = mm.find(b'DeviceID="')
            if idx != -1:
                end = mm.find(b'"', idx + 10)
                if end != -1:
                    result["device_id"] = mm[idx+10:end].decode("utf-8", errors="ignore")
            mm.close()
        except ValueError:
            pass

    if result["att"] > 0 and result["pem_priv"] > 0:
        result["format"] = "plaintext XML + PEM in partition"
    elif result["kb"] > 0 or result["wv"] > 0:
        result["format"] = "keybox-related strings present"
    return result


def print_report(path: Path) -> dict:
    info = analyze(path)
    if not path.exists():
        print(f"  (missing {path.name})")
        return info
    size = path.stat().st_size
    print(f"\n=== {path.name} ({size} bytes) ===")
    print(f"  AndroidAttestation blocks: {info['att']}")
    print(f"  Keybox tags: {info['kb']}")
    print(f"  PEM private keys: {info['pem_priv']}")
    print(f"  PEM certificates: {info['pem_cert']}")
    print(f"  widevine mentions: {info['wv']}")
    if info["device_id"]:
        print(f"  DeviceID: {info['device_id']}")
    print(f"  Format: {info['format']}")
    return info


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    dumps = root / "dumps"
    dump_files = sorted(dumps.glob("*.bin")) + sorted(dumps.glob("*.img"))
    snippet_files = sorted(dumps.glob("*_keybox_snippet.txt"))
    xml_files = sorted(dumps.glob("*.xml"))

    if not dump_files and not snippet_files and not xml_files:
        print("No dumps yet. Run dump_partitions.ps1 first.")
        return 1

    reports = []
    for f in dump_files:
        reports.append(print_report(f))

    for f in snippet_files:
        print_report(f)

    for xf in xml_files:
        print_report(xf)

    best = max(reports, key=lambda r: (r["att"], r["pem_priv"], r["kb"]), default=None)
    if best and best["att"] > 0:
        print(f"\nBest extraction candidate: {best['path'].name}")
    elif reports:
        print("\nNo AndroidAttestation block found yet. Check protect1/protect2 snippets or vendor partitions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
