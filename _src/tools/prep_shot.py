#!/usr/bin/env python3
"""앱 캡처(PNG)를 사이트용 JPEG 로 줄인다. macOS sips 사용. 사용: prep_shot.py <src> <dst>"""
import pathlib
import subprocess
import sys


def prepare(src, dst, long_edge=1600, quality=78):
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    if not src.exists():
        raise RuntimeError(f"원본 없음: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["sips", "-Z", str(long_edge), "--setProperty", "format", "jpeg",
           "--setProperty", "formatOptions", str(quality), str(src), "--out", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists():
        raise RuntimeError(f"sips 실패: {r.stderr.strip() or r.stdout.strip()}")
    return dst


if __name__ == "__main__":
    prepare(sys.argv[1], sys.argv[2])
