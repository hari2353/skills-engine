"""Build data/packs/onet/master_skills.csv from the O*NET Software Skills file.

Source (Creative Commons 4.0): https://www.onetcenter.org/database.html
-> "Software Skills" CSV (e.g. db_31_0_csv/software_skills.csv).

Usage:
    python scripts/build_onet_pack.py --src software_skills.csv --out data/packs/onet

One master-tier skill per Element Name (category) and one per Workplace Example
(child, parent_id -> its category). Example names repeating across categories
get an md5-suffixed skill_id on collision.
"""
import argparse
import csv
import hashlib
import re
from pathlib import Path

COLUMNS = ["skill_id", "name", "tier", "vendor", "locale", "parent_id", "status", "aliases"]


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "x"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True, help="O*NET software_skills.csv")
    ap.add_argument("--out", type=Path, required=True, help="pack output dir")
    ap.add_argument("--version", default="31.0")
    args = ap.parse_args()

    with args.src.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    vendor = f"O*NET {args.version}"

    # Element ID <-> Element Name is bijective in the source
    parents: dict[str, tuple[str, str]] = {}
    for r in rows:
        eid = r["Element ID"]
        parents.setdefault(eid, (f"onet__{eid.lower().replace('.', '')}", r["Element Name"]))

    out_rows: list[dict] = []
    used_ids: set[str] = set()
    for eid, (pid, pname) in sorted(parents.items()):
        out_rows.append({"skill_id": pid, "name": pname, "tier": "master", "vendor": vendor,
                         "locale": "en", "parent_id": "", "status": "active", "aliases": ""})
        used_ids.add(pid)

    seen: set[tuple[str, str]] = set()
    for r in rows:
        example = r["Workplace Example"].strip()
        eid = r["Element ID"]
        key = (example, eid)
        if not example or key in seen:
            continue
        seen.add(key)
        base = f"onet__{slug(example)}"
        skill_id = base if base not in used_ids else \
            f"{base}_{hashlib.md5((example + '|' + eid).encode()).hexdigest()[:6]}"
        used_ids.add(skill_id)
        out_rows.append({"skill_id": skill_id, "name": example, "tier": "master", "vendor": vendor,
                         "locale": "en", "parent_id": parents[eid][0], "status": "active",
                         "aliases": ""})

    out = args.out / "master_skills.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"wrote {len(out_rows)} skills "
          f"({len(parents)} categories + {len(out_rows) - len(parents)} examples) -> {out}")


if __name__ == "__main__":
    main()
