# NSE Market Data Downloader

Python CLI that downloads four live-analysis datasets from [NSE India](https://www.nseindia.com/) and saves each as a separate CSV (clear filename + calendar date). Built for reliability: retries with backoff, resilient error handling per dataset, validation, logging, and idempotent runs on the same trading day.

## Datasets and source pages

| Assignment page | JSON API used (same data the website loads) |
|-----------------|-------------------------------------------|
| [Top Gainers / Losers](https://www.nseindia.com/market-data/top-gainers-losers) | `GET /api/live-analysis-variations` with `index=gainers` and `index=loosers` (NIFTY block) |
| [Upper Band Hitters](https://www.nseindia.com/market-data/upper-band-hitters) | `GET /api/live-analysis-price-band-hitter` (`upper.AllSec.data`) |
| [Volume Gainers / Spurts](https://www.nseindia.com/market-data/volume-gainers-spurts) | `GET /api/live-analysis-volume-gainers` |
| [52-Week High — Equity](https://www.nseindia.com/market-data/52-week-high-equity-market) | `GET /api/live-analysis-data-52weekhighstock` |

**Note:** These are the undocumented JSON endpoints used by the public website. Use only for permitted personal/research purposes and respect NSE terms of use. This tool does not bypass logins or CAPTCHAs; it uses a normal browser-like session cookie after loading a market-data page.

## Installation

Python 3.10+ recommended.

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Download **all four** CSVs (default output: `output/<YYYY-MM-DD>/` in Asia/Kolkata):

```bash
python main.py
```

Or use the module form:

```bash
python -m nse_downloader.main
```

**One dataset** (matches the assignment example style):

```bash
python main.py --dataset top-gainers-losers
```

Aliases such as `top_gainers_losers`, `upper_band_hitters`, `52_week_high` are accepted; see `DATASET_ALIASES` in `nse_downloader/config.py`.

**Options:**

| Flag | Meaning |
|------|---------|
| `-o`, `--output-dir` | Output root directory (default: `output` or `NSE_OUTPUT_DIR`) |
| `--refresh` | Overwrite CSVs for today’s date folder if they already exist |
| `--sqlite on` or `--sqlite off` | Mirror each saved CSV into SQLite (overrides config) |
| `--sqlite-path PATH` | SQLite database file (default: `output/nse_snapshots.db` or `NSE_SQLITE_PATH`) |
| `--notify-webhook URL` | POST JSON when any dataset fails (Slack-compatible incoming URL) |
| `--history-retention-days N` | Delete `output/<date>/` folders older than N days (`0` = off) |
| `--schedule-daily HH:MM` | Loop: run once per day at this time in **Asia/Kolkata (IST)** |
| `--run-now` | Use with `--schedule-daily`: run the job once immediately, then sleep until the next slot |
| `--config` | Path to YAML settings (default `config/settings.yaml`) |
| `-v`, `--verbose` | Debug logging |

**Environment overrides:** `NSE_BASE_URL`, `NSE_OUTPUT_DIR`, `NSE_MAX_RETRIES`, `NSE_SESSION_INIT_PATH`, `NSE_SQLITE`, `NSE_SQLITE_PATH`, `NSE_NOTIFY_WEBHOOK`, `NSE_HISTORY_RETENTION_DAYS` (see `config/settings.yaml`).

By default the client loads **each dataset’s own market-data page** first (to obtain cookies). Set `session_init_path` in YAML or `NSE_SESSION_INIT_PATH` to force one path (e.g. `/market-data/top-gainers-losers`) for every request.

### Output layout and filenames

Files are written under `<output-dir>/<IST-date>/` so repeated runs the same day do not create confusing duplicates:

- `nse_top_gainers_losers_<date>.csv` — NIFTY gainers and losers combined; column `variation_side` is `gainer` or `loser`
- `nse_upper_band_hitters_<date>.csv`
- `nse_volume_gainers_spurts_<date>.csv`
- `nse_52_week_high_equity_market_<date>.csv`

If a file for that **date** already exists, the run **skips** the network call for that dataset unless you pass `--refresh`.

### Bonus features (assignment extras)

| Bonus | How it works here |
|--------|-------------------|
| **Scheduled execution** | `--schedule-daily 16:05` runs the same CLI every day at that **IST** wall time, or use Windows Task Scheduler / Linux `cron`, or `docker-compose` (see below). |
| **Retries with backoff** | Already in `nse_downloader/client.py` (`max_retries`, `backoff_factor_seconds`). |
| **Configurable output directory** | `-o` / `output_dir` / `NSE_OUTPUT_DIR`. |
| **Docker** | `Dockerfile` + `docker-compose.yml` (tzdata + `TZ=Asia/Kolkata` for IST). |
| **Database + CSV** | Optional SQLite mirror (`sqlite` in YAML or `--sqlite on`); schema in `docs/sqlite_schema.md`. |
| **Historical data management** | `history_retention_days` or `--history-retention-days` prunes old `output/YYYY-MM-DD/` trees. |
| **Failure notifications** | `notify_webhook_url` or `--notify-webhook` sends a JSON payload listing failed datasets after the run. |

Example with bonuses:

```bash
python main.py --sqlite on --sqlite-path output/nse_snapshots.db --history-retention-days 30 --notify-webhook https://hooks.slack.com/services/XXX/YYY/ZZZ
```

## Architecture

- `nse_downloader/config.py` — Page URLs, API paths, required columns, dedupe keys, settings loader
- `nse_downloader/client.py` — Session warm-up (HTML page → cookies), retries, JSON fetch
- `nse_downloader/validator.py` — Required-column checks, duplicate-row handling
- `nse_downloader/storage.py` — IST date strings, atomic CSV write
- `nse_downloader/sqlite_store.py` — Optional SQLite snapshots (bonus)
- `nse_downloader/history.py` — Prune old dated output folders (bonus)
- `nse_downloader/notifications.py` — Webhook on failures (bonus)
- `nse_downloader/scheduler.py` — IST daily loop (bonus)
- `nse_downloader/app.py` — Orchestration: skip-if-exists, fetch remaining, continue on failure
- `nse_downloader/main.py` — CLI

## Error handling and logging

- Transient HTTP errors (429, 5xx) and network timeouts: retried with exponential backoff + jitter (`max_retries`, `backoff_factor_seconds` in config).
- Invalid JSON or unexpected structure: dataset fails with a logged error; **other datasets still run**.
- Console logs use UTF-8 when possible; full detail also goes to `logs/nse_downloader.log` when writable.

## Data validation

Before save:

- DataFrame must be non-empty after parse.
- Expected columns must be present (extra columns from NSE are kept and logged at debug level).
- Duplicates are dropped on `(symbol, series, …)` per dataset (see `DatasetConfig.dedupe_keys`).

## Testing

```bash
pytest tests -q
```

Coverage includes extractors, validation, storage, mocked HTTP failures, and a mocked end-to-end run.

## Sample output

A successful live run’s CSVs are checked in under `examples/sample_output/<date>/` (regenerate with `python main.py -o examples/sample_output --refresh`).

## Database

Primary deliverable is still **CSV**. Optionally enable **SQLite** so each run also persists the same rows (`docs/sqlite_schema.md`).

## Docker (optional)

```bash
docker build -t nse-md .
docker run --rm -e TZ=Asia/Kolkata -v "%CD%/output:/app/output" nse-md python main.py --output-dir /app/output
```

Compose (one-shot and optional daily service profile):

```bash
docker compose up nse-downloader
# profile "scheduled": in-process IST daily loop
docker compose --profile scheduled up nse-scheduled
```

## Scheduled execution (optional)

1. **In-process (IST):** `python main.py --schedule-daily 16:05` (blocks; good in Docker).
2. **OS:** Task Scheduler (Windows) or `cron` calling `python main.py` once per day.
3. **Compose:** `docker compose --profile scheduled up` (see `docker-compose.yml`).

Avoid high frequency; NSE may rate-limit.

## Limitations and assumptions

- Market hours and holidays: APIs may return fewer rows or empty sets when the cash market is closed.
- NSE may change JSON shapes or block automation; failures are logged per dataset.
- “Trading day” for file paths is the **calendar date in Asia/Kolkata**, not NSE’s official session ID.

## License

Educational / assignment use. Data belongs to NSE and respective issuers; this repository only automates public page-backed JSON retrieval.
