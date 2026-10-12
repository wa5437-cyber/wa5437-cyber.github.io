#!/usr/bin/env python3
"""경력_정리.csv 에서 숫자를 계산해 content/career.json 에 쓴다(works 는 보존). 사용: career_stats.py <csv> """
import csv, json, pathlib, sys

OUT = pathlib.Path(__file__).resolve().parents[1] / "content" / "career.json"
ROLE_WORDS = {"마스터링": ("마스터링",), "믹싱": ("믹싱",), "녹음": ("녹음", "레코딩")}


def compute(rows):
    roles = {k: 0 for k in ROLE_WORDS}
    years = []
    for r in rows:
        role = r.get("역할", "") or ""
        years.append(int(r["년도"]))
        for k, words in ROLE_WORDS.items():
            if any(w in role for w in words):
                roles[k] += 1
    return {"since": min(years), "total": len(rows), "roles": roles}


def main(csv_path, out_path=OUT):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        stats = compute(list(csv.DictReader(f)))
    out = pathlib.Path(out_path)
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"works": []}
    data.update(stats)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    main(sys.argv[1])
