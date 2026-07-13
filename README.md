# ETF Portfolio Dashboard — setup

Why this exists: Stooq (the price data source) doesn't send the CORS
headers browsers require, so a browser can never fetch price data from
Stooq directly — no matter what proxy trick is used. The fix is to fetch
the data outside the browser (a scheduled script) and have the page just
read the result.

## What's in this folder
- `index.html` — the dashboard. Reads `data.json` (same-origin, no fetch to Stooq).
- `data.json` — the current snapshot. Starts empty; gets filled in by the workflow below.
- `scripts/fetch_data.py` — pulls 13 months of daily closes per ticker from Stooq and writes `data.json`.
- `.github/workflows/refresh.yml` — runs `fetch_data.py` every morning and commits the update.

## One-time setup (~5 minutes)
1. Create a new **public** GitHub repository (private also works, but Pages is simpler on public repos on the free tier).
2. Upload all the files in this folder, preserving the folder structure (`.github/workflows/refresh.yml` must stay at that exact path).
3. In the repo: **Settings → Pages** → set "Source" to "Deploy from a branch", branch `main`, folder `/ (root)`. Save. GitHub will give you a URL like `https://<username>.github.io/<repo>/`.
4. In the repo: **Settings → Actions → General** → under "Workflow permissions" select "Read and write permissions". Save. (The workflow needs this to commit the updated `data.json` back to the repo.)
5. Go to the **Actions** tab → "Refresh ETF Dashboard Data" → **Run workflow** to trigger it manually the first time, so `data.json` gets populated immediately instead of waiting for tomorrow.
6. Visit your GitHub Pages URL — the dashboard should now show live data.

From then on, the workflow runs automatically every morning (06:00 UTC ≈ 07:00 UK winter time — see the timing note in `refresh.yml` about British Summer Time, since GitHub's scheduler is UTC-only and doesn't shift for DST) and the page always reflects the latest committed `data.json`.

## If you'd rather not use GitHub
You can run `python scripts/fetch_data.py` yourself each morning (e.g. via
your own machine's Task Scheduler/cron) from any environment with internet
access — it just needs to sit in the same folder as `index.html` so the
`data.json` it writes lands next to the page. Then open `index.html`
through a local web server (e.g. `python -m http.server` in this folder)
rather than double-clicking it, since a bare `file://` page can also run
into `fetch()` restrictions when reading local JSON in some browsers.
