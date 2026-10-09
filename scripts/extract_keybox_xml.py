#!/usr/bin/env python3
"""Extract AndroidAttestation keybox XML from MTK partition dumps."""
import argparse
import re
import sys
from pathlib import Path
from typing import Optional


import mmap

def extract_keybox_xml_from_path(path: Path) -> str:
    size = path.stat().st_size
    if size == 0:
        raise ValueError("File is empty")

    blocks = []
    with path.open("rb") as f:
        try:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            idx = 0
            while True:
                start_idx = mm.find(b"<AndroidAttestation>", idx)
                if start_idx == -1:
                    break
                end_idx = mm.find(b"</AndroidAttestation>", start_idx)
                if end_idx == -1:
                    break
                end_idx += len(b"</AndroidAttestation>")
                blocks.append(mm[start_idx:end_idx])
                idx = end_idx
            mm.close()
        except ValueError:
            pass

    if not blocks:
        raise ValueError("No <AndroidAttestation> block found")

    block = max(blocks, key=len)
    text = block.decode("utf-8", errors="replace").strip()
    if not text.startswith("<?xml"):
        text = '<?xml version="1.0" encoding="UTF-8"?>\n' + text
    return text + "\n"


def score_dump(path: Path) -> tuple[int, int, int]:
    size = path.stat().st_size
    if size == 0:
        return (0, 0, 0)
    att = 0
    pem = 0
    kb = 0
    with path.open("rb") as f:
        try:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            def count_pattern(mm, pattern):
                count = 0
                idx = 0
                while True:
                    idx = mm.find(pattern, idx)
                    if idx == -1:
                        break
                    count += 1
                    idx += len(pattern)
                return count

            att = count_pattern(mm, b"<AndroidAttestation>")
            pem = count_pattern(mm, b"BEGIN EC PRIVATE KEY") + count_pattern(mm, b"BEGIN RSA PRIVATE KEY")
            kb = count_pattern(mm, b"<Keybox")
            mm.close()
        except ValueError:
            pass
    return (att, pem, kb)


def find_best_dump(dumps_dir: Path) -> Optional[Path]:
    candidates = sorted(dumps_dir.glob("*.bin")) + sorted(dumps_dir.glob("*.img"))
    if not candidates:
        return None
    ranked = sorted(candidates, key=score_dump, reverse=True)
    best_score = score_dump(ranked[0])
    if best_score[0] > 0:
        return ranked[0]
    return ranked[0] if best_score[2] > 0 or best_score[1] > 0 else None


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    dumps = root / "dumps"
    parser = argparse.ArgumentParser(description="Extract keybox XML from MTK partition dumps")
    parser.add_argument(
        "-i", "--input",
        default="",
        help="partition dump (default: auto-detect best dumps/*.bin)",
    )
    parser.add_argument(
        "-o", "--output",
        default=str(dumps / "device_keybox.xml"),
        help="output XML path",
    )
    args = parser.parse_args()

    if args.input:
        src = Path(args.input)
    else:
        src = find_best_dump(dumps)
        if not src and (dumps / "persist.bin").exists():
            src = dumps / "persist.bin"
        if src:
            print(f"Using input: {src}")

    if not src or not src.exists():
        print("ERROR: No partition dump found. Run dump_partitions.ps1 first.")
        return 1

    try:
        xml = extract_keybox_xml_from_path(src)
    except ValueError as exc:
        print(f"ERROR: {exc} in {src.name}")
        print("Try another partition: python extract_keybox_xml.py -i dumps/protect1.bin")
        return 1

    dst = Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(xml, encoding="utf-8", newline="\n")
    print(f"Wrote {dst} ({dst.stat().st_size} bytes)")
    m = re.search(r'DeviceID="([^"]+)"', xml)
    print(f"DeviceID: {m.group(1) if m else 'unknown'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
