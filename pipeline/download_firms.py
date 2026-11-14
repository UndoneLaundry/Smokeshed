"""Download the worldwide FIRMS yearly hotspot files (no API key needed).

Run:  python -m pipeline.download_firms

FIRMS publishes one zip per sensor per year containing every country's
hotspots. We need:
  - MODIS 2001-2014: the long history, plus 2013-2014 to compare with VIIRS
  - VIIRS S-NPP 2013-2025: the better sensor, used directly from 2013 on

Why 2013-2014 for the comparison: MODIS orbits drift in recent years, which
changes its counts. Comparing the sensors while both were stable gives a
fairer MODIS->VIIRS ratio.

Files are saved zipped in data/raw/firms/global/ (gitignored, ~5 GB).
Files that already exist are skipped, so it is safe to rerun after a failure.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

from pipeline.config import REPO_ROOT

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/data/country/zips"
OUT_DIR = REPO_ROOT / "data" / "raw" / "firms" / "global"

MODIS_YEARS = range(2001, 2015)  # 2001-2014
VIIRS_YEARS = range(2013, 2026)  # 2013-2025


def wanted_files() -> list[str]:
    names = [f"modis_{y}_all_countries.zip" for y in MODIS_YEARS]
    names += [f"viirs-snpp_{y}_all_countries.zip" for y in VIIRS_YEARS]
    return names


def looks_like_zip(path: Path) -> bool:
    # FIRMS can answer HTTP 200 with a plain-text error, so check the bytes.
    # Every zip file starts with the two letters "PK".
    with path.open("rb") as f:
        return f.read(2) == b"PK"


def download(name: str) -> None:
    target = OUT_DIR / name
    if target.exists() and looks_like_zip(target):
        print(f"skip  {name} (already downloaded)")
        return

    partial = target.with_suffix(".part")
    print(f"get   {name} ...", flush=True)
    urllib.request.urlretrieve(f"{BASE_URL}/{name}", partial)

    if not looks_like_zip(partial):
        partial.unlink()
        raise RuntimeError(f"{name}: FIRMS did not return a zip file")

    # Only rename when complete, so a half-finished file is never mistaken
    # for a good one on the next run.
    partial.replace(target)
    size_mb = target.stat().st_size / 1e6
    print(f"done  {name} ({size_mb:.0f} MB)", flush=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for name in wanted_files():
        try:
            download(name)
        except Exception as err:  # keep going; report at the end
            print(f"FAIL  {name}: {err}", flush=True)
            failed.append(name)

    if failed:
        print(f"\n{len(failed)} file(s) failed. Rerun the same command to retry.")
        sys.exit(1)
    print(f"\nAll {len(wanted_files())} files are in {OUT_DIR}")


if __name__ == "__main__":
    main()
