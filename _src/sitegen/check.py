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
GENERATED_PREFIXES = ("index.html", "en/", "apps/", "tools/")


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
        for link in sorted(set(SRC_ATTR.findall(text))):
            if link.startswith("//"):
                continue
            if not exists(root, link):
                errors.append(f"{rel}: 깨진 src {link}")
        for link in STORE.findall(text):
            if f"pt={PT}" not in link or "ct=homepage" not in link or not MT8.search(link):
                errors.append(f"{rel}: 앱스토어 링크에 pt={PT} / ct=homepage / mt=8 누락 {link[:70]}")
            if "&" in link.replace("&amp;", ""):
                errors.append(f"{rel}: 앱스토어 링크의 & 는 &amp; 여야 함 {link[:70]}")
        errors += page_meta_errors(root, rel, text)
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
