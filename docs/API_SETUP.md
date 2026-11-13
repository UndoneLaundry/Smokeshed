# API setup

Smokeshed pulls data from a few public services. Only one of them needs a key. This page explains which APIs we use, how to set up your keys locally, and how to keep them safe.

## Which APIs we use

| Service | What we use it for | Key needed? |
|---|---|---|
| **NASA FIRMS** | Active fire detections (MODIS + VIIRS) | **Yes, required.** Free "MAP_KEY" from <https://firms.modaps.eosdis.nasa.gov/api/map_key/> |
| **data.gov.sg** | Singapore air quality data | Optional. It works without a key; a key only gives higher rate limits |
| **NASA GIBS** | Satellite imagery map layers | No key |
| **NASA EONET** | Natural event data (wildfires, etc.) | No key |

## Setting up your keys locally

1. Get a free FIRMS MAP_KEY from <https://firms.modaps.eosdis.nasa.gov/api/map_key/>. It arrives by email.
2. In the repo root, copy the template:

   ```bash
   cp .env.example .env
   ```

3. Open `.env` in your editor and paste your key after the `=`:

   ```
   FIRMS_MAP_KEY=your_key_here
   DATAGOVSG_API_KEY=
   ```

   Leave `DATAGOVSG_API_KEY` blank unless you have one.
4. Install the Python dependencies (`pip install -r requirements.txt`). The pipeline reads the keys through `pipeline/config.py`. If `FIRMS_MAP_KEY` is missing you'll get a clear error telling you what to do. The key itself is never printed.

`.env` is listed in `.gitignore`, so git won't pick it up. Only `.env.example` (which has no real values) is committed.

## Rules for keeping keys safe

- **Never paste a key into a chat**, including AI assistants, Slack, Discord or GitHub issues.
- **Never commit a key.** Before committing, run `git status` and make sure no `.env` file is listed.
- **Never put a key in frontend code** (HTML, JavaScript, or anything served to the browser). Anyone can read frontend code. The browser should only see data the pipeline has already fetched.
- Don't share screenshots or screen recordings that show your `.env` file.

This repo's `.claude/settings.json` also blocks Claude Code from reading `.env` files.

## Live data via GitHub Actions

Live FIRMS data will be fetched by a GitHub Action, not by the browser. The Action reads the key from a **GitHub Secret named `FIRMS_MAP_KEY`**.

To add it (repo admins only):

1. On GitHub, go to the repo's **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `FIRMS_MAP_KEY`. Value: the FIRMS key. Save.

GitHub hides secret values in logs, and nobody can read a secret back after saving it.

## If a key leaks

If a key ends up somewhere public (a commit, a chat, a screenshot, a log):

1. **Request a new key** from FIRMS at <https://firms.modaps.eosdis.nasa.gov/api/map_key/> and stop using the old one.
2. Put the new key in your local `.env` and update the `FIRMS_MAP_KEY` GitHub Secret.
3. Tell the team so everyone switches to the new key.
4. If the key was committed, deleting it in a new commit is not enough because it stays in the git history. Treat it as exposed and replace it, whatever happens to the history.
