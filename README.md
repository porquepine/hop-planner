# Hop Planner: a Space-A route finder

Type where you are and where you want to go ("Texas" → "Germany", "Austin, TX" → "Ramstein") and Hop Planner chains posted AMC Space-A flights into multi-leg routes. Each leg shows the roll call time, seats (Tentative/Firm/TBD), and recent roll-call history: seats released, how many Space-A passengers flew, and the lowest category selected.

* **Collector (runs on GitHub every 3 hours).** It visits every AMC passenger terminal page and reads the 72-hour schedule and roll-call PDFs. Image-only slides go through OCR. It keeps 120 days of roll-call history and writes one **encrypted** file, `site/data.json`.
* **Website (GitHub Pages, free).** A single page with a username/password login. The schedules are decrypted in your browser and are never stored in readable form on GitHub.
* **No terminal where you are?** It finds the nearest terminals, with distance and drive time. It also lists the best "jumping-off" terminals: places with posted or recent flights to your destination.
* **Facebook-only terminals** (JBSA-Lackland, NAS Fort Worth, many Guard/Reserve units): they're linked in the Terminals tab. Use **My flights** to add a flight you saw there, and searches will include it.

---

## One-time setup (about 15 minutes)

### 1. Create the repository
1. Sign in at github.com (create a free account if you don't have one).
2. Click **+ → New repository**. Name it `hop-planner` and choose **Public**. GitHub Pages is free for public repos, and the flight data is encrypted. Click **Create repository**.
3. On the new repo page click **uploading an existing file**. Drag in **everything inside** the `spacea-hop` folder, including the hidden `.github` folder. On a Mac, press **Cmd+Shift+.** in Finder to show hidden files. Click **Commit changes**.

### 2. Add your logins (secrets)
**Settings → Secrets and variables → Actions → New repository secret**, then add two secrets:

| Name | Value |
|---|---|
| `SPACEA_USERS` | One `username:password` per line, e.g.<br>`patrick:SomeLongPassword!`<br>`spouse:AnotherPassword` |
| `SPACEA_MASTER_KEY` | Any long random string (40+ characters). It lets the collector keep history between runs. Don't share it. |

To add or remove a person later, edit `SPACEA_USERS` and run the workflow again (step 4).

### 3. Turn on GitHub Pages
**Settings → Pages → Build and deployment → Source: GitHub Actions.**

### 4. Run it the first time
**Actions → "Collect Space-A schedules" → Run workflow.** It takes about 3–6 minutes. When it turns green, open
`https://<your-github-username>.github.io/hop-planner/` and sign in.

After that it runs by itself every 3 hours.

---

## Putting it on aldridgestrategy.com

**Option A: subdomain (recommended).** Use `hop.aldridgestrategy.com`.
1. In your **Squarespace Domains** account → aldridgestrategy.com → DNS → add a record: **Type** `CNAME`, **Host** `hop`, **Data** `<your-github-username>.github.io`.
2. In GitHub: **Settings → Pages → Custom domain** → `hop.aldridgestrategy.com` → Save. Tick **Enforce HTTPS** once it's offered (can take up to an hour).

**Option B: inside your Google Site.** In Google Sites: **Insert → Embed → By URL** → paste the GitHub Pages address → **Whole page**. Or add a button that links to it. Inside an embed, "keep me signed in" may not stick, because browsers limit storage in embedded frames.

---

## Things to know

* **Seats are never guaranteed.** "T" seats are tentative and schedules change constantly. Arrival times are estimates from distance. Always confirm with the terminal.
* **AMC's notice on these schedules.** Many AMC schedule PDFs carry a notice against retransmitting or uploading their contents. That's why the data is encrypted and the site is login-only, blocked from search engines, and meant for you and people you trust. Keep it that way, and don't make the bundle public.
* **If a terminal shows "page unreachable" or "schedule looks old"** in the Terminals tab, that terminal changed its page or stopped updating. The collector skips it until it's fixed. Some terminals post PowerPoint files or only Facebook posts, which the collector can't read.
* **If GitHub's servers get blocked by the AMC site** (every terminal shows "page unreachable"), run the collector from your own computer instead: `pip install -r requirements.txt`, install `poppler` and `tesseract` (`brew install poppler tesseract`), set the two secrets as environment variables, run `python3 collector/collect.py`, and commit `site/data.json`.
* **GitHub pauses scheduled workflows after 60 days with no repository activity.** The bot's own commits normally keep it awake. If it ever stops, click **Run workflow** once.

## Files

| Path | What it is |
|---|---|
| `collector/collect.py` | Finds and downloads schedules, parses them, writes the encrypted bundle |
| `collector/parse.py` | Parsers for 72-hour schedules and roll-call reports |
| `collector/locations.py` | ~150 bases with coordinates and spelling variants ("MIGUIRE FORT DIX" → McGuire) |
| `collector/terminals.json` | Terminal directory: AMC pages, phone numbers, Facebook links |
| `site/index.html` | The website: login, search, flight board, terminals, my flights |
| `.github/workflows/collect.yml` | The 3-hourly schedule and Pages deploy |
| `tests/offline_build.py` | Builds a test bundle from saved PDFs (for development) |
