"""Fetch the last 7 days of fire hotspots worldwide -> data/processed/now.json

Run:  python -m pipeline.build_now
Needs: FIRMS_MAP_KEY (in .env locally; a GitHub Secret in the daily Action)

This is the "right now" data behind the page's status (Quiet / Normal /
Above normal / Surge) and the fire dots on the map. A GitHub Action runs it
every day (.github/workflows/site.yml), so the site stays current without
anyone touching it. The 25-year calendar doesn't need daily updates.

Which satellite: all VIIRS instruments (on S-NPP, NOAA-20, NOAA-21) are
identical, so we use whichever near-real-time feed is freshest, preferring
S-NPP to match the calendar. (S-NPP's feed stopped on 2 Nov 2026.)

Uses the same filters as the calendar: drops "low" confidence detections and
known gas flares / volcanoes (data/processed/static_sources.json).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from pipeline.config import REPO_ROOT, get_firms_map_key
from pipeline.fetch_recent import availability, chunks, fetch_rows, load_static_spots, near_static

DAYS = 7
POINT_DEG = 0.25  # map dots: fires grouped into ~28 km squares (keeps the file small)
SOURCES = {  # in order of preference
    "VIIRS_SNPP_NRT": "VIIRS S-NPP",
    "VIIRS_NOAA20_NRT": "VIIRS NOAA-20",
    "VIIRS_NOAA21_NRT": "VIIRS NOAA-21",
}
OUT = REPO_ROOT / "data" / "processed" / "now.json"


def pick_source(avail: dict) -> str:
    """The preferred feed, unless it's more than a day behind the freshest one."""
    freshest = max(avail[s][1] for s in SOURCES if s in avail)
    return next(s for s in SOURCES if s in avail and avail[s][1] >= freshest - timedelta(days=1))


def main() -> None:
    key = get_firms_map_key()
    avail = availability(key)
    source = pick_source(avail)
    # Stop at yesterday: today is only partly observed and would look "quiet".
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    end = min(avail[source][1], yesterday)
    start = end - timedelta(days=DAYS - 1)
    days = [str(start + timedelta(days=i)) for i in range(DAYS)]
    static = load_static_spots()

    cells: dict[str, list[int]] = {}   # 1-degree cells: daily counts, for the status numbers
    spots: dict[tuple, list] = {}      # 0.25-degree cells: [sum lat, sum lon, count, last day], for map dots
    for chunk_start, n in chunks(start, end):
        for row in fetch_rows(key, source, chunk_start, n):
            if row["confidence"] == "l" or near_static(row, static):
                continue
            if row["acq_date"] not in days:
                continue
            la, lo = float(row["latitude"]), float(row["longitude"])
            day = days.index(row["acq_date"])
            counts = cells.setdefault(f"{int(la // 1)},{int(lo // 1)}", [0] * DAYS)
            counts[day] += 1
            s = spots.setdefault((int(la // POINT_DEG), int(lo // POINT_DEG)), [0.0, 0.0, 0, 0])
            s[0] += la; s[1] += lo; s[2] += 1; s[3] = max(s[3], day)

    # Each map dot sits at the average position of the real fires in its ~28 km
    # square, so dots follow the actual fire pattern instead of a fixed grid.
    # The 4th number is the last day (0-6) a fire was seen there: the page fades
    # dots that haven't burned in the last 2 days.
    points = [[round(sla / n, 2), round(slo / n, 2), n, last] for sla, slo, n, last in spots.values()]

    OUT.write_text(json.dumps({
        "through": str(end),
        "days": days,
        "source": f"{SOURCES[source]} (near real time)",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cells": cells,
        "points": points,  # [lat, lon, fires in last 7 days, last day seen (index into days)]
    }, separators=(",", ":")))
    total = sum(sum(c) for c in cells.values())
    print(f"{total:,} fire hotspots worldwide, {days[0]} to {days[-1]} ({SOURCES[source]}), "
          f"in {len(cells):,} grid cells -> {OUT.relative_to(REPO_ROOT)} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
