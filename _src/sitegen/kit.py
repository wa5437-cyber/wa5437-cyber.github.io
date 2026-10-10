import html
import pathlib


def esc(s):
    return html.escape(str(s), quote=True)


def url(lang, path):
    """ko 는 기본(접두사 없음), en 은 /en 접두사."""
    return path if lang == "ko" else "/en" + path


def write(root, url_path, content):
    root = pathlib.Path(root)
    rel = url_path.lstrip("/")
    target = root / (rel + "index.html" if url_path.endswith("/") else rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
