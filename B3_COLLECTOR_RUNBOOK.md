# B3 Public Data Collector — Railway Runbook

Purpose: build a raw B3 data lake moving forward, as broadly as possible, for future algos.

## What it collects

### 1. B3 index API snapshots

Source:

```text
https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/
```

For many indices:

```text
IBOV, IBXX, IBXL, IBRA, SMLL, MLCX, IDIV, IVBX, IGCX, IGCT, IGNM,
ITAG, ISEE, ICO2, UTIL, IFNC, ICON, IMOB, INDX, IEEX, IMAT, BDRX,
IFIX, IFIL, GPTW, AGFS
```

Datasets:

```text
GetPortfolioDay
GetTheoricalPortfolio
GetQuartelyPreview
GetConfigurations
GetDownloadPortfolioDay
GetDownloadPortfolioTheorical
GetDownloadPreview
GetDownloadPortfolioSegment
```

This gives current/day/theoretical/preview index portfolio snapshots going forward.

### 2. B3 Pesquisa por Pregão daily files

Source:

```text
https://www.b3.com.br/pesquisapregao/download?filelist=...
```

Patterns collected with rolling backfill:

```text
SecurityList{YYMMDD}.zip
IN{YYMMDD}.zip
II{YYMMDD}.zip
PR{YYMMDD}.zip
SPRE{YYMMDD}.zip
SPRD{YYMMDD}.zip
IR{YYMMDD}.zip
AI{YYMMDD}.zip
FP{YYMMDD}.zip
FR{YYMMDD}.zip
LD{YYMMDD}.zip
LA{YYMMDD}.zip
PG{YYMMDD}.zip
DI{YYMMDD}.zip
UN{YYMMDD}.zip
VA{YYMMDD}.zip
TX{YYMMDD}.zip
CT{YYMMDD}.zip
CV{YYMMDD}.zip
CN{YYMMDD}.zip
GL{YYMMDD}.zip
ID{YYMMDD}.ex_
PE{YYMMDD}.ex_
RE{YYMMDD}.ex_
MM{YYMMDD}.ex_
TS{YYMMDD}.ex_
PU{YYMMDD}.ex_
RF{YYMMDD}.ex_
```

It backfills the last `B3_BACKFILL_DAYS` every run to catch missed/late files.

### 3. B3 COTAHIST yearly files

Source:

```text
https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP
```

Collects current/prior/next year each run. This is redundant but useful because the current-year file changes over time.

## Storage design

Raw-first. No destructive parsing.

Local path:

```text
/data/b3_lake/raw/<source>/<dataset>/<logical_date>/<timestamp>_<sha>.ext
```

Metadata:

```text
/data/b3_lake/manifest.jsonl
/data/b3_lake/errors.jsonl
/data/b3_lake/runs.jsonl
```

Each artifact has:

```json
{
  "source": "b3_index_api",
  "dataset": "IBOV_portfolio_day",
  "logical_date": "2026-06-08",
  "path": "...",
  "bytes": 12345,
  "sha256": "...",
  "url": "...",
  "collected_at": "...",
  "extra": {...}
}
```

## Redundancy

- retries with exponential backoff;
- rolling backfill every run;
- stores every raw artifact with content hash;
- optional S3/R2 mirror;
- Railway restart policy;
- can run multiple collectors with same bucket safely because paths include hash/timestamp;
- empty/missing B3 zip responses are skipped but noted in manifest.

## Railway deploy

Files:

```text
b3_data_collector.py
requirements-collector.txt
Dockerfile.collector
railway.toml
```

Deploy manually:

```bash
railway login
railway init
railway up
```

If you already have a Railway project/workspace:

```bash
railway link
railway up
```

Set a persistent Railway volume mounted at:

```text
/data
```

Strongly recommended: configure S3/R2 mirror because Railway volumes are not a complete backup strategy.

## Environment variables

Core:

```text
B3_DATA_DIR=/data/b3_lake
COLLECT_INTERVAL_MINUTES=360
B3_BACKFILL_DAYS=50000
B3_MAX_RETRIES=4
B3_REQUEST_TIMEOUT=90
B3_ENABLE_INDEX_API=1
B3_ENABLE_PESQUISA=1
B3_ENABLE_COTAHIST=1
```

Overrides for smaller tests or separate services:

```text
B3_INDEX_CODES=IBOV,IBXX,IFIX
B3_PESQUISA_PATTERNS=SecurityList{YYMMDD}.zip,IN{YYMMDD}.zip,PR{YYMMDD}.zip,IR{YYMMDD}.zip
```

For one-shot jobs:

```text
RUN_ONCE=1
```

Optional S3/R2 mirror:

```text
B3_S3_BUCKET=your-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=auto
B3_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
```

## Smoke test

```bash
RUN_ONCE=1 \
B3_DATA_DIR=./collector_smoke \
B3_INDEX_CODES=IBOV \
B3_ENABLE_PESQUISA=0 \
B3_ENABLE_COTAHIST=0 \
B3_MAX_RETRIES=1 \
python3 b3_data_collector.py
```

Validated on 2026-06-08: collected 8 IBOV API artifacts with no errors.

## Suggested Railway setup

### Service 1 — daemon collector

```text
COLLECT_INTERVAL_MINUTES=360
B3_BACKFILL_DAYS=50000
```

This runs every 6h and backfills recent days.

### Service 2 — daily deep backfill collector

Same image, separate service or Railway cron if available:

```text
RUN_ONCE=1
B3_BACKFILL_DAYS=50000
```

Run daily at night. This gives extra redundancy for delayed files.

### Service 3 — yearly COTAHIST snapshot

Same image is enough, but if cost becomes high, split later.

## Important caveats

- This collects public B3 files/APIs. It does not collect licensed Binary UMDF live feeds.
- B3 may change hidden API contracts; raw errors are logged.
- Some index codes may return empty or errors; this is expected.
- Some Pesquisa por Pregão patterns are not published every day; empty zips are skipped.

## Next improvements

1. Add parser jobs that convert raw XML/CSV/TXT into normalized Parquet.
2. Add object-store inventory validation: verify every manifest path exists in S3.
3. Add alerting when a run collects zero artifacts from a core source.
4. Add B3 website JS endpoint monitor to detect API changes.
5. Add Wayback/backfill scraper for historical index portfolios if found.
