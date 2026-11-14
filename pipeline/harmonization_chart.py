"""Draw the "does harmonization work?" chart: docs/harmonization.png

Run:  python -m pipeline.harmonization_chart
Needs: python -m pipeline.build_calendar  (uses its cached counts + meta.json)

For two very different regions it plots, month by month in 2013-2014 (when
both satellites flew):
  - MODIS Terra as measured        (grey)   -> far below VIIRS
  - VIIRS as measured              (blue)
  - MODIS after harmonization      (orange) -> should sit on top of VIIRS
Two regions, because the ratio differs a lot between them: that's why we use
one ratio per region, not one for the whole world.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pipeline.build_calendar import CACHE_DIR, OUT_DIR, tile_of  # noqa: E402
from pipeline.config import REPO_ROOT  # noqa: E402

CHART = REPO_ROOT / "docs" / "harmonization.png"
YEARS = (2013, 2014)
# (south, west, north, east) in whole degrees
REGIONS = {
    "Sumatra + Kalimantan (peat fires)": [(-6, 95, 6, 106), (-5, 108, 5, 119)],
    "California (forest and brush fires)": [(32, -125, 42, -114)],
}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
MODIS_RAW, VIIRS, MODIS_HARM = "#9a9890", "#2a78d6", "#eb6834"


def in_boxes(cell: str, boxes) -> bool:
    lat, lon = (int(v) for v in cell.split(","))
    return any(s <= lat < n and w <= lon < e for s, w, n, e in boxes)


def monthly(sensor: str, boxes, ratios=None, global_ratio=1.0) -> list[float]:
    out = []
    for year in YEARS:
        counts = json.loads((CACHE_DIR / f"{sensor}_{year}_all_countries.json").read_text())
        months = [0.0] * 12
        for cell, row in counts.items():
            if in_boxes(cell, boxes):
                factor = ratios.get(tile_of(cell), global_ratio) if ratios is not None else 1.0
                for m, n in enumerate(row):
                    months[m] += n * factor
        out += months
    return out


def main() -> None:
    meta = json.loads((OUT_DIR / "meta.json").read_text())
    ratios, g = meta["tile_ratios"], meta["global_ratio"]
    x = list(range(24))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")

    for ax, (title, boxes) in zip(axes, REGIONS.items()):
        raw = monthly("modis", boxes)
        viirs = monthly("viirs-snpp", boxes)
        harm = monthly("modis", boxes, ratios, g)
        ax.plot(x, raw, color=MODIS_RAW, linewidth=2, label="MODIS, as measured")
        ax.plot(x, viirs, color=VIIRS, linewidth=2, label="VIIRS, as measured")
        ax.plot(x, harm, color=MODIS_HARM, linewidth=2, linestyle=(0, (5, 3)), label="MODIS, harmonized")
        factor = sum(viirs) / max(1, sum(raw))
        ax.set_title(f"{title}: VIIRS sees {factor:.0f}× more", loc="left", fontsize=10, color=INK_2)
        ax.set_facecolor("#fcfcfb")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK_2, labelsize=8, length=0)
        ax.set_xticks([0, 6, 12, 18], ["Jan 2013", "Jul 2013", "Jan 2014", "Jul 2014"])
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}")

    axes[0].legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle("Harmonization: once converted, the old MODIS counts line up with VIIRS",
                 x=0.01, y=0.98, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.text(0.01, 0.885, "Fire hotspots per month while both satellites flew (2013–2014). "
             "Grey = MODIS raw, blue = VIIRS, dashed orange = MODIS after our per-region conversion.",
             fontsize=9, color=INK_2)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(CHART, facecolor=fig.get_facecolor())
    print(f"Chart saved to {CHART.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
