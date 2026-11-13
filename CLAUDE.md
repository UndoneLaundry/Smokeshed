# CLAUDE.md: Smokeshed project rules

Read this first, every session.

## What this project is

**Smokeshed** is our NASA Space Apps 2026 entry for the *harmonized burning activity calendar* challenge.
A user drops a pin where they live. The app shows which burning areas affect that location's air (its *smokeshed*), a harmonized MODIS + VIIRS burning calendar for that area (2001→now), and a "Haze Watch" warning when hotspots in the smokeshed surge.

- Full plan, reasoning and sources: `docs/WORKFLOW.md`
- API keys and secrets: `docs/API_SETUP.md`

## Rule #1: Simple beats clever

This applies to everything: the app, the code, and how you work with me. However advanced a tool is, simple functionality wins.

**For the user of the app:**
- Getting from question to answer takes the **fewest possible steps**. Target: one action → one answer.
- The app opens with a sensible default already shown (Singapore pinned, current year's calendar visible). No empty screens.
- No logins, no settings pages, no setup wizards, no modals that must be dismissed.
- Every feature must pass the test: *"Can a tired emergency manager get the answer in under 10 seconds without instructions?"* If not, simplify or cut it.
- Show answers as a **plain-language sentence first**, then the chart. Numbers support the sentence, not the other way round.
- If a feature needs more than 2 clicks to reach its result, redesign it.

**For the code:**
- Fewest moving parts. Default architecture: **static website + pre-computed JSON files**. No backend server unless there's no other way.
- Frontend default: plain HTML/CSS/JavaScript with **Leaflet** for the map. No build step, no framework, unless I agree to change it.
- Pipeline: plain Python scripts, each run with **one command**, e.g. `python -m pipeline.<name>`.
- Add a dependency only when it removes real work. Ask me before adding one, and say why.
- Prefer boring, readable code over clever code. Short functions, clear names, comments that explain *why*.
- Rebuilding all data should eventually be one command: `python -m pipeline.build`.

**For working with me:**
- Give me **one step at a time**. Don't hand me a list of 10 things to do.
- When I need to run something, give me the exact command, say in one sentence what it does, and say what output to expect.

## About me (the developer)

- This is my first project of this kind. I'm learning as I go. Explain things simply, like a senior engineer who enjoys teaching.
- I'm on **Windows, PowerShell**, repo at `c:\dev\Smokeshed`.
- Run modules with `python -m pipeline.<name>` from the repo root (plain `python pipeline/x.py` breaks imports).

## Security rules (never break these)

- **Never read, open, print, or `cat` any `.env` file**, by any tool or command.
- Never print API keys. Never put a key in a URL that gets printed or logged. Redact keys in error messages.
- **Never put API keys in frontend code.** Anything the browser loads is public.
- Live FIRMS data for the website must be fetched by a GitHub Action using the GitHub Secret `FIRMS_MAP_KEY`, saved as JSON, and the site reads the JSON.
- Before every commit, run `git status` and confirm no `.env` file is staged.
- Never commit large raw data. Raw downloads go in `data/raw/` (gitignored). Small processed outputs the website needs go in `data/processed/`.

## Facts we've already confirmed (don't re-learn these the hard way)

- FIRMS MAP_KEY works. Connectivity check: `python -m pipeline.check_firms`.
- The FIRMS **area API** only accepts a day range of **1–5 days**. Use it only for recent data (Haze Watch).
- **History** (2001→now) comes from the **FIRMS archive download** (requested on the FIRMS website, delivered by email as CSV). I download these manually and put them in `data/raw/`.
- Singapore PM2.5 history comes from data.gov.sg (downloaded manually into `data/raw/`).
- FIRMS sometimes returns HTTP 200 with a plain-text error. Always check the response actually looks like CSV.
- Hotspot counts can legitimately be 0 (e.g. wet season). Zero is data, not an error.

## Docs rules

- `docs/WORKFLOW.md` contains researched facts and numbered sources. Don't change facts, numbers or sources without telling me. Only add a new source if you've verified it and can give the link.
- When a decision from WORKFLOW.md section 13 ("Open decisions") gets made, record it in that section with a one-line reason.

## Current task list (do in order, one at a time)

1. **Feasibility test.** Does a surge in Sumatra/Kalimantan hotspots come *before* Singapore PM2.5 spikes?
   - First, walk me step by step through downloading (a) FIRMS archive VIIRS S-NPP hotspots for Indonesia, Jun–Oct 2025, and (b) Singapore 2025 hourly PM2.5 from data.gov.sg. Tell me exactly where to save them in `data/raw/`.
   - Then write `pipeline/feasibility.py`. One command, output = **one chart image** (daily hotspot count vs daily Singapore PM2.5, same timeline) + **one printed sentence** stating the best lag in days and how strong the link is, in plain words.
   - Keep it simple: whole-region daily counts first. Per-grid-cell smokeshed comes later.
2. Harmonization prototype (MODIS vs VIIRS overlap ratio) for one region.
3. Smoke Calendar page: one HTML page, Singapore default, calendar from pre-computed JSON.
4. Haze Watch sentence + GitHub Action for live FIRMS data.
5. CSV export + briefing card.

After each task: tell me in 3–4 lines what was built, the one command to run it, and what I should check. Then wait for me before starting the next task.
