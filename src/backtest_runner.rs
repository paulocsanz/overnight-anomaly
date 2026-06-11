/// Automatic B3 backtest runner.
/// Downloads COTAHIST ZIPs from Tigris S3, parses the fixed-width format,
/// evaluates all active strategies, and inserts historical trades directly
/// into the database — no Python or external scripts required.
use anyhow::{bail, Context, Result};
use chrono::Datelike as _;
use hmac::{Hmac, Mac};
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use std::collections::{HashMap, VecDeque};
use std::io::Read;
use std::sync::Arc;
use uuid::Uuid;

type HmacSha256 = Hmac<Sha256>;
const UNBOUNDED_LIQUIDITY_CAP_BRL: f64 = 9_999_999_999.0;

// ═══════════════════════════════════════════════════════════════════════════════
// S3 config + SigV4 signing
// ═══════════════════════════════════════════════════════════════════════════════

pub struct S3Cfg {
    pub endpoint: String,
    pub bucket: String,
    pub access_key: String,
    pub secret_key: String,
    pub region: String,
}

impl S3Cfg {
    pub fn from_env() -> Option<Self> {
        Some(S3Cfg {
            endpoint: std::env::var("S3_ENDPOINT")
                .unwrap_or_else(|_| "https://t3.storageapi.dev".into()),
            bucket: std::env::var("S3_BUCKET")
                .unwrap_or_else(|_| "b3-public-data-lake-xi4emg".into()),
            access_key: std::env::var("AWS_ACCESS_KEY_ID").ok()?,
            secret_key: std::env::var("AWS_SECRET_ACCESS_KEY").ok()?,
            region: std::env::var("S3_REGION").unwrap_or_else(|_| "auto".into()),
        })
    }
}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    h.finalize().iter().map(|b| format!("{b:02x}")).collect()
}

fn hmac_sha256(key: &[u8], data: &[u8]) -> Vec<u8> {
    let mut mac = HmacSha256::new_from_slice(key).expect("HMAC accepts any key");
    mac.update(data);
    mac.finalize().into_bytes().to_vec()
}

fn signing_key(secret: &str, date: &str, region: &str, service: &str) -> Vec<u8> {
    let key = format!("AWS4{secret}");
    let k1 = hmac_sha256(key.as_bytes(), date.as_bytes());
    let k2 = hmac_sha256(&k1, region.as_bytes());
    let k3 = hmac_sha256(&k2, service.as_bytes());
    hmac_sha256(&k3, b"aws4_request")
}

fn uri_encode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char);
            }
            b => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

fn s3_headers(cfg: &S3Cfg, path: &str, query: &str) -> reqwest::header::HeaderMap {
    let now = chrono::Utc::now();
    let amzdate = now.format("%Y%m%dT%H%M%SZ").to_string();
    let datestamp = now.format("%Y%m%d").to_string();
    let host = cfg
        .endpoint
        .trim_start_matches("https://")
        .trim_start_matches("http://");
    let empty_hash = sha256_hex(b"");

    let canonical_headers =
        format!("host:{host}\nx-amz-content-sha256:{empty_hash}\nx-amz-date:{amzdate}\n");
    let signed_headers = "host;x-amz-content-sha256;x-amz-date";
    let canonical_request =
        format!("GET\n{path}\n{query}\n{canonical_headers}\n{signed_headers}\n{empty_hash}");
    let scope = format!("{datestamp}/{}/{}/aws4_request", cfg.region, "s3");
    let string_to_sign = format!(
        "AWS4-HMAC-SHA256\n{amzdate}\n{scope}\n{}",
        sha256_hex(canonical_request.as_bytes())
    );

    let skey = signing_key(&cfg.secret_key, &datestamp, &cfg.region, "s3");
    let sig: String = {
        let mut mac = HmacSha256::new_from_slice(&skey).unwrap();
        mac.update(string_to_sign.as_bytes());
        mac.finalize()
            .into_bytes()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect()
    };
    let auth = format!(
        "AWS4-HMAC-SHA256 Credential={}/{scope}, SignedHeaders={signed_headers}, Signature={sig}",
        cfg.access_key
    );

    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("x-amz-date", amzdate.parse().unwrap());
    headers.insert("x-amz-content-sha256", empty_hash.parse().unwrap());
    headers.insert("Authorization", auth.parse().unwrap());
    headers
}

async fn list_keys(client: &reqwest::Client, cfg: &S3Cfg, prefix: &str) -> Result<Vec<String>> {
    let path = format!("/{}", cfg.bucket);
    let query = format!("list-type=2&prefix={}", uri_encode(prefix));
    let url = format!("{}{path}?{query}", cfg.endpoint);

    let body = client
        .get(&url)
        .headers(s3_headers(cfg, &path, &query))
        .send()
        .await
        .context("S3 list request")?
        .text()
        .await?;

    // Minimal XML parse — extract <Key>…</Key>
    let mut keys = Vec::new();
    let mut cur = body.as_str();
    while let Some(s) = cur.find("<Key>") {
        cur = &cur[s + 5..];
        if let Some(e) = cur.find("</Key>") {
            keys.push(cur[..e].to_string());
            cur = &cur[e + 6..];
        }
    }
    keys.sort();
    Ok(keys)
}

async fn get_object(client: &reqwest::Client, cfg: &S3Cfg, key: &str) -> Result<Vec<u8>> {
    let enc_key = key.split('/').map(uri_encode).collect::<Vec<_>>().join("/");
    let path = format!("/{}/{}", cfg.bucket, enc_key);
    let url = format!("{}{path}", cfg.endpoint);

    let resp = client
        .get(&url)
        .headers(s3_headers(cfg, &path, ""))
        .send()
        .await
        .context("S3 get request")?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        bail!("S3 get {key} → {status}: {body}");
    }
    Ok(resp.bytes().await?.to_vec())
}

// ═══════════════════════════════════════════════════════════════════════════════
// COTAHIST parsing (fixed-width, Latin-1, inside a ZIP)
// ═══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone)]
struct OhlcvRow {
    date: String, // YYYYMMDD
    ticker: String,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    volume: f64, // BRL traded value for the day
    num_trades: f64,
}

fn parse_i64_field(bytes: &[u8], start: usize, end: usize) -> Option<i64> {
    let s = std::str::from_utf8(bytes.get(start..end)?).ok()?.trim();
    s.parse().ok()
}

fn parse_cotahist_zip(zip_bytes: &[u8]) -> Result<Vec<OhlcvRow>> {
    let cursor = std::io::Cursor::new(zip_bytes);
    let mut arc = zip::ZipArchive::new(cursor).context("open zip")?;

    // Find first non-directory entry
    let idx = (0..arc.len())
        .find(|&i| {
            !arc.by_index(i)
                .map(|f| f.name().ends_with('/'))
                .unwrap_or(true)
        })
        .context("no file in zip")?;

    let mut file = arc.by_index(idx)?;
    let mut data = Vec::new();
    file.read_to_end(&mut data).context("read cotahist")?;

    let mut rows = Vec::new();
    for line in data.split(|&b| b == b'\n') {
        if line.len() < 188 {
            continue;
        }
        if &line[0..2] != b"01" {
            continue;
        }
        // BDI code: '02' = equity, '12' = ETF
        let bdi = line.get(10..12).unwrap_or(b"");
        if bdi != b"02" && bdi != b"12" {
            continue;
        }
        // Market type '010' = regular
        if line.get(24..27).unwrap_or(b"") != b"010" {
            continue;
        }

        let ticker = std::str::from_utf8(line.get(12..24).unwrap_or(b""))
            .unwrap_or("")
            .trim()
            .to_string();
        let date = std::str::from_utf8(line.get(2..10).unwrap_or(b""))
            .unwrap_or("")
            .to_string();

        let open = parse_i64_field(line, 56, 69).map(|v| v as f64 / 100.0);
        let high = parse_i64_field(line, 69, 82).map(|v| v as f64 / 100.0);
        let low = parse_i64_field(line, 82, 95).map(|v| v as f64 / 100.0);
        let close = parse_i64_field(line, 108, 121).map(|v| v as f64 / 100.0);
        let num_trades = parse_i64_field(line, 147, 152).map(|v| v as f64);
        let volume = parse_i64_field(line, 170, 188).map(|v| v as f64 / 100.0);

        if let (Some(o), Some(h), Some(l), Some(c), Some(v), Some(n)) =
            (open, high, low, close, volume, num_trades)
        {
            if o > 0.0 && c > 0.0 {
                rows.push(OhlcvRow {
                    date,
                    ticker,
                    open: o,
                    high: h,
                    low: l,
                    close: c,
                    volume: v,
                    num_trades: n,
                });
            }
        }
    }
    Ok(rows)
}

// ═══════════════════════════════════════════════════════════════════════════════
// Gap + derived-feature computation
// ═══════════════════════════════════════════════════════════════════════════════

#[derive(Debug)]
struct GappedRow {
    date: String, // YYYYMMDD
    ticker: String,
    open: f64,
    close: f64,
    volume: f64,
    num_trades: f64,
    gap_pct: f64,
    prev_close: f64,
    prev_day_return: Option<f64>,
    prev_range_pct: Option<f64>,
    prev_volume: Option<f64>,
    avg_volume_10d: Option<f64>,
}

fn compute_gaps(mut rows: Vec<OhlcvRow>) -> Vec<GappedRow> {
    // Sort by ticker then date so we can iterate groups sequentially
    rows.sort_unstable_by(|a, b| a.ticker.cmp(&b.ticker).then(a.date.cmp(&b.date)));

    let mut result = Vec::with_capacity(rows.len());
    let mut i = 0;

    while i < rows.len() {
        let ticker = rows[i].ticker.clone();
        let mut j = i;
        while j < rows.len() && rows[j].ticker == ticker {
            j += 1;
        }

        // rows[i..j]: this ticker, sorted by date
        let mut vol_history: VecDeque<f64> = VecDeque::new();

        for k in i..j {
            let curr = &rows[k];

            if k > i {
                let prev = &rows[k - 1];
                let prev_close = prev.close;
                if prev_close <= 0.0 {
                    vol_history.push_back(curr.volume);
                    continue;
                }

                let gap_pct = (curr.open - prev_close) / prev_close * 100.0;

                let prev_day_return = if k >= i + 2 {
                    let pp = &rows[k - 2];
                    if pp.close > 0.0 {
                        Some((prev_close - pp.close) / pp.close * 100.0)
                    } else {
                        None
                    }
                } else {
                    None
                };

                let prev_range_pct = Some((prev.high - prev.low) / prev_close * 100.0);

                let avg_volume_10d = if vol_history.len() >= 5 {
                    let sum: f64 = vol_history.iter().sum();
                    Some(sum / vol_history.len() as f64)
                } else {
                    None
                };

                result.push(GappedRow {
                    date: curr.date.clone(),
                    ticker: curr.ticker.clone(),
                    open: curr.open,
                    close: curr.close,
                    volume: curr.volume,
                    num_trades: curr.num_trades,
                    gap_pct,
                    prev_close,
                    prev_day_return,
                    prev_range_pct,
                    prev_volume: Some(prev.volume),
                    avg_volume_10d,
                });
            }

            if vol_history.len() >= 10 {
                vol_history.pop_front();
            }
            vol_history.push_back(curr.volume);
        }
        i = j;
    }
    result
}

// ═══════════════════════════════════════════════════════════════════════════════
// Strategy signal evaluation
// ═══════════════════════════════════════════════════════════════════════════════

struct StrategyConf {
    id: Uuid,
    gap_threshold: f64,
    direction: String,
    tickers: Option<Vec<String>>,
    volume_multiplier: f64,
    require_trend_confirm: bool,
    require_tight_prior_range: bool,
    tight_range_threshold: f64,
    min_daily_volume_brl: f64,
    min_num_trades: f64,
    min_price: f64,
    max_avg_volume_participation_pct: f64,
    max_prev_volume_participation_pct: f64,
    max_position_brl: f64,
    min_position_brl: f64,
    max_daily_exposure_pct: f64,
    pos_pct: f64,
    slippage_bps: f64,
}

struct SignalRow {
    strategy_id: Uuid,
    ticker: String,
    signal_type: String,
    gap_pct: f64,
    open_price: f64,
    close_price: f64,
    signal_date: String, // YYYY-MM-DD
    gross_return_pct: f64,
    net_return_pct: f64,
    pos_pct: f64,
    liquidity_cap_brl: f64,
    min_position_brl: f64,
    max_daily_exposure_pct: f64,
}

fn evaluate_signal(row: &GappedRow, strat: &StrategyConf) -> Option<SignalRow> {
    let gap = row.gap_pct;
    let gap_abs = gap.abs();

    if gap_abs < strat.gap_threshold {
        return None;
    }
    if row.volume < strat.min_daily_volume_brl {
        return None;
    }
    if row.num_trades < strat.min_num_trades {
        return None;
    }
    if row.open < strat.min_price {
        return None;
    }

    let mut liquidity_cap_brl = f64::INFINITY;
    if strat.max_avg_volume_participation_pct > 0.0 {
        let av = row.avg_volume_10d?;
        if av <= 0.0 {
            return None;
        }
        liquidity_cap_brl =
            liquidity_cap_brl.min(av * strat.max_avg_volume_participation_pct / 100.0);
    }
    if strat.max_prev_volume_participation_pct > 0.0 {
        let pv = row.prev_volume?;
        if pv <= 0.0 {
            return None;
        }
        liquidity_cap_brl =
            liquidity_cap_brl.min(pv * strat.max_prev_volume_participation_pct / 100.0);
    }
    if strat.max_position_brl > 0.0 {
        liquidity_cap_brl = liquidity_cap_brl.min(strat.max_position_brl);
    }
    if !liquidity_cap_brl.is_finite() {
        liquidity_cap_brl = UNBOUNDED_LIQUIDITY_CAP_BRL;
    }
    if liquidity_cap_brl < strat.min_position_brl {
        return None;
    }

    if let Some(ref tickers) = strat.tickers {
        if !tickers.contains(&row.ticker) {
            return None;
        }
    }

    // Trend confirmation: gap must agree with prior-day direction
    if strat.require_trend_confirm {
        let prev_ret = row.prev_day_return?;
        if gap > 0.0 && prev_ret < 0.0 {
            return None;
        }
        if gap < 0.0 && prev_ret > 0.0 {
            return None;
        }
    }

    // Volume surge: prior day volume must exceed N × rolling average.
    // Missing rolling history is not a valid pass; otherwise newly listed/illiquid
    // instruments slip through the filter.
    if strat.volume_multiplier > 0.0 {
        let pv = row.prev_volume?;
        let av = row.avg_volume_10d?;
        if av <= 0.0 || pv < av * strat.volume_multiplier {
            return None;
        }
    }

    // Tight prior range: prior day must have been low-volatility (compressed)
    if strat.require_tight_prior_range {
        let pr = row.prev_range_pct?;
        if pr > strat.tight_range_threshold {
            return None;
        }
    }

    let sig_type = if strat.direction == "momentum" {
        if gap > 0.0 {
            "LONG"
        } else {
            "SHORT"
        }
    } else {
        if gap > 0.0 {
            "SHORT"
        } else {
            "LONG"
        }
    };

    let gross_ret = if strat.direction == "momentum" {
        (row.close - row.open) / row.open
    } else {
        (row.open - row.close) / row.open
    };
    let slippage = strat.slippage_bps / 10000.0;
    let net_ret = gross_ret - slippage;

    // Format date YYYYMMDD → YYYY-MM-DD
    let d = &row.date;
    let signal_date = if d.len() == 8 {
        format!("{}-{}-{}", &d[..4], &d[4..6], &d[6..8])
    } else {
        d.clone()
    };

    Some(SignalRow {
        strategy_id: strat.id,
        ticker: row.ticker.clone(),
        signal_type: sig_type.to_string(),
        gap_pct: gap,
        open_price: row.open,
        close_price: row.close,
        signal_date,
        gross_return_pct: gross_ret * 100.0,
        net_return_pct: net_ret * 100.0,
        pos_pct: strat.pos_pct,
        liquidity_cap_brl,
        min_position_brl: strat.min_position_brl,
        max_daily_exposure_pct: strat.max_daily_exposure_pct,
    })
}

async fn fetch_active_strategies(pool: &PgPool) -> Result<Vec<StrategyConf>> {
    let rows: Vec<(Uuid, serde_json::Value, serde_json::Value)> = sqlx::query_as(
        "SELECT id, signal_config, trading_rules FROM strategies WHERE active = true",
    )
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|(id, sc, rules)| {
            let tickers: Option<Vec<String>> = sc
                .get("tickers")
                .and_then(|v| serde_json::from_value(v.clone()).ok());

            StrategyConf {
                id,
                gap_threshold: sc
                    .get("gap_threshold")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(2.0),
                direction: sc
                    .get("direction")
                    .and_then(|v| v.as_str())
                    .unwrap_or("reversal")
                    .to_string(),
                tickers,
                volume_multiplier: sc
                    .get("volume_multiplier")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0),
                require_trend_confirm: sc
                    .get("require_trend_confirmation")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false),
                require_tight_prior_range: sc
                    .get("require_tight_prior_range")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false),
                tight_range_threshold: sc
                    .get("tight_range_threshold")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(1.5),
                min_daily_volume_brl: sc
                    .get("min_daily_volume_brl")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0),
                min_num_trades: sc
                    .get("min_num_trades")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0),
                min_price: sc.get("min_price").and_then(|v| v.as_f64()).unwrap_or(0.0),
                max_avg_volume_participation_pct: sc
                    .get("max_avg_volume_participation_pct")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(2.0),
                max_prev_volume_participation_pct: sc
                    .get("max_prev_volume_participation_pct")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(5.0),
                max_position_brl: sc
                    .get("max_position_brl")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0),
                min_position_brl: rules
                    .get("min_position_brl")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(500.0),
                max_daily_exposure_pct: rules
                    .get("max_daily_exposure_pct")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(100.0),
                pos_pct: rules
                    .get("position_pct")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(10.0),
                slippage_bps: rules
                    .get("slippage_bps")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(5.0),
            }
        })
        .collect())
}

// ═══════════════════════════════════════════════════════════════════════════════
// DB insertion
// ═══════════════════════════════════════════════════════════════════════════════

async fn insert_signals(pool: &PgPool, signals: &[SignalRow], run_id: Uuid) -> Result<usize> {
    // Fetch simulated accounts only. Backtests must never mutate real accounts.
    let accounts: Vec<(Uuid, Uuid, f64)> = sqlx::query_as(
        "SELECT id, strategy_id, current_equity::float8
         FROM accounts
         WHERE account_type = 'simulated'",
    )
    .fetch_all(pool)
    .await?;

    // Build a local mutable equity map so later trades size from updated equity.
    let mut acct_map: HashMap<Uuid, Vec<(Uuid, f64)>> = HashMap::new();
    for (acct_id, strat_id, equity) in accounts {
        acct_map
            .entry(strat_id)
            .or_default()
            .push((acct_id, equity));
    }

    let mut ordered: Vec<&SignalRow> = signals.iter().collect();
    ordered.sort_by(|a, b| {
        a.signal_date
            .cmp(&b.signal_date)
            .then(a.strategy_id.cmp(&b.strategy_id))
            .then(a.ticker.cmp(&b.ticker))
    });

    let mut inserted = 0usize;
    let mut day_exposure: HashMap<(Uuid, String), f64> = HashMap::new();

    for chunk in ordered.chunks(500) {
        let mut tx = pool.begin().await?;
        for s in chunk {
            let Some(accounts) = acct_map.get_mut(&s.strategy_id) else {
                continue;
            };

            for (acct_id, equity) in accounts.iter_mut() {
                let intended_position_size = *equity * s.pos_pct / 100.0;
                let max_daily_exposure = *equity * s.max_daily_exposure_pct / 100.0;
                let day_key = (*acct_id, s.signal_date.clone());
                let already_used = *day_exposure.get(&day_key).unwrap_or(&0.0);
                let remaining_daily_capacity = (max_daily_exposure - already_used).max(0.0);

                let position_size = intended_position_size
                    .min(s.liquidity_cap_brl)
                    .min(remaining_daily_capacity);

                if position_size < s.min_position_brl {
                    continue;
                }

                let pnl = position_size * s.net_return_pct / 100.0;
                let capacity_used_pct = if s.liquidity_cap_brl > 0.0
                    && s.liquidity_cap_brl < UNBOUNDED_LIQUIDITY_CAP_BRL
                {
                    position_size / s.liquidity_cap_brl * 100.0
                } else {
                    0.0
                };
                // Use the actual closing price as exit; PnL is still from net_return_pct
                let exit_price = s.close_price;

                sqlx::query(
                    "INSERT INTO trades
                     (id, account_id, strategy_id, trade_date, ticker,
                      entry_price, exit_price, gap_pct, signal,
                      gross_return_pct, net_return_pct, pnl, position_size,
                      status, source, backtest_run_id,
                      intended_position_size, liquidity_cap_brl, capacity_used_pct)
                     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                             'executed','backtest',$14,$15,$16,$17)
                     ON CONFLICT DO NOTHING",
                )
                .bind(Uuid::new_v4())
                .bind(*acct_id)
                .bind(s.strategy_id)
                .bind(&s.signal_date)
                .bind(&s.ticker)
                .bind(s.open_price)
                .bind(exit_price)
                .bind(s.gap_pct)
                .bind(&s.signal_type)
                .bind(s.gross_return_pct)
                .bind(s.net_return_pct)
                .bind(pnl)
                .bind(position_size)
                .bind(run_id)
                .bind(intended_position_size)
                .bind(s.liquidity_cap_brl)
                .bind(capacity_used_pct)
                .execute(&mut *tx)
                .await?;

                sqlx::query(
                    "UPDATE accounts
                     SET current_equity = current_equity + $1,
                         num_trades     = num_trades + 1,
                         updated_at     = NOW()
                     WHERE id = $2",
                )
                .bind(pnl)
                .bind(*acct_id)
                .execute(&mut *tx)
                .await?;

                day_exposure.insert(day_key, already_used + position_size);
                *equity += pnl;
                inserted += 1;
            }
        }
        tx.commit().await?;
    }

    // Update run trade count
    sqlx::query(
        "UPDATE backtest_runs SET total_trades = (
             SELECT COUNT(*)::int4 FROM trades WHERE backtest_run_id = $1)
         WHERE id = $1",
    )
    .bind(run_id)
    .execute(pool)
    .await?;

    Ok(inserted)
}

// ═══════════════════════════════════════════════════════════════════════════════
// Public API — orchestration
// ═══════════════════════════════════════════════════════════════════════════════

pub async fn run_for_years(pool: Arc<PgPool>, mut years: Vec<i32>, job_id: Uuid) -> Result<usize> {
    // Mark job as running
    sqlx::query("UPDATE backtest_jobs SET status='running', started_at=NOW() WHERE id=$1")
        .bind(job_id)
        .execute(pool.as_ref())
        .await?;

    years.sort_unstable();

    let s3 = S3Cfg::from_env()
        .context("AWS credentials not set (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)")?;
    let strategies = fetch_active_strategies(pool.as_ref()).await?;

    if strategies.is_empty() {
        bail!("No active strategies found");
    }
    tracing::info!(
        count = strategies.len(),
        "Running backtest for {} strategies",
        strategies.len()
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .build()?;

    // Full rerun semantics: clear previous backtest artifacts and reset only
    // simulated accounts. Real/live accounts are not touched.
    sqlx::query("DELETE FROM trades WHERE source = 'backtest'")
        .execute(pool.as_ref())
        .await?;
    sqlx::query("DELETE FROM backtest_runs")
        .execute(pool.as_ref())
        .await?;
    sqlx::query(
        "UPDATE accounts
         SET current_equity = initial_capital,
             num_trades = 0,
             win_rate = 0,
             sharpe_ratio = 0,
             cumulative_return = 0,
             updated_at = NOW()
         WHERE account_type = 'simulated'",
    )
    .execute(pool.as_ref())
    .await?;

    let mut total_inserted = 0usize;

    for &year in &years {
        let prefix = format!("raw/b3_cotahist/COTAHIST_A{year}/{year}/");
        tracing::info!(year, "Listing COTAHIST keys");

        let keys = list_keys(&client, &s3, &prefix)
            .await
            .with_context(|| format!("list keys for {year}"))?;

        if keys.is_empty() {
            tracing::warn!(year, "No COTAHIST files found — skipping");
            continue;
        }

        let latest_key = keys.last().unwrap();
        tracing::info!(year, key = latest_key.as_str(), "Downloading COTAHIST");

        let zip_bytes = get_object(&client, &s3, latest_key)
            .await
            .with_context(|| format!("download {latest_key}"))?;

        tracing::info!(year, bytes = zip_bytes.len(), "Parsing COTAHIST");
        let ohlcv =
            parse_cotahist_zip(&zip_bytes).with_context(|| format!("parse {latest_key}"))?;

        tracing::info!(year, rows = ohlcv.len(), "Computing gaps and features");
        let gapped = compute_gaps(ohlcv);

        tracing::info!(year, gapped = gapped.len(), "Evaluating strategies");
        let mut signals: Vec<SignalRow> = Vec::new();
        for row in &gapped {
            for strat in &strategies {
                if let Some(sig) = evaluate_signal(row, strat) {
                    signals.push(sig);
                }
            }
        }
        tracing::info!(year, signals = signals.len(), "Generated signals");

        // Create a named backtest run for this year
        let run_name = format!("Auto backtest {year}");
        let run_id: Uuid = sqlx::query_scalar(
            "INSERT INTO backtest_runs (name, params) VALUES ($1, $2) RETURNING id",
        )
        .bind(&run_name)
        .bind(serde_json::json!({ "year": year, "job_id": job_id.to_string() }))
        .fetch_one(pool.as_ref())
        .await?;

        let n = insert_signals(pool.as_ref(), &signals, run_id)
            .await
            .with_context(|| format!("insert signals for {year}"))?;

        tracing::info!(year, inserted = n, "Inserted backtest trades");
        total_inserted += n;
    }

    // Mark job completed
    sqlx::query(
        "UPDATE backtest_jobs
         SET status='completed', completed_at=NOW(), total_trades=$2
         WHERE id=$1",
    )
    .bind(job_id)
    .bind(total_inserted as i32)
    .execute(pool.as_ref())
    .await?;

    Ok(total_inserted)
}

/// Called at startup: if any active strategy has 0 backtest trades, kick off a full run.
pub async fn auto_seed_if_needed(pool: Arc<PgPool>) {
    let needs_seed: bool = sqlx::query_scalar(
        "SELECT EXISTS (
             SELECT 1 FROM strategies s
             WHERE s.active = true
               AND NOT EXISTS (
                   SELECT 1 FROM trades t
                   WHERE t.strategy_id = s.id AND t.source = 'backtest'
               )
         )",
    )
    .fetch_one(pool.as_ref())
    .await
    .unwrap_or(false);

    if !needs_seed {
        tracing::info!("Backtest data already present — skipping auto-seed");
        return;
    }

    tracing::info!("No backtest data found — starting automatic backtest...");

    let years = {
        let y = chrono::Utc::now().year();
        vec![y - 1, y] // prior year + current year
    };

    let job_id: Uuid = match sqlx::query_scalar(
        "INSERT INTO backtest_jobs (status, years_run) VALUES ('pending', $1) RETURNING id",
    )
    .bind(&years)
    .fetch_one(pool.as_ref())
    .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("Could not create backtest job: {e}");
            return;
        }
    };

    let pool2 = pool.clone();
    tokio::spawn(async move {
        match run_for_years(pool2, years.clone(), job_id).await {
            Ok(n) => tracing::info!(trades = n, "Auto-backtest completed"),
            Err(e) => {
                tracing::error!("Auto-backtest failed: {e}");
                let _ = sqlx::query(
                    "UPDATE backtest_jobs SET status='failed', completed_at=NOW(), error_message=$2 WHERE id=$1",
                )
                .bind(job_id)
                .bind(e.to_string())
                .execute(pool.as_ref())
                .await;
            }
        }
    });
}
