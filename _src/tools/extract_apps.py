#!/usr/bin/env python3
"""policy.html(옛 홈)의 앱 카드에서 앱 목록을 뽑아 content/apps.json 으로 쓴다. 한 번만 쓰는 도구."""
import json, pathlib, re, sys, html as H

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "_src" / "content" / "apps.json"

# (slug, i18n 키 접두사, 표시 이름 ko, 표시 이름 en, 약관 페이지)
APPS = [
    ("stage-sound", "app_stage", "무대음향 자격증 기출문제", "Stage Sound Exam Prep (Korea)", None),
    ("ear-trainer", "app_eartrainer", "AudioEngineer Ear Trainer", "AudioEngineer Ear Trainer", None),
    ("spl-rta", "app_splrta", "AudioEngineerKit: SPL & RTA", "AudioEngineerKit: SPL & RTA", None),
    ("toolkit", "app_toolkit", "AudioEngineerToolkit", "AudioEngineerToolkit", None),
    ("aet-quiz", "app_quiz", "AET Quiz", "AET Quiz", None),
    ("keymap", "app_keymap", "DAW 단축키 — KeyMap", "DAW Shortcuts — KeyMap", None),
    ("patchio", "app_patchio", "Patch & I/O", "Patch & I/O", "/patchio_legal.html"),
    ("nora", "app_nora", "NORA — 커버곡 노래 녹음", "NORA — Cover Song Recording", "/nora_legal.html"),
    ("yul", "app_yul", "율 — 국악 튜너 & 장단", "Yul — Gugak Tuner & Janggu Rhythm", "/yul_legal.html"),
    ("sheetscope", "app_sheetscope", "SheetScope", "SheetScope", "/sheetscope_legal.html"),
    ("temposcope", "app_temposcope", "TempoScope", "TempoScope", None),
]

def main():
    existing = {}
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
    if existing.get("apps") and "--force" not in sys.argv[1:]:
        print("apps.json 에 이미 앱 목록이 있습니다. 덮어쓰려면 --force 를 붙이세요(details 는 보존됩니다).")
        sys.exit(1)
    t = (ROOT / "policy.html").read_text(encoding="utf-8")
    m = re.search(r"const I18N\s*=\s*(\{.*?\});\s*\n", t, re.S)
    i18n = json.loads(m.group(1))
    seg = t[t.find('id="apps"'):t.find('id="tools"')]
    # 카드 순서와 같은 순서로 스토어 링크를 뽑는다(카드마다 1개씩).
    links = re.findall(r'href="(https://apps\.apple\.com/[^"]+)"', seg)
    unique = []
    for l in links:
        if l not in unique:
            unique.append(l)
    assert len(unique) == len(APPS), (len(unique), len(APPS))

    def pick(key, lang):
        d = i18n.get(key, {})
        return d.get(lang) or d.get("en") or d.get("ko") or ""

    out = {"apps": [], "details": existing.get("details", {})}
    for (slug, key, ko, en, legal), link in zip(APPS, unique):
        out["apps"].append({
            "slug": slug,
            "name": {"ko": ko, "en": en},
            "tagline": {"ko": pick(key + "_desc", "ko"), "en": pick(key + "_desc", "en")},
            "badge": {"ko": pick(key + "_badge", "ko"), "en": pick(key + "_badge", "en")},
            "appstore": H.unescape(link).split("?")[0],
            "play": "https://play.google.com/store/apps/details?id=com.mlmusicstudio.stagesoundexam" if slug == "stage-sound" else None,
            "legal": legal,
            "detail": slug == "stage-sound",
        })
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("앱", len(out["apps"]), "개 기록")


if __name__ == "__main__":
    main()
