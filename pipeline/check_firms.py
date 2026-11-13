"""Quick connectivity check for the NASA FIRMS area API.

Fetches VIIRS_SNPP_NRT hotspots for a small box over Sumatra for the last day
and prints only the HTTP status, the row count and the first 3 rows.

The MAP_KEY is loaded via pipeline.config and is never printed: the request
URL (which embeds the key) is never shown, and any error text is redacted.

Run from the repo root:
    python -m pipeline.check_firms
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.error
import urllib.request

from pipeline.config import MissingAPIKeyError, get_firms_map_key

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCE = "VIIRS_SNPP_NRT"
AREA = "95,-11,141,6"  # covers all of Indonesia, including Kalimantan.
DAY_RANGE = 5
TIMEOUT_S = 60
MAX_ERROR_CHARS = 500


def _redact(text: str, key: str) -> str:
    return text.replace(key, "***REDACTED***") if key else text


def main() -> int:
    try:
        key = get_firms_map_key()
    except MissingAPIKeyError as exc:
        print(f"Config error: {exc}")
        return 1

    url = f"{BASE_URL}/{key}/{SOURCE}/{AREA}/{DAY_RANGE}"
    req = urllib.request.Request(url, headers={"User-Agent": "smokeshed-check/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP status: {exc.code}")
        print(f"Error: {_redact(err_body.strip()[:MAX_ERROR_CHARS], key)}")
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print("HTTP status: (no response)")
        print(f"Error: {_redact(str(exc), key)}")
        return 1

    print(f"HTTP status: {status}")

    # FIRMS sometimes returns 200 with a plain-text error (e.g. "Invalid MAP_KEY.").
    first_line = body.lstrip().splitlines()[0] if body.strip() else ""
    if not first_line.lower().startswith("latitude"):
        print(f"Error: {_redact(body.strip()[:MAX_ERROR_CHARS], key) or '(empty response)'}")
        return 1

    rows = list(csv.DictReader(io.StringIO(body)))
    print(f"Hotspot rows: {len(rows)}")
    for i, row in enumerate(rows[:3], start=1):
        print(f"Row {i}: {_redact(str(dict(row)), key)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
