"""Build the worldwide harmonized burning calendar (2001-2025, monthly).

Run:  python -m pipeline.build_calendar
Needs: python -m pipeline.download_firms  (run first)

How the harmonization works (plain words):
  1. Count hotspots per month in every 1-degree grid square (~110 km).
  2. MODIS and VIIRS see fires differently: VIIRS has sharper eyes and finds
     more of them. While both flew (2013-2014) we compare their counts in
     each 10-degree "region" and get one ratio: VIIRS count / MODIS count.
  3. History 2001-2012 = MODIS count x that ratio  ("VIIRS-equivalent").
     2013 onward       = real VIIRS counts.
  So the whole calendar is in one unit and years can be compared fairly.

Which hotspots count:
  - type 0 only (vegetation fires; skips volcanoes, gas flares, factories)
  - MODIS: Terra only, confidence >= 30 (Aqua only started mid-2002, so
    mixing it in would make 2001-02 look artificially quiet)
  - VIIRS S-NPP: confidence "nominal" or "high" (drops "low")

Output (small JSON files the web page loads):
  data/processed/calendar/meta.json            months, ratios, units
  data/processed/calendar/tile_<lat>_<lon>.json   one per 10-degree region
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from pipeline.config import REPO_ROOT
from pipeline.download_firms import MODIS_YEARS, OUT_DIR as RAW_DIR, VIIRS_YEARS

CACHE_DIR = REPO_ROOT / "data" / "raw" / "firms" / "agg"  # per-file counts
RECENT_DIR = REPO_ROOT / "data" / "raw" / "firms" / "recent"  # from fetch_recent
OUT_DIR = REPO_ROOT / "data" / "processed" / "calendar"

FIRST_YEAR = 2001
LAST_YEAR = 2025
SWITCH_YEAR = 2013            # first year we use real VIIRS
OVERLAP_YEARS = (2013, 2014)  # both sensors stable: used for the ratio
TILE = 10                     # region size in degrees
MIN_MODIS_FOR_RATIO = 200     # fewer MODIS hotspots than this -> use global ratio


# ---------- Step 1: count hotspots per 1-degree cell per month, per file ----------

def keep_row(row: list[str], col: dict[str, int], sensor: str) -> bool:
    if row[col["type"]] != "0":
        return False
    conf = row[col["confidence"]]
    if sensor == "modis":
        return row[col["satellite"]].startswith("T") and int(conf) >= 30
    return conf != "l"


def count_file(zip_name: str) -> dict[str, list[int]]:
    """Return {"lat,lon": [12 monthly counts]} for one yearly zip file."""
    sensor = "modis" if zip_name.startswith("modis") else "viirs"
    counts: dict[str, list[int]] = {}
    with zipfile.ZipFile(RAW_DIR / zip_name) as z:
        for member in z.namelist():
            if not member.endswith(".csv"):
                continue
            with z.open(member) as raw:
                reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8"))
                header = next(reader, None)
                if header is None:
                    continue
                col = {name: i for i, name in enumerate(header)}
                for row in reader:
                    if not keep_row(row, col, sensor):
                        continue
                    lat = math.floor(float(row[col["latitude"]]))
                    lon = math.floor(float(row[col["longitude"]]))
                    month = int(row[col["acq_date"]][5:7])
                    key = f"{lat},{lon}"
                    if key not in counts:
                        counts[key] = [0] * 12
                    counts[key][month - 1] += 1
    return counts


def cached_count(zip_name: str) -> dict[str, list[int]]:
    """Counting a file takes minutes, so keep the result for reruns."""
    cache = CACHE_DIR / zip_name.replace(".zip", ".json")
    if cache.exists():
        return json.loads(cache.read_text())
    counts = count_file(zip_name)
    cache.write_text(json.dumps(counts))
    print(f"counted {zip_name}", flush=True)
    return counts


# ---------- Step 2: one MODIS->VIIRS ratio per 10-degree region ----------

def tile_of(cell: str) -> str:
    lat, lon = (int(v) for v in cell.split(","))
    return f"{lat // TILE * TILE}_{lon // TILE * TILE}"


def totals_by_tile(yearly: dict[str, list[int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for cell, months in yearly.items():
        t = tile_of(cell)
        out[t] = out.get(t, 0) + sum(months)
    return out


def compute_ratios(modis: dict[int, dict], viirs: dict[int, dict], years) -> tuple[dict[str, float], float]:
    m_tot: dict[str, int] = {}
    v_tot: dict[str, int] = {}
    for y in years:
        for t, n in totals_by_tile(modis[y]).items():
            m_tot[t] = m_tot.get(t, 0) + n
        for t, n in totals_by_tile(viirs[y]).items():
            v_tot[t] = v_tot.get(t, 0) + n
    global_ratio = sum(v_tot.values()) / sum(m_tot.values())
    ratios = {
        t: v_tot.get(t, 0) / m
        for t, m in m_tot.items()
        if m >= MIN_MODIS_FOR_RATIO
    }
    return ratios, global_ratio


def check_ratio(modis: dict, viirs: dict) -> str:
    """Honest test: learn ratios from 2013 only, predict 2014 VIIRS from 2014 MODIS."""
    ratios, global_ratio = compute_ratios(modis, viirs, [2013])
    pred = {t: n * ratios.get(t, global_ratio) for t, n in totals_by_tile(modis[2014]).items()}
    actual = totals_by_tile(viirs[2014])
    # Only judge regions with real fire activity, otherwise tiny numbers dominate.
    errors = sorted(
        abs(pred[t] - actual.get(t, 0)) / actual[t]
        for t in pred
        if actual.get(t, 0) >= 1000
    )
    median = errors[len(errors) // 2]
    return (
        f"Check: ratios learned from 2013 predicted 2014 VIIRS totals within "
        f"{median:.0%} (median error) across {len(errors)} fire-active regions."
    )


# ---------- Step 3: stitch the calendar and write JSON ----------

def load_recent() -> tuple[str | None, dict[str, list[int]]]:
    """This year's monthly counts from pipeline.fetch_recent (if it was run)."""
    path = RECENT_DIR / f"daily_{LAST_YEAR + 1}.json"
    if not path.exists():
        print("No 2026 data yet (run python -m pipeline.fetch_recent); calendar ends 2025.")
        return None, {}
    data = json.loads(path.read_text())
    n_months = int(data["through"][5:7])
    monthly: dict[str, list[int]] = {}
    for day, cells in data["daily"].items():
        m = int(day[5:7]) - 1
        for cell, n in cells.items():
            monthly.setdefault(cell, [0] * n_months)[m] += n
    return data["through"], monthly


def build() -> None:
    names = [f"modis_{y}_all_countries.zip" for y in MODIS_YEARS]
    names += [f"viirs-snpp_{y}_all_countries.zip" for y in VIIRS_YEARS]
    missing = [n for n in names if not (RAW_DIR / n).exists()]
    if missing:
        raise SystemExit(
            f"{len(missing)} file(s) missing, e.g. {missing[0]}. "
            "Run: python -m pipeline.download_firms"
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Counting hotspots in {len(names)} yearly files (first run: ~10-20 min)...")
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = dict(zip(names, pool.map(cached_count, names)))
    modis = {y: results[f"modis_{y}_all_countries.zip"] for y in MODIS_YEARS}
    viirs = {y: results[f"viirs-snpp_{y}_all_countries.zip"] for y in VIIRS_YEARS}

    ratios, global_ratio = compute_ratios(modis, viirs, OVERLAP_YEARS)
    check_sentence = check_ratio(modis, viirs)

    through, recent = load_recent()
    n_history = (LAST_YEAR - FIRST_YEAR + 1) * 12
    n_months = n_history + (int(through[5:7]) if through else 0)
    calendar: dict[str, list[int]] = {}  # "lat,lon" -> monthly counts
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        use_viirs = year >= SWITCH_YEAR
        source = viirs[year] if use_viirs else modis[year]
        offset = (year - FIRST_YEAR) * 12
        for cell, months in source.items():
            factor = 1.0 if use_viirs else ratios.get(tile_of(cell), global_ratio)
            row = calendar.setdefault(cell, [0] * n_months)
            for i, n in enumerate(months):
                row[offset + i] = round(n * factor)

    for cell, months in recent.items():  # 2026 is real VIIRS: no ratio needed
        row = calendar.setdefault(cell, [0] * n_months)
        row[n_history:n_history + len(months)] = months

    # One file per 10-degree region, so the page only loads what it needs.
    tiles: dict[str, dict[str, list[int]]] = {}
    for cell, row in calendar.items():
        if any(row):
            tiles.setdefault(tile_of(cell), {})[cell] = row

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("tile_*.json"):
        old.unlink()
    for t, cells in tiles.items():
        (OUT_DIR / f"tile_{t}.json").write_text(json.dumps({"cells": cells}, separators=(",", ":")))

    meta = {
        "first_month": f"{FIRST_YEAR}-01",
        "n_months": n_months,
        "data_through": through or f"{LAST_YEAR}-12-31",  # last month may be partial
        "cell_degrees": 1,
        "tile_degrees": TILE,
        "units": "VIIRS-equivalent hotspots per month",
        "switch_year": SWITCH_YEAR,
        "overlap_years": list(OVERLAP_YEARS),
        "global_ratio": round(global_ratio, 3),
        "tile_ratios": {t: round(r, 3) for t, r in sorted(ratios.items())},
        "ratio_check": check_sentence,
        "built": date.today().isoformat(),
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=1))

    size_mb = sum(p.stat().st_size for p in OUT_DIR.glob("*.json")) / 1e6
    print(f"\nWrote {len(tiles)} region files ({size_mb:.1f} MB) to {OUT_DIR}")
    print(
        f"Worldwide, VIIRS sees {global_ratio:.1f}x as many hotspots as MODIS Terra; "
        f"{len(ratios)} regions got their own ratio, the rest use the worldwide one."
    )
    print(check_sentence)


if __name__ == "__main__":
    build()
