#!/usr/bin/env python3
"""guides/<slug>.html 의 게시일·최종 수정일을 git 기록에서 뽑아 content/guide_dates.json 에 쓴다.
손으로 실행: python3 _src/tools/guide_dates.py   (chrome_legacy.py 는 git 을 부르지 않고 이 JSON 만 읽는다)

published = 파일을 처음 추가한 커밋의 날짜(가장 오래된 것)
modified  = 기계적 커밋을 뺀 가장 최근 커밋의 날짜(남는 게 없으면 published)
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "_src" / "content" / "guide_dates.json"

# 글 내용과 무관한 일괄(기계적) 수정 커밋의 제목에 들어 있는 말.
# 앞으로 일괄 수정(링크 표시·도메인·메뉴 변경 등)을 하면 여기에 그 제목의 한 구절을 반드시 추가할 것.
MECHANICAL_SUBJECTS = ("캠페인 표시", "커스텀 도메인", "새 메뉴·푸터 링크·글쓴이 박스")


def pick_dates(added, touched):
    """added: 파일을 추가한 커밋 (날짜, 제목) 목록, touched: 파일을 건드린 모든 커밋 (날짜, 제목) 목록.
    날짜는 YYYY-MM-DD. 반환 (published, modified)."""
    if not added:
        raise ValueError("추가 커밋이 없음")
    published = min(d for d, _ in added)
    real = [d for d, s in touched if not any(m in s for m in MECHANICAL_SUBJECTS)]
    modified = max(real) if real else published
    return published, max(modified, published)


def _log(args, root):
    out = subprocess.run(["git", "log", "--follow", "--format=%ad\t%s", "--date=short"] + args,
                         cwd=str(root), capture_output=True, text=True, check=True).stdout
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line.strip()]


def collect(root=ROOT):
    data = {}
    for path in sorted((root / "guides").glob("*.html")):
        if path.name == "index.html":
            continue
        rel = "guides/" + path.name
        added = _log(["--diff-filter=A", "--", rel], root)
        touched = _log(["--", rel], root)
        pub, mod = pick_dates(added, touched)
        data[path.stem] = {"published": pub, "modified": mod}
    return data


def main():
    data = collect()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("가이드 %d개 날짜 기록 → %s" % (len(data), OUT))


if __name__ == "__main__":
    sys.exit(main())
