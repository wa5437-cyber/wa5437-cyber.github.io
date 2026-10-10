#!/usr/bin/env python3
"""사이트 생성기. 사용: python3 _src/build.py [--check]"""
import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parent
ROOT = SRC.parent
sys.path.insert(0, str(SRC))

from sitegen import check  # noqa: E402


def main():
    if "--check" in sys.argv:
        errors = check.run(ROOT)
        for e in errors:
            print(" ✗", e)
        print("점검 통과" if not errors else f"점검 실패 {len(errors)}건")
        sys.exit(1 if errors else 0)
    print("생성 단계는 Task 3 이후에 추가됩니다.")


if __name__ == "__main__":
    main()
