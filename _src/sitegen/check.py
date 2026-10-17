import pathlib
import re

from .kit import BASE

PT = "129167489"        # 앱스토어 캠페인 제공자 토큰(링크 점검 기준)

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
SRC_ATTR = re.compile(r'\ssrc="(/[^"#?]*)')
LINK_TAG = re.compile(r"<link\b[^>]*>")
CANONICAL = re.compile(r'<link\b[^>]*\brel="canonical"[^>]*>')
MT8 = re.compile(r"(?:\?|&amp;|&)mt=8(?!\d)")
# 생성기가 만드는 페이지만 내부 링크를 점검한다(기존 페이지는 건드리지 않음).
GENERATED_PREFIXES = ("index.html", "en/", "apps/", "tools/", "plugins/", "studio/", "about/", "contact/", "privacy/", "work/",
                      "ja/", "zh-Hans/", "es/", "de/", "fr/", "pt-BR/", "timer/", "metronome/")
# 기존(손으로 쓴) 페이지는 사이트 안 링크·src(루트 기준 주소)가 실제 파일을 가리키는지만 본다. 스토어 링크·canonical 등은 건드리지 않는다.
PLAIN_LINK_PREFIXES = ("guides/",)
PLAIN_LINK_FILES = ("policy.html", "nora_legal.html", "patchio_legal.html", "sheetscope_legal.html", "yul_legal.html",
                    # 웹 도구 9쪽(_src/tools/chrome_tools.py 가 사이트 머리·푸터를 넣는다)
                    "rta.html", "trainer.html", "generator.html", "effects-listening.html", "delay-calculator.html",
                    "acoustics-calculator.html", "electrical-calculator.html", "tempo-pitch-calculator.html",
                    "stage-sound-quiz.html")
MAIN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S)
NONKR = ("ja", "zh-Hans", "es", "de", "fr", "pt-BR")


def exists(root, url_path):
    p = root / url_path.lstrip("/")
    return (p / "index.html").exists() if url_path.endswith("/") else p.exists()


def attr(tag, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', tag)
    return m.group(1) if m else None


def own_url(rel):
    """생성된 파일의 상대 경로(rel) -> 사이트 주소."""
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[:-len("index.html")]
    return "/" + rel


def alternates(text):
    """`<link rel="alternate" hreflang=…>` 의 (hreflang, href) 목록."""
    out = []
    for tag in LINK_TAG.findall(text):
        if attr(tag, "rel") == "alternate" and attr(tag, "hreflang"):
            out.append((attr(tag, "hreflang"), attr(tag, "href") or ""))
    return out


def local_path(href):
    """절대 주소(BASE/...) -> 사이트 안 경로. 사이트 밖 주소는 None."""
    return (href[len(BASE):] or "/") if href.startswith(BASE) else None


def page_file(root, url_path):
    p = root / url_path.lstrip("/")
    return p / "index.html" if url_path.endswith("/") else p


NOINDEX_META = '<meta name="robots" content="noindex'
LOC = re.compile(r"<loc>\s*([^<]*?)\s*</loc>")


def sitemap_errors(root):
    """sitemap.xml 의 <loc> 중 우리 주소(BASE)인데 디스크에 없는 것."""
    f = pathlib.Path(root) / "sitemap.xml"
    if not f.exists():
        return []
    errors = []
    for loc in LOC.findall(f.read_text(encoding="utf-8")):
        path = local_path(loc)
        if path is None:
            continue
        if not exists(pathlib.Path(root), path):
            errors.append(f"sitemap.xml: 파일 없는 주소 {path}")
        elif NOINDEX_META in page_file(pathlib.Path(root), path).read_text(encoding="utf-8", errors="ignore"):
            errors.append(f"sitemap.xml: noindex 페이지가 사이트맵에 있음 {path}")
    return errors


def link_errors(root, rel, text):
    """루트 기준 내부 링크(href)·src 가 가리키는 파일이 있는지. 쪽지(#)·쿼리는 떼고 파일만 본다."""
    errors = []
    for pattern, what in ((HREF, "깨진 내부 링크"), (SRC_ATTR, "깨진 src")):
        for link in sorted(set(pattern.findall(text))):
            if not link.startswith("//") and not exists(root, link):
                errors.append(f"{rel}: {what} {link}")
    return errors


def run(root):
    root = pathlib.Path(root)
    errors = []
    errors += sitemap_errors(root)
    for path in PRESERVED:
        if not exists(root, path):
            errors.append(f"보존 주소 없음: {path}")
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel.startswith("_src"):
            continue
        if rel.startswith(PLAIN_LINK_PREFIXES) or rel in PLAIN_LINK_FILES:
            errors += link_errors(root, rel, f.read_text(encoding="utf-8"))
            continue
        if not rel.startswith(GENERATED_PREFIXES):
            continue
        text = f.read_text(encoding="utf-8")
        errors += link_errors(root, rel, text)
        for link in STORE.findall(text):
            if f"pt={PT}" not in link or "ct=homepage" not in link or not MT8.search(link):
                errors.append(f"{rel}: 앱스토어 링크에 pt={PT} / ct=homepage / mt=8 누락 {link[:70]}")
            if "&" in link.replace("&amp;", ""):
                errors.append(f"{rel}: 앱스토어 링크의 & 는 &amp; 여야 함 {link[:70]}")
        errors += page_meta_errors(root, rel, text)
        errors += language_errors(rel, text)
    return errors


def page_meta_errors(root, rel, text):
    """canonical(자기 주소와 일치)·hreflang 짝(대상 존재 + 되돌아오는 링크)·en 고아 페이지 점검."""
    errors = []
    me = own_url(rel)
    canon = CANONICAL.search(text)
    href = attr(canon.group(0), "href") if canon else None
    if href is None:
        errors.append(f"{rel}: canonical 없음")
    elif href != BASE + me:
        errors.append(f"{rel}: canonical 불일치 {href} (기대 {BASE + me})")
    alts = alternates(text)
    for code, target in alts:
        path = local_path(target)
        if path is None:
            errors.append(f"{rel}: hreflang 대상이 사이트 밖 {target}")
            continue
        f = page_file(root, path)
        if not f.exists():
            errors.append(f"hreflang 짝 불일치: {rel} -> {path} (대상 없음)")
            continue
        if path == me:
            continue
        back = {local_path(h) for _, h in alternates(f.read_text(encoding="utf-8"))}
        if me not in back:
            errors.append(f"hreflang 짝 불일치: {rel} -> {path} (대상이 되돌아오는 링크 없음)")
    if rel.startswith("en/") and not any(code == "ko" for code, _ in alts):
        errors.append(f"{rel}: 짝이 되는 ko 페이지(hreflang=ko)가 선언되지 않음")
    return errors


def _visible_text(html):
    html = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", "", html, flags=re.S)
    html = re.sub(r'<(\w+)\b[^>]*\blang="ko"[^>]*>.*?</\1>', "", html, flags=re.S)   # lang="ko" 로 표시한 한글은 정상
    return re.sub(r"<[^>]+>", " ", html)


def language_errors(rel, text):
    """비(非)ko/en 페이지의 한글 노출, 빈 h1, html lang 불일치 점검."""
    errors = []
    lang = rel.split("/", 1)[0] if rel.split("/", 1)[0] in NONKR else None
    m = MAIN.search(text)
    main = m.group(1) if m else ""
    if lang and re.search(r"[가-힣]", _visible_text(main)):
        errors.append(f"{rel}: {lang} 페이지에 한글 노출")
    h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", main, re.S)
    if not h1 or not _visible_text(h1.group(1)).strip():
        errors.append(f"{rel}: h1 비어 있음")
    if lang:
        hl = re.search(r'<html\b[^>]*\blang="([^"]*)"', text)
        if not hl or hl.group(1) != lang:
            errors.append(f"{rel}: html lang 불일치")
    return errors
