"""Feasibility test: do fire surges in Sumatra/Kalimantan come before haze in Singapore?

Run:  python -m pipeline.feasibility
Needs: python -m pipeline.fetch_recent   (2026 daily hotspots)

What it does (plain words):
  1. Daily fire hotspots in two fixed boxes: Sumatra and Kalimantan (2026).
  2. Daily Singapore PM2.5 (island average) from data.gov.sg, for the same days.
  3. For delays of 0-7 days, how closely does "fires N days ago" track
     "today's PM2.5"? (Pearson correlation r: 1 = moves perfectly together.)
  4. Prints one sentence with the best delay and how strong the link is,
     and saves one chart: docs/feasibility.png

It also writes data/processed/smokeshed.json, which the web page reads.
Fallback rule (CLAUDE.md): even if the link is weak, the fixed boxes are used
as the smokeshed; the sentence just says so honestly.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from statistics import correlation, mean

import matplotlib

matplotlib.use("Agg")  # draw straight to a file, no window
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from pipeline.config import REPO_ROOT, get_datagovsg_api_key  # noqa: E402
from pipeline.fetch_recent import RECENT_DIR  # noqa: E402

START = date(2026, 6, 1)  # dry season starts; haze season is Jun-Oct
MAX_LAG_DAYS = 7
PM25_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25?date={day}"
PM25_CACHE = REPO_ROOT / "data" / "raw" / "pm25" / "singapore_daily_2026.json"
CHART = REPO_ROOT / "docs" / "feasibility.png"
SMOKESHED_JSON = REPO_ROOT / "data" / "processed" / "smokeshed.json"

# Fixed smokeshed boxes, in whole degrees (south, west, north, east).
# The Sumatra box also catches the southern Malay Peninsula; that's fine,
# its fires drift toward Singapore too.
REGIONS = {
    "Sumatra": (-6, 95, 6, 106),
    "Kalimantan": (-5, 108, 5, 119),
}
SINGAPORE = (1.352, 103.82)


# ---------- data ----------

def in_box(cell: str, box: tuple[int, int, int, int]) -> bool:
    lat, lon = (int(v) for v in cell.split(","))  # south-west corner of the cell
    south, west, north, east = box
    return south <= lat < north and west <= lon < east


def daily_hotspots() -> tuple[dict[str, dict[date, int]], date]:
    path = RECENT_DIR / "daily_2026.json"
    if not path.exists():
        raise SystemExit("No 2026 hotspot data. Run: python -m pipeline.fetch_recent")
    data = json.loads(path.read_text())
    through = date.fromisoformat(data["through"])
    out = {name: {} for name in REGIONS}
    for day_str, cells in data["daily"].items():
        day = date.fromisoformat(day_str)
        for name, box in REGIONS.items():
            out[name][day] = sum(n for c, n in cells.items() if in_box(c, box))
    return out, through


def fetch_pm25_day(day: date) -> float | None:
    """Island-average PM2.5 for one day (mean of all hourly readings, 5 regions)."""
    req = urllib.request.Request(PM25_URL.format(day=day), headers={"User-Agent": "smokeshed"})
    key = get_datagovsg_api_key()
    if key:
        req.add_header("x-api-key", key)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                items = json.load(resp)["data"]["items"]
            values = [v for item in items for v in item["readings"]["pm25_one_hourly"].values()]
            return mean(values) if values else None  # a day with no readings is missing, not zero
        except urllib.error.HTTPError as err:
            if err.code != 429:  # 429 = "slow down": wait and retry
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"data.gov.sg kept rate-limiting us on {day}")


def daily_pm25(days: list[date]) -> dict[date, float]:
    cache = json.loads(PM25_CACHE.read_text()) if PM25_CACHE.exists() else {}
    missing = [d for d in days if str(d) not in cache]
    if missing:
        print(f"Downloading Singapore PM2.5 for {len(missing)} days...", flush=True)
    for i, day in enumerate(missing, 1):
        cache[str(day)] = fetch_pm25_day(day)
        if i % 20 == 0 or i == len(missing):
            PM25_CACHE.parent.mkdir(parents=True, exist_ok=True)
            PM25_CACHE.write_text(json.dumps(cache, indent=0))
        time.sleep(0.3)  # be polite to the free API
    return {d: cache[str(d)] for d in days if cache.get(str(d)) is not None}


# ---------- analysis ----------

def best_lag(fires: dict[date, int], pm25: dict[date, float]) -> tuple[int, float]:
    """Delay (days) at which past fires best match today's PM2.5."""
    results = []
    for lag in range(MAX_LAG_DAYS + 1):
        pairs = [(fires[d - timedelta(days=lag)], v) for d, v in pm25.items()
                 if d - timedelta(days=lag) in fires]
        results.append((correlation([p[0] for p in pairs], [p[1] for p in pairs]), lag))
    r, lag = max(results)
    return lag, r


def strength_words(r: float) -> str:
    if r >= 0.7:
        return "strong"
    if r >= 0.5:
        return "moderate"
    if r >= 0.3:
        return "weak"
    return "very weak"


# ---------- chart ----------

INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
AIR = "#2a78d6"  # categorical slot 1 (blue)
# Slots 2 and 3 (orange, aqua): each region keeps its colour everywhere.
REGION_COLORS = {"Sumatra": "#eb6834", "Kalimantan": "#1baf7a"}


def draw_chart(days, fires, pm25, title, subtitle) -> None:
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, dpi=150)
    fig.patch.set_facecolor("#fcfcfb")

    for name, color in REGION_COLORS.items():
        values = [fires[name].get(d, 0) for d in days]
        top.plot(days, values, color=color, linewidth=2, label=name)
    top.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
    top.set_title("Fire hotspots per day (VIIRS)", loc="left", fontsize=10, color=INK_2)

    pm_days = [d for d in days if d in pm25]
    bottom.plot(pm_days, [pm25[d] for d in pm_days], color=AIR, linewidth=2)
    bottom.axhline(15, color=INK_2, linewidth=1, linestyle=(0, (4, 3)))
    # Label the guideline in the right margin, so it never sits on the data.
    bottom.text(1.01, 15, "WHO 24-h\nguideline", transform=bottom.get_yaxis_transform(),
                fontsize=8, color=INK_2, va="center")
    bottom.set_title("Singapore PM2.5 per day, island average (µg/m³)", loc="left",
                     fontsize=10, color=INK_2)

    peak = max(pm_days, key=lambda d: pm25[d])  # label only the worst day
    bottom.annotate(f"{peak:%d %b}: {pm25[peak]:.0f}", (peak, pm25[peak]),
                    xytext=(8, -4), textcoords="offset points", fontsize=8, color=INK)

    for ax in (top, bottom):
        ax.set_facecolor("#fcfcfb")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK_2, labelsize=8, length=0)
        ax.set_ylim(bottom=0)
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    bottom.xaxis.set_major_locator(mdates.MonthLocator())

    fig.suptitle(title, x=0.01, y=0.985, ha="left", fontsize=13, color=INK, fontweight="bold")
    fig.text(0.01, 0.925, subtitle, fontsize=9, color=INK_2)
    # Space Apps rule: AI-assisted images carry a visible note.
    fig.text(0.99, 0.01, "Chart code written with AI assistance (Claude)", ha="right", fontsize=7, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 0.93, 0.93))
    CHART.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART, facecolor=fig.get_facecolor())


# ---------- main ----------

def main() -> None:
    fires, through = daily_hotspots()
    days = [START + timedelta(days=i) for i in range((through - START).days + 1)]
    pm25 = daily_pm25(days)
    total = {d: sum(fires[name].get(d, 0) for name in REGIONS) for d in days}

    lag, r = best_lag(total, pm25)  # both regions together, for the record
    per_region = {name: best_lag({d: fires[name].get(d, 0) for d in days}, pm25) for name in REGIONS}
    # Lead with the region whose fires track Singapore's air best: adding a
    # weaker region to the total only blurs the signal.
    leader = max(per_region, key=lambda n: per_region[n][1])
    lead_lag, lead_r = per_region[leader]
    words = strength_words(lead_r)
    others = "; ".join(
        f"{n}: {strength_words(rr)} link (r = {rr:.2f}, ~{lg} days)"
        for n, (lg, rr) in per_region.items() if n != leader
    )

    sentence = (
        f"{START:%b} to {through:%b %Y}: when fires surged in {leader}, Singapore's air got worse "
        f"about {lead_lag} day{'s' if lead_lag != 1 else ''} later ({words} link, r = {lead_r:.2f}). "
        f"{others}."
    )
    if words in ("weak", "very weak"):
        sentence += " (Weak link: the app still uses the fixed Sumatra + Kalimantan boxes as the smokeshed.)"

    draw_chart(days, fires, pm25,
               title="Fires first, haze after: Singapore, 2026",
               subtitle=f"{leader} fires best match Singapore's air {lead_lag} day(s) later "
                        f"({words} link, r = {lead_r:.2f})")

    SMOKESHED_JSON.parent.mkdir(parents=True, exist_ok=True)
    SMOKESHED_JSON.write_text(json.dumps({
        "city": "Singapore",
        "lat": SINGAPORE[0], "lon": SINGAPORE[1],
        "regions": [
            {"name": n, "box_swne": [b[0], b[1], b[2], b[3]],
             "lag_days": per_region[n][0], "r": round(per_region[n][1], 2)}
            for n, b in REGIONS.items()
        ],
        "lead_region": leader, "lag_days": lead_lag, "r": round(lead_r, 2), "strength": words,
        "combined": {"lag_days": lag, "r": round(r, 2)},
        "period": [str(START), str(through)],
        "sentence": sentence,
    }, indent=1))

    for name, (lg, rr) in per_region.items():
        print(f"  {name}: best delay {lg} day(s), r = {rr:.2f}")
    print(f"\nChart saved to {CHART.relative_to(REPO_ROOT)}")
    print(sentence)


if __name__ == "__main__":
    main()
