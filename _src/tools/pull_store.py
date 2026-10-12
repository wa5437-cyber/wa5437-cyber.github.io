#!/usr/bin/env python3
"""앱스토어에 올라가 있는(READY_FOR_SALE) 현지화 문구를 content/apps/<slug>.json 의 "store" 로 가져온다.

읽기 전용. 사용: python3 _src/tools/pull_store.py [--allow-empty] [slug ...]   (인자 없으면 apps.json 의 모든 앱)
심사 중·준비 중 버전에만 있는 문구는 쓰지 않는다(아직 공개되지 않은 기능을 사이트가 먼저 말하지 않도록).
"""
import json
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path.home() / ".claude" / "skills" / "appstore-metadata"))

LIVE_STATES = ("READY_FOR_SALE", "READY_FOR_DISTRIBUTION")   # Apple 이 상태 이름을 옮겨 가는 중이라 둘 다 공개 중으로 본다
LOCALES = {"ko": "ko", "en-US": "en", "ja": "ja", "zh-Hans": "zh-Hans", "es-ES": "es",
           "de-DE": "de", "fr-FR": "fr", "pt-BR": "pt-BR"}


def map_locale(asc_locale):
    return LOCALES.get(asc_locale)


def _ready_version(get, app_id):
    """공개 중(READY_FOR_SALE)인 가장 높은 IOS 버전. IOS 가 하나도 없으면(맥 전용 앱) 가장 높은 MAC_OS 버전."""
    vs = get(f"/apps/{app_id}/appStoreVersions", limit=50)["data"]

    def key(v):
        return [int(x) for x in re.findall(r"\d+", v["attributes"].get("versionString", "0"))]
    def live(v):
        at = v["attributes"]      # 어느 키로 오든(옛 appStoreState / 새 appVersionState / state) 본다
        return any(at.get(k) in LIVE_STATES for k in ("appStoreState", "appVersionState", "state"))
    for platform in ("IOS", "MAC_OS"):
        ready = [v for v in vs if v["attributes"].get("platform") == platform and live(v)]
        if ready:
            return max(ready, key=key)
    return None


def collect(app_id, get=None):
    if get is None:
        get = _asc_get
    v = _ready_version(get, app_id)
    if v is None:
        return {}
    out = {}
    for loc in get(f"/appStoreVersions/{v['id']}/appStoreVersionLocalizations", limit=50)["data"]:
        a = loc["attributes"]
        lang = map_locale(a["locale"])
        if lang:
            out[lang] = {"description": (a.get("description") or "").strip(),
                         "promo": (a.get("promotionalText") or "").strip()}
    infos = list(get(f"/apps/{app_id}/appInfos", limit=10)["data"])

    def is_live(i):
        at = i["attributes"]
        return any(at.get(k) in LIVE_STATES for k in ("state", "appStoreState"))
    # 공개 중인 appInfo 만 쓴다. 하나뿐일 때만 상태와 무관하게 쓴다(여럿인데 공개 표시가 없으면 초안일 수 있어 쓰지 않는다).
    live = [i for i in infos if is_live(i)][:1] or (infos if len(infos) == 1 else [])
    for info in live:
        for loc in get(f"/appInfos/{info['id']}/appInfoLocalizations", limit=50)["data"]:
            a = loc["attributes"]
            lang = map_locale(a["locale"])
            if lang:
                out.setdefault(lang, {"description": "", "promo": ""}).update(
                    name=(a.get("name") or "").strip(), subtitle=(a.get("subtitle") or "").strip())
    return {lang: {"name": d.get("name", ""), "subtitle": d.get("subtitle", ""),
                   "promo": d["promo"], "description": d["description"]}
            for lang, d in out.items() if d.get("name") and d["description"]}


def _asc_get(path, **params):
    """asc.get 은 /v1 을 포함한 전체 경로를 받는다. 이 모듈은 /v1 없는 경로를 쓴다."""
    import asc
    return asc.get("/v1" + path, **params)


def app_id_from_url(url):
    m = re.search(r"/id(\d+)", url)
    return m.group(1) if m else None


def merge_store(existing, new, allow_empty=False):
    """새로 읽은 store 로 바꾸되, 기존에 내용이 있는데 새 결과가 비면(API 오류·상태 이름 변경 등) 기존 것을 지키고 경고한다."""
    if not new and existing and not allow_empty:
        print("경고: 앱스토어에서 공개 문구를 하나도 못 읽었습니다 — 기존 store 를 그대로 둡니다 "
              "(정말 비우려면 --allow-empty).", file=sys.stderr)
        return existing
    return new


def main(argv):
    allow_empty = "--allow-empty" in argv
    argv = [a for a in argv if a != "--allow-empty"]
    apps = json.loads((SRC / "content" / "apps.json").read_text(encoding="utf-8"))["apps"]
    want = set(argv) or {a["slug"] for a in apps}
    for a in apps:
        if a["slug"] not in want:
            continue
        app_id = app_id_from_url(a["appstore"])
        if not app_id:
            print(f"{a['slug']}: 앱스토어 주소에서 id 를 못 찾음 — 건너뜀")
            continue
        store = collect(app_id)
        f = SRC / "content" / "apps" / f"{a['slug']}.json"
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        store = merge_store(data.get("store"), store, allow_empty)
        data["store"] = store          # detail 등 다른 키는 그대로 둔다
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{a['slug']}: {', '.join(store) or '(공개 문구 없음)'}")


if __name__ == "__main__":
    main(sys.argv[1:])
