import pathlib
import re

# 이동·삭제되면 안 되는 주소(파일). 폴더형(`/`로 끝남)은 index.html 로 확인한다.
PRESERVED = [
    "/guides/", "/about.html", "/sheetscope_legal.html", "/yul_legal.html", "/patchio_legal.html",
    "/nora_legal.html", "/stage-sound-quiz.html", "/delay-calculator.html", "/acoustics-calculator.html",
    "/electrical-calculator.html", "/tempo-pitch-calculator.html", "/effects-listening.html",
    "/trainer.html", "/generator.html", "/rta.html", "/ads.txt", "/robots.txt", "/sitemap.xml",
    "/CNAME", "/favicon.svg", "/og-image.png",
]
STORE = re.compile(r'href="(https://apps\.apple\.com/[^"]*)"')
HREF = re.compile(r'href="(/[^"#?]*)')
# 생성기가 만드는 페이지만 내부 링크를 점검한다(기존 페이지는 건드리지 않음).
GENERATED_PREFIXES = ("index.html", "en/", "apps/", "tools/")


def exists(root, url_path):
    p = root / url_path.lstrip("/")
    return (p / "index.html").exists() if url_path.endswith("/") else p.exists()


def run(root):
    root = pathlib.Path(root)
    errors = []
    for path in PRESERVED:
        if not exists(root, path):
            errors.append(f"보존 주소 없음: {path}")
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if not rel.startswith(GENERATED_PREFIXES) or rel.startswith("_src"):
            continue
        text = f.read_text(encoding="utf-8")
        for link in sorted(set(HREF.findall(text))):
            if link.startswith("//"):
                continue
            if not exists(root, link):
                errors.append(f"{rel}: 깨진 내부 링크 {link}")
        for link in STORE.findall(text):
            if "pt=129167489" not in link or "ct=homepage" not in link:
                errors.append(f"{rel}: 앱스토어 링크에 pt=129167489 / ct=homepage 누락 {link[:70]}")
            if "&" in link.replace("&amp;", ""):
                errors.append(f"{rel}: 앱스토어 링크의 & 는 &amp; 여야 함 {link[:70]}")
    return errors
