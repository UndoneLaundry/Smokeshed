"""Fetch this year's VIIRS hotspots (worldwide) from the FIRMS API.

Run:  python -m pipeline.fetch_recent
Needs: FIRMS_MAP_KEY in .env (see docs/API_SETUP.md)

Why this script exists: FIRMS yearly files only exist for finished years, so
2026 has to come from the API, which gives at most 5 days per request.
  - Archive data (VIIRS_SNPP_SP) is final: each 5-day chunk is cached and
    never downloaded twice.
  - Near-real-time data (VIIRS_SNPP_NRT) covers roughly the last 3 months and
    is re-downloaded on every run, so rerunning before submission refreshes
    the "last few days".

Near-real-time rows have no `type` column, so they can't say "this is a gas
flare, not a fire". Gas flares and volcanoes don't move, so we remember where
the archive months saw them (to ~1 km) and drop near-real-time hotspots there.

Output: data/raw/firms/recent/daily_<year>.json = {date: {"lat,lon": count}}
(1-degree cells, same filters as pipeline.build_calendar).

The MAP_KEY is never printed; error messages are redacted.
"""

from __future__ import annotations

import csv
import io
import json
import math
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from pipeline.config import REPO_ROOT, get_firms_map_key

API = "https://firms.modaps.eosdis.nasa.gov/api"
ARCHIVE, NRT = "VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"
CHUNK_DAYS = 5  # the API maximum
RECENT_DIR = REPO_ROOT / "data" / "raw" / "firms" / "recent"


QUOTA_WAIT_S = 600  # the MAP_KEY allows 5000 "transactions" per 10 minutes
MAX_TRIES = 8


def get_text(url: str, key: str) -> str:
    """GET a FIRMS URL; never let the key reach the screen.

    A worldwide request costs many transactions, so we hit the quota after
    ~25 requests. FIRMS then answers HTTP 400 "Exceeding allowed transaction
    limit": we just wait for the 10-minute window to reset and try again.
    """
    for attempt in range(1, MAX_TRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            if "transaction limit" not in body.lower() or attempt == MAX_TRIES:
                raise RuntimeError(f"HTTP {err.code}: {body[:200]}".replace(key, "***")) from None
            print("  FIRMS quota used up: waiting 10 minutes for it to reset...", flush=True)
            time.sleep(QUOTA_WAIT_S)
        except Exception as err:  # timeouts etc.: one quick retry
            if attempt >= 2:
                raise RuntimeError(str(err).replace(key, "***")) from None
    raise AssertionError("unreachable")


def availability(key: str) -> dict[str, tuple[date, date]]:
    text = get_text(f"{API}/data_availability/csv/{key}/all", key)
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        out[row["data_id"]] = (date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"]))
    return out


def fetch_rows(key: str, source: str, start: date, days: int) -> list[dict[str, str]]:
    text = get_text(f"{API}/area/csv/{key}/{source}/world/{days}/{start}", key)
    # FIRMS can answer "200 OK" with a plain-text error, so check it's a CSV.
    if not text.lstrip().lower().startswith("latitude"):
        raise RuntimeError(f"{source} {start}: not a CSV: {text[:200].replace(key, '***')}")
    return list(csv.DictReader(io.StringIO(text)))


def spot(row: dict[str, str]) -> tuple[int, int]:
    """Location rounded to 0.01 degree (~1 km): fine enough to pin a gas flare."""
    return round(float(row["latitude"]) * 100), round(float(row["longitude"]) * 100)


def near_static(row: dict[str, str], static: set[tuple[int, int]]) -> bool:
    la, lo = spot(row)
    # Check the 8 neighbours too, in case a detection lands just over a boundary.
    return any((la + dy, lo + dx) in static for dy in (-1, 0, 1) for dx in (-1, 0, 1))


def add_count(daily: dict, row: dict[str, str]) -> None:
    cell = f"{math.floor(float(row['latitude']))},{math.floor(float(row['longitude']))}"
    day = daily.setdefault(row["acq_date"], {})
    day[cell] = day.get(cell, 0) + 1


def chunks(first: date, last: date):
    start = first
    while start <= last:
        days = min(CHUNK_DAYS, (last - start).days + 1)
        yield start, days
        start += timedelta(days=days)


def archive_chunk(key: str, start: date, days: int) -> dict:
    """Archive data is final, so cache each chunk on disk."""
    cache = RECENT_DIR / f"{ARCHIVE}_{start}_{days}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    daily: dict = {}
    static: set = set()
    for row in fetch_rows(key, ARCHIVE, start, days):
        if row["type"] != "0":
            static.add(spot(row))
        elif row["confidence"] != "l":
            add_count(daily, row)
    result = {"daily": daily, "static": sorted(static)}
    cache.write_text(json.dumps(result))
    print(f"archive  {start} (+{days}d)", flush=True)
    return result


STATIC_JSON = REPO_ROOT / "data" / "processed" / "static_sources.json"


def save_static_spots(static: set[tuple[int, int]]) -> None:
    """Save known gas flare / volcano spots so the daily GitHub Action (which has
    no raw data cache) can filter them out of near-real-time data too."""
    STATIC_JSON.write_text(json.dumps(sorted(static), separators=(",", ":")))


def load_static_spots() -> set[tuple[int, int]]:
    return {tuple(s) for s in json.loads(STATIC_JSON.read_text())}


def main() -> None:
    key = get_firms_map_key()
    RECENT_DIR.mkdir(parents=True, exist_ok=True)
    avail = availability(key)
    year_start = date(date.today().year, 1, 1)
    archive_end = avail[ARCHIVE][1]
    nrt_end = avail[NRT][1]

    daily: dict = {}
    static: set[tuple[int, int]] = set()
    for start, days in chunks(year_start, archive_end):
        part = archive_chunk(key, start, days)
        daily.update(part["daily"])
        static.update(tuple(s) for s in part["static"])

    dropped = 0
    for start, days in chunks(archive_end + timedelta(days=1), nrt_end):
        for row in fetch_rows(key, NRT, start, days):
            if row["confidence"] == "l":
                continue
            if near_static(row, static):
                dropped += 1
                continue
            add_count(daily, row)
        print(f"near-real-time  {start} (+{days}d)", flush=True)

    save_static_spots(static)
    out = RECENT_DIR / f"daily_{year_start.year}.json"
    out.write_text(json.dumps({"through": str(nrt_end), "daily": daily}))
    total = sum(sum(cells.values()) for cells in daily.values())
    print(
        f"\n{total:,} fire hotspots from {year_start} to {nrt_end} saved to {out.name}. "
        f"Dropped {dropped:,} near-real-time detections at known gas flares/volcanoes."
    )


if __name__ == "__main__":
    main()
