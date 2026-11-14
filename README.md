# Smokeshed

> **A burning calendar for the people who breathe the smoke.** NASA Space Apps Challenge 2026: harmonized burning activity calendar.

**Drop a pin anywhere on Earth** and get, in one click:
1. **Right now:** is it burning more than normal? A status (Quiet / Normal / Above normal / Surge) from the last 7 days of NASA fire detections, updated daily, plus yesterday's real satellite image so you can see the smoke.
2. **History:** a harmonized MODIS + VIIRS fire calendar for that area, 2001 to now, with a CSV download.

**Pin Singapore** and you get its *smokeshed*: the burning areas whose smoke ends up in Singapore's air, a haze warning based on the measured "fires in Sumatra → worse air ~1 day later" link, and Singapore's live PM2.5. A *watershed* is all the land whose rain ends up in your river; a *smokeshed* is all the land whose burning ends up in your lungs.

## Why this exists: the pieces existed, but never together

| Existing tool | What's missing |
|---|---|
| NASA FIRMS | MODIS and VIIRS stay separate: no single comparable 2001→now record |
| Global Forest Watch fires | Not harmonized across sensors; only fires *inside* your area |
| SMOKE Policy Tool (Harvard/Columbia) | One region, a heavy atmospheric model, built for land planners |
| MODIS/VIIRS harmonization research | Burned area, not hotspots; a dataset, not a tool |

Smokeshed bridges them: **harmonized record + calendar vs. history + "whose smoke am I breathing?"**, in one click. Details and sources: [docs/WORKFLOW.md](docs/WORKFLOW.md) §4.1.

## Key results

- **Harmonization works:** VIIRS sees ~12× as many hotspots as MODIS worldwide, but the ratio varies by region (8× in California, 16–20× over Indonesian peat). One ratio per 10° region, learned from 2013 alone, predicted 2014 within **11% median error**.
- **It recovers known history unprompted:** Indonesia's El Niño haze years (2006, 2015, 2019, 2023), and Los Angeles's 2003, 2007, 2017 and Jan 2025 fires.
- **Fires come first, haze after:** in 2026, Singapore's PM2.5 rose about **1 day** after Sumatra's fires surged (r = 0.67). This agrees with the monsoon winds and with the SMOKE Policy Tool's finding that South Sumatra matters most. [Chart](docs/feasibility.png)

## Run it yourself (Windows PowerShell, from the repo root)

```powershell
pip install -r requirements.txt
python -m pipeline.download_firms    # ~5 GB of FIRMS yearly files, no key needed
python -m pipeline.fetch_recent      # this year, via the FIRMS API (needs FIRMS_MAP_KEY, see docs/API_SETUP.md)
python -m pipeline.build_calendar    # -> data/processed/calendar/
python -m pipeline.feasibility       # -> docs/feasibility.png + data/processed/smokeshed.json
python -m pipeline.build_now         # last 7 days of fires -> data/processed/now.json (a GitHub Action runs this daily)
python -m http.server 8000 --bind 127.0.0.1   # then open http://127.0.0.1:8000
```

The website is one static page (`index.html`, Leaflet, no build step) reading pre-computed JSON, so it can be hosted on GitHub Pages.

## Data

NASA FIRMS (MODIS Collection 6.1, VIIRS S-NPP 375 m), Singapore PM2.5 from data.gov.sg (NEA), basemap © OpenStreetMap.
