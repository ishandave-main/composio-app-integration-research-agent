"""
run_pipeline.py -- Orchestrator for the deterministic half of the pipeline.

Everything upstream of this script (web research, extraction into a raw
per-app JSON record matching schema.ResearchRecord) is done by the agent
stage and saved to research/<version>/<app_id>.json. Everything in this
script is pure, deterministic Python with no network/model calls -- so it
can be re-run any number of times on the same raw research to re-validate,
re-score confidence, and re-export, without re-doing any research.

Usage:
    python -m pipeline.run_pipeline --raw-dir research/v1_raw --out data/output/v1

This will write:
    data/output/v1/final_dataset.csv
    data/output/v1/final_dataset.json
    data/output/v1/validation_log.json   (every correction/flag applied, per app)
"""

from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from datetime import date

from .schema import ResearchRecord, CSV_COLUMNS, record_to_csv_row
from .validate import validate_record
from .confidence import assess_confidence
from .review_routing import route_for_review


def run(raw_dir: str, out_dir: str, pipeline_version: str = "v1") -> None:
    raw_path = Path(raw_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(raw_path.glob("*.json"))
    if not raw_files:
        raise SystemExit(f"No raw research JSON files found in {raw_dir}")

    records: list[ResearchRecord] = []
    validation_log = []

    for fp in raw_files:
        with fp.open() as f:
            raw = json.load(f)
        r = ResearchRecord.from_dict(raw)
        r.pipeline_version = pipeline_version
        if not r.research_date:
            r.research_date = date.today().isoformat()

        result = validate_record(r)
        assess_confidence(r)
        route_for_review(r)

        records.append(r)
        validation_log.append({
            "app": r.app,
            "app_id": fp.stem,
            "flags": result.flags,
            "corrections": result.corrections,
        })

    # --- Write CSV -----------------------------------------------------
    csv_path = out_path / "final_dataset.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in records:
            writer.writerow(record_to_csv_row(r))

    # --- Write JSON (full fidelity, incl. structured evidence) ---------
    json_path = out_path / "final_dataset.json"
    with json_path.open("w") as f:
        json.dump([r.to_dict() for r in records], f, indent=2)

    # --- Write validation log -------------------------------------------
    log_path = out_path / "validation_log.json"
    with log_path.open("w") as f:
        json.dump(validation_log, f, indent=2)

    n_review = sum(1 for r in records if r.needs_human_review)
    n_corrections = sum(len(v["corrections"]) for v in validation_log)
    print(f"Processed {len(records)} apps.")
    print(f"  -> {csv_path}")
    print(f"  -> {json_path}")
    print(f"  -> {log_path}")
    print(f"Flagged for human review: {n_review}/{len(records)}")
    print(f"Auto-corrections applied: {n_corrections}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="research/v1_raw")
    ap.add_argument("--out", default="data/output/v1")
    ap.add_argument("--version", default="v1")
    args = ap.parse_args()
    run(args.raw_dir, args.out, args.version)


if __name__ == "__main__":
    main()
