#!/usr/bin/env python3
"""sitemap.xml 의 각 <url> 에 <lastmod>(YYYY-MM-DD)를 채운다. 손으로 실행: python3 _src/tools/sitemap_lastmod.py

lastmod = 그 페이지 파일을 건드린 커밋 중 '기계적 커밋'을 뺀 가장 최근 날짜(없으면 파일을 처음 추가한 날).
기계적 커밋 판정은 guide_dates.py 와 같다(제목의 MECHANICAL_SUBJECTS 구절, 또는 한 커밋이 html 15개 이상을 건드린 일괄 수정).
→ 메뉴·푸터·도메인 같은 일괄 수정 때문에 모든 페이지의 날짜가 한꺼번에 바뀌어 보이지 않게 한다.
같은 날짜를 거짓으로 꾸미지 않는다: git 기록이 없는 파일(아직 커밋 안 한 새 파일)은 lastmod 를 넣지 않는다.
이미 lastmod 가 있는 항목은 새 값으로 바꾼다. 다른 필드(changefreq·priority)는 건드리지 않는다.
"""
import pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from guide_dates import is_mechanical  # noqa: E402

BASE = "https://mlmusicstudio.co.kr"


def _git(args):
    return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True, check=True).stdout


def file_for(loc):
    path = loc[len(BASE):] if loc.startswith(BASE) else None
    if path is None:
        return None
    if path.endswith("/"):
        path += "index.html"
    f = path.lstrip("/")
    return f if (ROOT / f).exists() else None


def html_count(sha):
    names = _git(["diff-tree", "--no-commit-id", "--name-only", "-r", sha]).split()
    return sum(1 for n in names if n.endswith(".html"))


_count_cache = {}


def lastmod(rel):
    rows = []
    for line in _git(["log", "--follow", "--format=%H\t%ad\t%s", "--date=short", "--", rel]).splitlines():
        if line.strip():
            sha, date, subject = line.split("\t", 2)
            rows.append((sha, date, subject))
    if not rows:
        return None
    real = []
    for sha, date, subject in rows:
        if sha not in _count_cache:
            _count_cache[sha] = html_count(sha)
        if not is_mechanical(subject, _count_cache[sha]):
            real.append(date)
    return max(real) if real else min(d for _, d, _ in rows)


def main():
    f = ROOT / "sitemap.xml"
    text = f.read_text(encoding="utf-8")
    n = {"set": 0, "skip": 0}

    def fix(m):
        block = m.group(0)
        loc = re.search(r"<loc>([^<]*)</loc>", block).group(1)
        rel = file_for(loc)
        date = lastmod(rel) if rel else None
        if not date:
            n["skip"] += 1
            return block
        block = re.sub(r"<lastmod>[^<]*</lastmod>", "", block)
        n["set"] += 1
        return block.replace("</loc>", "</loc><lastmod>%s</lastmod>" % date, 1)

    new = re.sub(r"<url>.*?</url>", fix, text, flags=re.S)
    if new != text:
        f.write_text(new, encoding="utf-8")
    print("lastmod 채움 %d개, 건너뜀(기록 없음) %d개" % (n["set"], n["skip"]))


if __name__ == "__main__":
    sys.exit(main())
