"""웹 도구 2개(온라인 타이머·메트로놈)의 8개 언어 페이지.

내용은 content/clock/<도구>/<언어>.json (meta·ui·article·related) 에 있고, 여기서는 도구 화면의 뼈대(HTML)와
설명 글·관련 링크·JSON-LD 를 조립해 kit.page 에 넘긴다. 동작은 assets/*.js 가 한다.
"""
import hashlib
import json
import pathlib
import re

from . import kit
from .kit import esc, url

SRC = pathlib.Path(__file__).resolve().parents[1]
ROOT = SRC.parent

TOOLS = ("timer", "metronome")
SCRIPTS = {"timer": ("timer-core.js", "timer.js"), "metronome": ("metronome-core.js", "metronome.js")}
CSS = "tools-clock.css"
CATEGORY = {"timer": "UtilitiesApplication", "metronome": "MultimediaApplication"}


def load(tool, lang):
    f = SRC / "content" / "clock" / tool / f"{lang}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def tool_path(lang, tool):
    return url(lang, f"/{tool}/")


def tool_alts(tool):
    return {lang: tool_path(lang, tool) for lang in kit.LANGS}


def tool_paths_ko():
    """한국어(접두사 없는) 주소 목록: ['/timer/', '/metronome/']"""
    return [tool_path("ko", t) for t in TOOLS]


def all_paths():
    return [tool_path(lang, tool) for tool in TOOLS for lang in kit.LANGS]


def asset(name):
    """/assets/<name>?v=<내용 해시>: 파일이 바뀌면 주소가 바뀌어 캐시가 새로 받는다."""
    data = (ROOT / "assets" / name).read_bytes()
    return f"/assets/{name}?v={hashlib.sha1(data).hexdigest()[:10]}"


def bold(text):
    """esc 한 뒤 **굵게** 만 <strong> 으로."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


# ---------------------------------------------------------------------------
# 도구 화면 뼈대
# ---------------------------------------------------------------------------

def _num(fid, label, mn, mx, val, cls="ck-field"):
    return (f'<div class="{cls}"><label for="{fid}">{esc(label)}</label>'
            f'<input id="{fid}" type="number" inputmode="numeric" min="{mn}" max="{mx}" value="{val}"></div>')


def timer_shell(u):
    e = lambda k: esc(u[k])
    modes = ("countdown", "stopwatch", "range", "interval", "booking")
    tabs = "".join(
        f'<button type="button" role="tab" id="tab-{m}" aria-controls="panel-{m}" '
        f'aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{e("tab_" + m)}</button>'
        for i, m in enumerate(modes))

    def panel(m, inner):
        hid = "" if m == modes[0] else " hidden"
        return (f'<div role="tabpanel" id="panel-{m}" aria-labelledby="tab-{m}" class="ck-panel" '
                f'data-mode="{m}"{hid}>{inner}</div>')

    quick = "".join(
        f'<button type="button" class="btn" data-quick="{n}" aria-label="{esc(u["quick_aria"].replace("{n}", str(n)))}">'
        f'{esc(u["quick_label"].replace("{n}", str(n)))}</button>' for n in (5, 10, 30))
    p_countdown = panel("countdown",
        '<div class="ck-fields">' + _num("cd-h", u["lbl_hours"], 0, 99, 0) + _num("cd-m", u["lbl_minutes"], 0, 59, 25) +
        _num("cd-s", u["lbl_seconds"], 0, 59, 0) + '</div>'
        f'<div class="ck-quick" role="group" aria-label="{e("quick_group")}">{quick}</div>')
    p_stopwatch = panel("stopwatch", f'<p class="ck-note">{e("sw_hint")}</p>')
    p_range = panel("range",
        '<div class="ck-fields">'
        f'<div class="ck-field"><label for="rg-start">{e("lbl_range_start")}</label><input id="rg-start" type="time"></div>'
        f'<div class="ck-field"><label for="rg-end">{e("lbl_range_end")}</label><input id="rg-end" type="time"></div>'
        f'<button type="button" id="rg-now" class="btn" aria-label="{e("btn_now_aria")}">{e("btn_now")}</button>'
        f'<button type="button" id="rg-apply" class="btn primary">{e("btn_apply")}</button></div>'
        f'<p class="ck-note">{e("range_hint")}</p><p id="range-msg" class="ck-error" role="alert" hidden></p>')
    presets = "".join(f'<option value="{k}">{e("preset_" + k)}</option>' for k in ("mix", "pomodoro", "practice", "custom"))
    p_interval = panel("interval",
        f'<div class="ck-fields"><div class="ck-field ck-wide"><label for="iv-preset">{e("lbl_preset")}</label>'
        f'<select id="iv-preset">{presets}</select></div>'
        + _num("iv-work", u["lbl_work_min"], 1, 600, 45) + _num("iv-rest", u["lbl_rest_min"], 0, 600, 5)
        + _num("iv-cycles", u["lbl_cycles"], 0, 99, 4) + '</div>'
        f'<p class="ck-note">{e("iv_hint")}</p>')
    book = "".join(
        f'<button type="button" class="btn primary" data-book="{h}" aria-label="{esc(u["book_aria"].replace("{n}", str(h)))}">'
        f'{esc(u["dur_h"].replace("{n}", str(h)))}</button>' for h in (1, 2, 3))
    p_booking = panel("booking",
        f'<p class="ck-note">{e("book_intro")}</p><div class="ck-quick" role="group" aria-label="{e("book_group")}">{book}</div>'
        '<div class="ck-fields">' + _num("book-pre", u["lbl_book_pre"], 0, 120, 10) + '</div>')

    display = (
        '<div class="ck-display" id="display-card" data-state="idle">'
        '<p class="ck-label" id="disp-label"></p>'
        '<div class="ck-time" id="disp-time" role="timer" aria-live="off" aria-labelledby="disp-label">00:00</div>'
        '<div class="ck-bar" id="disp-barwrap" aria-hidden="true"><span id="disp-bar"></span></div>'
        '<dl class="ck-stats" id="range-stats" hidden>'
        f'<div><dt>{e("range_window")}</dt><dd id="rs-window"></dd></div><div><dt>{e("range_total")}</dt><dd id="rs-total"></dd></div>'
        f'<div><dt>{e("range_elapsed")}</dt><dd id="rs-elapsed"></dd></div><div><dt>{e("range_left")}</dt><dd id="rs-left"></dd></div></dl>'
        '<div class="ck-controls">'
        f'<button type="button" id="btn-main" class="btn primary ck-big">{e("btn_start")}</button>'
        f'<button type="button" id="btn-lap" class="btn" hidden>{e("btn_lap")}</button>'
        f'<button type="button" id="btn-reset" class="btn" disabled>{e("btn_reset")}</button>'
        f'<button type="button" id="btn-full" class="btn">{e("btn_full")}</button></div>'
        f'<p class="ck-other" id="other-run" hidden><span id="other-run-text"></span> '
        f'<button type="button" id="btn-goto" class="btn ck-mini">{e("btn_goto")}</button></p>'
        '<div id="laps-wrap" hidden>'
        f'<div class="lap-head" aria-hidden="true"><span></span><span>{e("lap_split")}</span><span>{e("lap_total")}</span></div>'
        f'<ol id="laps" class="ck-laps" aria-label="{e("lap_title")}"></ol></div></div>')

    sounds = "".join(f'<option value="{k}">{e("sound_" + k)}</option>' for k in ("bell", "beep", "chime"))
    opts = (
        f'<fieldset class="ck-opts"><legend>{e("opts_title")}</legend>'
        f'<div class="ck-opt"><label class="ck-check"><input type="checkbox" id="opt-pre"><span>{e("opt_pre")}</span></label>'
        f'<span class="ck-inline"><input id="opt-pre-min" type="number" inputmode="numeric" min="1" max="999" value="5" '
        f'aria-label="{e("lbl_pre_aria")}"><span aria-hidden="true">{e("lbl_pre_min")}</span></span></div>'
        '<div id="opt-audio-box">'
        f'<div class="ck-opt"><label for="opt-sound">{e("lbl_sound")}</label><select id="opt-sound">{sounds}</select>'
        f'<button type="button" class="btn ck-mini" id="opt-test">{e("btn_test")}</button></div>'
        f'<div class="ck-opt"><label for="opt-volume">{e("lbl_volume")}</label>'
        '<input id="opt-volume" type="range" min="0" max="100" value="70"></div>'
        f'<div class="ck-opt"><label for="opt-repeat">{e("lbl_repeat")}</label>'
        '<input id="opt-repeat" type="number" inputmode="numeric" min="1" max="5" value="2"></div></div>'
        f'<div class="ck-opt" id="opt-notify-row"><label class="ck-check"><input type="checkbox" id="opt-notify"><span>{e("opt_notify")}</span></label></div>'
        f'<div class="ck-opt" id="opt-wake-row"><label class="ck-check"><input type="checkbox" id="opt-wake"><span>{e("opt_wake")}</span></label></div>'
        f'</fieldset><p class="ck-note">{e("opt_note")}</p>')

    return (f'<div class="ck-tool" id="tool" data-tool="timer">'
            f'<div class="ck-tabs" role="tablist" aria-label="{e("tabs_label")}">{tabs}</div>'
            f'<div class="ck-modes">{p_countdown}{p_stopwatch}{p_range}{p_interval}{p_booking}</div>'
            f'{display}<p id="hint" class="ck-hint" role="status" hidden></p>{opts}'
            '<p id="sr-live" class="sr-only" aria-live="polite" aria-atomic="true"></p></div>')


def metronome_shell(u):
    e = lambda k: esc(u[k])
    sigs = "".join(f'<option value="{s}">{esc(s)}</option>' for s in ("2/4", "3/4", "4/4", "5/4", "6/8", "7/8")) \
        + f'<option value="custom">{e("sig_custom")}</option>'
    subs = "".join(f'<option value="{s}">{e("sub_" + s)}</option>' for s in ("quarter", "eighth", "triplet", "sixteenth"))
    sounds = "".join(f'<option value="{s}">{e("sound_" + s)}</option>' for s in ("click", "wood", "beep"))
    display = (
        '<div class="ck-display met" id="display-card" data-state="idle">'
        '<div class="ck-bpm-row">'
        f'<button type="button" id="bpm-down" class="ck-round" aria-label="{e("bpm_down_aria")}">−</button>'
        '<div class="ck-bpm-box">'
        f'<input id="bpm" type="number" inputmode="numeric" min="20" max="300" value="100" aria-label="{e("bpm_input_aria")}">'
        f'<span class="ck-unit" aria-hidden="true">BPM</span></div>'
        f'<button type="button" id="bpm-up" class="ck-round" aria-label="{e("bpm_up_aria")}">+</button></div>'
        f'<p class="ck-term" id="term"></p>'
        f'<input id="bpm-range" class="ck-slider" type="range" min="20" max="300" value="100" aria-label="{e("bpm_slider_aria")}">'
        f'<div class="ck-leds" id="leds" role="img" aria-label="{e("beats_aria")}"></div>'
        '<p class="ck-bar-count" id="bar-count"></p>'
        '<div class="ck-controls">'
        f'<button type="button" id="btn-main" class="btn primary ck-big" aria-pressed="false">{e("btn_start")}</button>'
        f'<button type="button" id="btn-tap" class="btn ck-big">{e("btn_tap")}</button></div>'
        '<p class="ck-note" id="tap-info" hidden></p></div>')
    settings = (
        '<div class="ck-grid">'
        f'<div class="ck-card"><h2 class="ck-h">{e("grp_rhythm")}</h2>'
        f'<div class="ck-opt"><label for="sig">{e("lbl_sig")}</label><select id="sig">{sigs}</select></div>'
        f'<div class="ck-opt" id="sig-custom-wrap" hidden><label for="sig-custom">{e("lbl_beats")}</label>'
        '<input id="sig-custom" type="number" inputmode="numeric" min="1" max="16" value="5"></div>'
        f'<div class="ck-opt"><label for="sub">{e("lbl_sub")}</label><select id="sub">{subs}</select></div>'
        f'<p class="ck-note">{e("sig_note")}</p></div>'
        f'<div class="ck-card"><h2 class="ck-h">{e("grp_sound")}</h2>'
        f'<div class="ck-opt"><label for="sound">{e("lbl_sound")}</label><select id="sound">{sounds}</select></div>'
        f'<div class="ck-opt"><label for="volume">{e("lbl_volume")}</label><input id="volume" type="range" min="0" max="100" value="80"></div>'
        f'<div class="ck-opt"><label class="ck-check"><input type="checkbox" id="opt-accent" checked><span>{e("opt_accent")}</span></label></div>'
        f'<div class="ck-opt" id="opt-wake-row"><label class="ck-check"><input type="checkbox" id="opt-wake"><span>{e("opt_wake")}</span></label></div></div>'
        f'<div class="ck-card"><h2 class="ck-h">{e("trainer_title")}</h2>'
        f'<div class="ck-opt"><label class="ck-check"><input type="checkbox" id="tr-on"><span>{e("opt_trainer")}</span></label></div>'
        '<div class="ck-fields">' + _num("tr-start", u["lbl_tr_start"], 20, 300, 80) + _num("tr-target", u["lbl_tr_target"], 20, 300, 120)
        + _num("tr-every", u["lbl_tr_every"], 1, 64, 4) + _num("tr-step", u["lbl_tr_step"], 1, 50, 5) + '</div>'
        f'<p class="ck-note" id="tr-note" hidden></p></div>'
        f'<div class="ck-card"><h2 class="ck-h">{e("practice_title")}</h2>'
        '<div class="ck-fields">' + _num("pr-min", u["lbl_practice_min"], 0, 180, 0) + '</div>'
        f'<p class="ck-note">{e("practice_note")}</p><p class="ck-practice-left" id="pr-left" hidden></p></div></div>')
    kb = (f'<div class="ck-card ck-kb"><h2 class="ck-h">{e("kb_title")}</h2><ul>'
          + "".join(f'<li>{e(k)}</li>' for k in ("kb_space", "kb_arrows", "kb_tap")) + '</ul></div>')
    return ('<div class="ck-tool" id="tool" data-tool="metronome">' + display +
            '<p id="hint" class="ck-hint" role="status" hidden></p>' + settings + kb +
            f'<p class="ck-note">{e("opt_note")}</p>'
            '<p id="sr-live" class="sr-only" aria-live="polite" aria-atomic="true"></p></div>')


SHELLS = {"timer": timer_shell, "metronome": metronome_shell}


# ---------------------------------------------------------------------------
# 설명 글·관련 링크
# ---------------------------------------------------------------------------

def render_blocks(blocks):
    out = []
    for b in blocks:
        if "h3" in b:
            out.append(f'<h3>{esc(b["h3"])}</h3>')
        elif "p" in b:
            out.append(f'<p>{bold(b["p"])}</p>')
        elif "ol" in b:
            out.append("<ol>" + "".join(f"<li>{bold(x)}</li>" for x in b["ol"]) + "</ol>")
        elif "ul" in b:
            out.append("<ul>" + "".join(f"<li>{bold(x)}</li>" for x in b["ul"]) + "</ul>")
        elif "faq" in b:
            for qa in b["faq"]:
                out.append(f'<h3>{esc(qa["q"])}</h3><p>{bold(qa["a"])}</p>')
        else:
            raise ValueError(f"unknown block: {list(b)}")
    return "".join(out)


def article_html(c):
    return "".join(f'<h2>{esc(s["h2"])}</h2>{render_blocks(s["blocks"])}' for s in c["article"])


def article_text(c):
    """설명 글의 글자만(태그 없이). 분량 점검용."""
    parts = []
    for s in c["article"]:
        parts.append(s["h2"])
        for b in s["blocks"]:
            for k in ("h3", "p"):
                if k in b:
                    parts.append(b[k])
            for k in ("ol", "ul"):
                parts.extend(b.get(k, []))
            for qa in b.get("faq", []):
                parts += [qa["q"], qa["a"]]
    return "\n".join(parts)


def related_links(lang, tool, c):
    """(주소, 글, 한국어 가이드 여부) 목록. 파일·페이지가 실제로 있는 것만."""
    from . import pages
    labels = c["related"]["items"]
    out = []

    def add(key, href, guide=False, check=True):
        target = ROOT / href.lstrip("/")
        if not check or (target / "index.html" if href.endswith("/") else target).exists():
            out.append((href, labels[key], guide))

    other = "metronome" if tool == "timer" else "timer"
    out.append((tool_path(lang, other), labels[other], False))
    if tool == "timer":
        add("trainer", "/trainer.html")
        add("gain", "/guides/gain-staging-basics.html", True)
        add("pink", "/guides/pink-noise-eq-ear-training.html", True)
    else:
        add("bpm_delay", "/guides/bpm-to-delay-time.html", True)
        add("tempo_calc", "/tempo-pitch-calculator.html")
        if lang in pages.alts_for_app("temposcope"):
            add("temposcope", url(lang, "/apps/temposcope/"), check=False)   # 앱 상세 유무는 alts_for_app 이 안다
    return out


def related_html(lang, tool, c):
    r = c["related"]
    items = ""
    for href, label, guide in related_links(lang, tool, c):
        tag = f' <span class="ck-tag">{esc(r["guide_tag"])}</span>' if guide and r.get("guide_tag") else ""
        items += f'<li><a href="{esc(href)}">{esc(label)}</a>{tag}</li>'
    return f'<h2>{esc(r["heading"])}</h2><ul class="ck-related">{items}</ul>'


# ---------------------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------------------

def json_ld(lang, tool, c):
    m = c["meta"]
    data = {"@context": "https://schema.org", "@type": "WebApplication", "name": m["h1"],
            "description": m["description"], "applicationCategory": CATEGORY[tool], "operatingSystem": "Any",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "inLanguage": lang, "url": kit.BASE + tool_path(lang, tool)}
    return ('<script type="application/ld+json">' +
            json.dumps(data, ensure_ascii=False).replace("<", "\\u003c") + "</script>")


def page(lang, tool):
    c = load(tool, lang)
    m = c["meta"]
    path = tool_path(lang, tool)
    shell = SHELLS[tool](c["ui"])
    i18n = json.dumps({"lang": lang, "ui": c["ui"]}, ensure_ascii=False).replace("<", "\\u003c")
    head = (f'<link rel="stylesheet" href="{asset(CSS)}">\n'
            + "".join(f'<script defer src="{asset(s)}"></script>\n' for s in SCRIPTS[tool])
            + json_ld(lang, tool, c))
    body = (f'<section class="hero ck-hero"><div class="wrap"><h1>{esc(m["h1"])}</h1>'
            f'<p class="sub">{esc(m["sub"])}</p></div></section>'
            f'<section class="band ck-band"><div class="wrap">{shell}'
            f'<noscript><p class="ck-error">{esc(c["ui"]["noscript"])}</p></noscript></div></section>'
            f'<section class="band ck-article-band"><div class="wrap"><article class="ck-prose">'
            f'{article_html(c)}{related_html(lang, tool, c)}</article></div></section>'
            f'<script type="application/json" id="i18n">{i18n}</script>')
    return path, kit.page(lang, path, m["title"], m["description"], body, tool_alts(tool), extra_head=head, ads=True)


def build(root):
    """16쪽(2 도구 × 8 언어)을 쓰고 주소 목록을 돌려준다."""
    made = []
    for tool in TOOLS:
        for lang in kit.LANGS:
            path, html = page(lang, tool)
            kit.write(root, path, html)
            made.append(path)
    return made
