# RFC-001: B3 Data Parsing Pipeline and Schema Design for Trading Algos

## Status
Proposed

## Goals
- Transform raw B3 data into production-ready Parquet format
- Enable efficient algorithm development with clean, structured time-series data
- Maintain backwards compatibility for historical analysis

## Data Pipeline
1. **Raw Collection**: As implemented in `b3_data_collector.py` (stores files at `/data/b3_lake/raw/`)
2. **Parsing Job** (daily after collection):
   - Process COTAHIST annual files → daily OHLCV for equities
   - Parse PR{YYMMDD}.zip → per-trade event records
   - Process SecurityList{YYMMDD}.zip → instrument metadata

## Schema Specifications
### COTAHIST (Equities OHLCV)
```json
{
  "date": "2024-12-20",
  "ticker": "PETR4",
  "open": 28.35,
  "high": 28.58,
  "low": 28.01,
  "close": 28.47,
  "volume": 1098450.0,
  "turnover": 31275200.0
}
```

### PR Trade Events
```json
{
  "time": "2024-12-20T10:05:42.123Z",
  "ticker": "VALE5",
  "price": 45.67,
  "volume": 2000,
  "side": "B",
  "order_id": "12345.7890"
}
```

## Validation Requirements
- **COTAHIST**: Verify no missing date entries > 3 days
- **PR**: Confirm ≥500 trades per day for major stocks
- **Metadata**: Check consistency between `SecurityList` dates
- **S3 Check**: Ensure all manifest entries exist in storage

## Implementation Plan
| Phase | Task | Timeline |
|--------|------|-----------|
| 1 | COTAHIST parser | 1 week |
| 2 | PR files parser | 1.5 weeks |
| 3 | Metadata enrichment (ISO codes, corporate actions) | 1 week |
| 4 | Monitoring/alerts deployment | 3 days |

## Notes
- All parsed outputs will reside at `/data/b3_lake/parquet/`
- Existing raw data will remain for reference
- Schema version control TBD per source