"""Inspect ELF PT_LOAD alignment inside APK/AAB without extracting untrusted paths.

ZIP alignment is independently checked by Android zipalign. This verifies
64-bit native ELF segments; 32-bit entries are inventoried, not 16 KiB-gated.
"""
import argparse
import json
import struct
import zipfile
from pathlib import Path

PAGE = 16384


def load_segments(data):
    if len(data) < 16 or data[:4] != b"\x7fELF" or data[5] != 1:
        raise ValueError("not a little-endian ELF")
    bits = data[4]
    if bits == 2:
        header = struct.Struct("<16sHHIQQQIHHHHHH")
        program = struct.Struct("<IIQQQQQQ")
    elif bits == 1:
        header = struct.Struct("<16sHHIIIIIHHHHHH")
        program = struct.Struct("<IIIIIIII")
    else:
        raise ValueError("unknown ELF class")
    fields = header.unpack_from(data)
    phoff, entsize, count = fields[5], fields[9], fields[10]
    if not count or entsize < program.size or phoff + entsize * count > len(data):
        raise ValueError("invalid program header table")
    loads = []
    for i in range(count):
        p = program.unpack_from(data, phoff + i * entsize)
        if p[0] != 1:
            continue
        offset, vaddr, align = (p[2], p[3], p[7]) if bits == 2 else (p[1], p[2], p[7])
        loads.append({"offset": offset, "vaddr": vaddr, "alignment": align,
                      "aligned": align >= PAGE and align & (align - 1) == 0
                      and offset % PAGE == vaddr % PAGE})
    if not loads:
        raise ValueError("no PT_LOAD segments")
    return bits * 32, loads


def inspect(path):
    libraries = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.filename.endswith(".so") or "/lib/" not in "/" + info.filename:
                continue
            row = {"library": info.filename}
            try:
                bits, segments = load_segments(archive.read(info))
                row.update(bits=bits, segments=segments,
                           passed=bits == 32 or all(s["aligned"] for s in segments))
                if "/arm64-v8a/" in info.filename or "/x86_64/" in info.filename:
                    row["passed"] = row["passed"] and bits == 64
            except (ValueError, struct.error, OSError, zipfile.BadZipFile) as exc:
                row.update(passed=False, error=str(exc))
            libraries.append(row)
    return {"archive": str(path), "libraries": libraries,
            "passed": all(row["passed"] for row in libraries)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.archive)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    for row in result["libraries"]:
        print(("PASS " if row["passed"] else "FAIL ") + row["library"])
    print("64-bit ELF segment alignment:", "PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
