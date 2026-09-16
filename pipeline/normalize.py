"""
normalize.py -- Stage: Input normalization

Reads apps.csv and produces a clean, uniform list of app records to feed
into research. Handles header-name variance (e.g. "App Name" vs "app" vs
"Application"), trims whitespace, drops empty rows, de-duplicates by app
name, and assigns a stable app_id (slug) used to name per-app raw research
files (research/v1_raw/<app_id>.json etc.) so outputs are traceable back to
inputs.
"""

from __future__ import annotations
import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict

# Accepted header aliases -> canonical field
HEADER_ALIASES = {
    "app": "app", "app name": "app", "application": "app", "name": "app",
    "category": "category", "vertical": "category", "cat": "category",
    "website": "website_hint", "website/developer-documentation hint": "website_hint",
    "website hint": "website_hint", "docs": "website_hint", "documentation": "website_hint",
    "hint": "website_hint", "url": "website_hint", "domain": "website_hint",
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return re.sub(r"-+", "-", s).strip("-")


def _canonical_headers(fieldnames: List[str]) -> Dict[str, str]:
    mapping = {}
    for h in fieldnames:
        key = h.strip().lower()
        canon = HEADER_ALIASES.get(key)
        if canon:
            mapping[h] = canon
    return mapping


def load_apps_csv(path: str) -> List[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"apps.csv not found at {path}")

    with p.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header_map = _canonical_headers(reader.fieldnames or [])
        missing = {"app", "category"} - set(header_map.values())
        if missing:
            raise ValueError(
                f"apps.csv is missing required column(s): {missing}. "
                f"Found headers: {reader.fieldnames}"
            )

        rows = []
        seen_ids = set()
        for i, raw_row in enumerate(reader):
            row = {}
            for h, v in raw_row.items():
                canon = header_map.get(h)
                if canon:
                    row[canon] = (v or "").strip()
            if not row.get("app"):
                continue  # skip blank rows

            app_id = slugify(row["app"])
            base_id = app_id
            n = 2
            while app_id in seen_ids:
                app_id = f"{base_id}-{n}"
                n += 1
            seen_ids.add(app_id)

            rows.append({
                "app_id": app_id,
                "app": row["app"],
                "category": row.get("category", "").strip() or "UNCATEGORIZED",
                "website_hint": row.get("website_hint", "").strip(),
                "row_index": i,
            })
        return rows


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "data/input/apps.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "data/output/normalized_apps.json"

    apps = load_apps_csv(in_path)

    categories = sorted(set(a["category"] for a in apps))
    print(f"Loaded {len(apps)} apps across {len(categories)} categories:")
    for c in categories:
        count = sum(1 for a in apps if a["category"] == c)
        print(f"  {c}: {count}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(apps, f, indent=2)
    print(f"\nWrote normalized apps -> {out_path}")


if __name__ == "__main__":
    main()
