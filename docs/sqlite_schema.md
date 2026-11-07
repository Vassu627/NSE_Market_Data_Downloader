# SQLite mirror schema (bonus)

When `sqlite.enabled` is true or you pass `--sqlite on`, each successful dataset save is also stored in a SQLite file (default `output/nse_snapshots.db`).

## Tables

```sql
PRAGMA journal_mode = WAL;

CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    csv_path TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(dataset_id, trade_date)
);

CREATE TABLE snapshot_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    row_json TEXT NOT NULL
);

CREATE INDEX idx_snapshot_rows_snapshot ON snapshot_rows(snapshot_id);
```

Each `snapshot_rows.row_json` holds one CSV row as JSON (keys match NSE field names). Re-running the same `dataset_id` + `trade_date` replaces the prior snapshot.
