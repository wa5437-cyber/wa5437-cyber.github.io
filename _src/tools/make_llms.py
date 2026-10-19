#!/usr/bin/env python3
"""사이트 요약본 /llms.txt 를 만든다(AI 검색·요약이 사이트를 정확히 이해하도록). 사용: python3 _src/tools/make_llms.py
내용은 _src/content 와 guides/*.html 에서 읽는다. 가이드나 앱이 늘면 다시 실행한다."""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = "https://mlmusicstudio.co.kr"


def j(name):
    return json.loads((ROOT / "_src" / "content" / name).read_text(encoding="utf-8"))


def guides():
    out = []
    for f in sorted((ROOT / "guides").glob("*.html")):
        if f.name == "index.html":
            continue
        t = f.read_text(encoding="utf-8")
        h1 = re.search(r"<h1>(.*?)</h1>", t, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)"', t)
        if h1 and d:
            out.append((html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip(), f.name, html.unescape(d.group(1)).strip()))
    return out


def main():
    apps, tools = j("apps.json")["apps"], j("tools.json")["en"]["groups"]
    L = ["# ML Music Studio (엠엘뮤직스튜디오)", "",
         "> ML Music Studio is a recording, mixing and mastering studio in Yongsan, Seoul, run by sound engineer Hyoseop Lee (이효섭). "
         "It also makes iOS/Mac apps and free browser tools for sound engineers and musicians. Site languages: Korean and English; "
         "app pages also in Japanese, Simplified Chinese, Spanish, German, French and Brazilian Portuguese; guides are in Korean.", "",
         "서울 용산의 녹음·믹싱·마스터링 스튜디오이며, 사운드 엔지니어 이효섭이 만든 앱과 무료 웹 도구, 음향 가이드를 제공합니다.", "",
         "## Studio", f"- [Home]({B}/): overview", f"- [Work]({B}/work/): selected albums, films and stage work",
         f"- [Studio]({B}/studio/): the room and gear", f"- [About]({B}/about/): the engineer",
         f"- [Contact]({B}/contact/): by appointment via KakaoTalk", "", "## Apps"]
    for a in apps:
        L.append(f"- [{a['name']['en']} / {a['name']['ko']}]({B}/en/apps/{a['slug']}/): {a['tagline']['en'].split('. ')[0].rstrip('.')}")
    L += ["", "## Free web tools (no install)"]
    for g in tools:
        for it in g["items"]:
            L.append(f"- [{it['name']}]({B}{it['href'] if it['href'].startswith('/') else '/' + it['href']}): {it['text']}")
    L += ["", "## Guides (Korean)"]
    for title, name, desc in guides():
        L.append(f"- [{title}]({B}/guides/{name}): {desc}")
    L += ["", "## Notes", "- Measurement features (RTA/SPL) use the device microphone and are for reference, not calibrated measurement.",
          "- Timer and metronome settings are stored only in the visitor's browser (localStorage).",
          f"- Sitemap: {B}/sitemap.xml", ""]
    (ROOT / "llms.txt").write_text("\n".join(L), encoding="utf-8")
    print("llms.txt", len(L), "lines")


if __name__ == "__main__":
    main()
