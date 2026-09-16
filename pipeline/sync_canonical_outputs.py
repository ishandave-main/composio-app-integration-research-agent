"""
Copies the versioned V2 pipeline output (data/output/v2/) to the canonical,
version-agnostic output location (data/output/) that a reviewer would look
for first. V2 is the only research version in this repository -- this is a
plain copy, not a merge across versions.

Run: python3 -m pipeline.sync_canonical_outputs
"""
import shutil
import os

FILES = ["final_dataset.csv", "final_dataset.json", "patterns.json"]
SRC_DIR = "data/output/v2"
DST_DIR = "data/output"


def main():
    os.makedirs(DST_DIR, exist_ok=True)
    for fname in FILES:
        src = os.path.join(SRC_DIR, fname)
        dst = os.path.join(DST_DIR, fname)
        shutil.copyfile(src, dst)
        print(f"Copied {src} -> {dst}")

    # Also refresh the deployable copy of the case study
    shutil.copyfile("case_study/index.html", "site/index.html")
    print("Copied case_study/index.html -> site/index.html")


if __name__ == "__main__":
    main()
