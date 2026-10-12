#!/usr/bin/env python3
"""guides/<slug>.html 의 게시일·최종 수정일을 git 기록에서 뽑아 content/guide_dates.json 에 쓴다.
손으로 실행: python3 _src/tools/guide_dates.py   (chrome_legacy.py 는 git 을 부르지 않고 이 JSON 만 읽는다)

published = 파일을 처음 추가한 커밋의 날짜(가장 오래된 것)
modified  = 기계적 커밋을 뺀 가장 최근 커밋의 날짜(남는 게 없으면 published)
기계적 커밋 = ① 제목에 MECHANICAL_SUBJECTS 의 구절이 있거나 ② 제목에 "[mechanical]" 이 있거나
              ③ 한 커밋이 가이드 파일을 MECHANICAL_MIN_GUIDES(15)개 이상 건드린 일괄 수정.

새 가이드를 올리는 순서: ① 가이드 커밋 → ② 이 도구 실행 → ③ guide_dates.json 커밋
(그러면 chrome_legacy.py 가 박스·JSON-LD 에 날짜를 넣는다. 일괄 수정 커밋에는 제목에 [mechanical] 을 붙일 것).
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "_src" / "content" / "guide_dates.json"

# 글 내용과 무관한 일괄(기계적) 수정 커밋의 제목에 들어 있는 말.
# 앞으로 일괄 수정(링크 표시·도메인·메뉴 변경 등)을 하면 제목에 [mechanical] 을 붙이거나 여기에 구절을 추가할 것.
MECHANICAL_SUBJECTS = ("캠페인 표시", "커스텀 도메인", "새 메뉴·푸터 링크·글쓴이 박스", "무대음향 앱 1.2 반영", "[mechanical]")
MECHANICAL_MIN_GUIDES = 15


def is_mechanical(subject, n_guides):
    return n_guides >= MECHANICAL_MIN_GUIDES or any(m in subject for m in MECHANICAL_SUBJECTS)


def pick_dates(added, touched):
    """added, touched: 파일을 추가한/건드린 커밋의 (날짜 YYYY-MM-DD, 제목, 그 커밋이 건드린 가이드 파일 수) 목록.
    반환 (published, modified)."""
    if not added:
        raise ValueError("추가 커밋이 없음")
    published = min(d for d, _, _ in added)
    real = [d for d, s, n in touched if not is_mechanical(s, n)]
    modified = max(real) if real else published
    return published, max(modified, published)


def _git(args, root):
    return subprocess.run(["git"] + args, cwd=str(root), capture_output=True, text=True, check=True).stdout


def _log(args, root):
    rows = []
    for line in _git(["log", "--follow", "--format=%H\t%ad\t%s", "--date=short"] + args, root).splitlines():
        if not line.strip():
            continue
        sha, date, subject = line.split("\t", 2)
        names = _git(["diff-tree", "--no-commit-id", "--name-only", "-r", sha, "--", "guides"], root).split()
        rows.append((date, subject, sum(1 for n in names if n.endswith(".html"))))
    return rows


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
