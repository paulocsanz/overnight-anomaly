#!/usr/bin/env python3
"""Broad B3 public-data collector for Railway.

Goals:
- collect raw B3 data moving forward, not just IBOV;
- be redundant: retry, backfill recent days every run, store raw bytes + metadata;
- be storage-backend agnostic: local disk plus optional S3/R2 mirror;
- never parse destructively: raw-first data lake, parse later for algos.

Main sources collected:
1) B3 hidden index API: day/theoretical/preview/config portfolios for many indices.
2) B3 Pesquisa por Pregao daily files: SecurityList, Instruments, PriceReport,
   IndexReport, simplified equity/derivatives reports, fee/risk/public files, etc.
3) B3 COTAHIST yearly official historical quotes for current/prior years.

Railway usage:
  python b3_data_collector.py               # daemon loop
  RUN_ONCE=1 python b3_data_collector.py    # one run

Optional S3/R2 mirror env:
  B3_S3_BUCKET=...
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  AWS_DEFAULT_REGION=auto
  B3_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import random
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = os.getenv(
    "B3_USER_AGENT",
    "Mozilla/5.0 (compatible; PauloB3Collector/1.0; +https://railway.app)",
)
DATA_DIR = Path(os.getenv("B3_DATA_DIR", "/data/b3_lake"))
MANIFEST = DATA_DIR / "manifest.jsonl"
ERROR_LOG = DATA_DIR / "errors.jsonl"
RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
INTERVAL_MINUTES = int(os.getenv("COLLECT_INTERVAL_MINUTES", "360"))
BACKFILL_DAYS = int(os.getenv("B3_BACKFILL_DAYS", "10"))
REQUEST_TIMEOUT = int(os.getenv("B3_REQUEST_TIMEOUT", "90"))
MAX_RETRIES = int(os.getenv("B3_MAX_RETRIES", "4"))
ENABLE_INDEX_API = os.getenv("B3_ENABLE_INDEX_API", "1") == "1"
ENABLE_PESQUISA = os.getenv("B3_ENABLE_PESQUISA", "1") == "1"
ENABLE_COTAHIST = os.getenv("B3_ENABLE_COTAHIST", "1") == "1"

B3_INDEX_API = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/"
PESQUISA_URL = "https://www.b3.com.br/pesquisapregao/download?filelist={filelist}"
COTAHIST_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"

# Broad set of B3 indices. Some endpoints may return empty for some names; keep them
# because the goal is broad collection.
DEFAULT_INDEX_CODES = [
    "IBOV", "IBXX", "IBXL", "IBRA", "IBRX", "SMLL", "MLCX", "IDIV", "IVBX",
    "IGCX", "IGCT", "IGNM", "ITAG", "ISEE", "ICO2", "UTIL", "IFNC", "ICON",
    "IMOB", "INDX", "IEEX", "IMAT", "BDRX", "IFIX", "IFIL", "GPTW", "AGFS",
]
INDEX_CODES = [x.strip().upper() for x in os.getenv("B3_INDEX_CODES", ",".join(DEFAULT_INDEX_CODES)).split(",") if x.strip()]

# Pesquisa por Pregao file patterns discovered from B3 page. We backfill recent
# dates every run to catch late publication and missed days.
DEFAULT_PESQUISA_PATTERNS = [
    # Core market/reference files
    "SecurityList{YYMMDD}.zip",     # Tradable Security List
    "IN{YYMMDD}.zip",               # Instruments File BVBG.028.02
    "II{YYMMDD}.zip",               # Indicator instruments
    "PR{YYMMDD}.zip",               # PriceReport BVBG.086.01
    "SPRE{YYMMDD}.zip",             # Simplified Price Report - Equities
    "SPRD{YYMMDD}.zip",             # Simplified Price Report - Derivatives
    "IR{YYMMDD}.zip",               # IndexReport BVBG.087.01
    # Risk/liquidity/fees/reference
    "AI{YYMMDD}.zip", "FP{YYMMDD}.zip", "FR{YYMMDD}.zip",
    "LD{YYMMDD}.zip", "LA{YYMMDD}.zip", "PG{YYMMDD}.zip",
    "DI{YYMMDD}.zip", "UN{YYMMDD}.zip", "VA{YYMMDD}.zip", "TX{YYMMDD}.zip",
    # FX / derivatives / option refs / fixed income public files
    "CT{YYMMDD}.zip", "CV{YYMMDD}.zip", "CN{YYMMDD}.zip", "GL{YYMMDD}.zip",
    "ID{YYMMDD}.ex_", "PE{YYMMDD}.ex_", "RE{YYMMDD}.ex_", "MM{YYMMDD}.ex_",
    "TS{YYMMDD}.ex_", "PU{YYMMDD}.ex_", "RF{YYMMDD}.ex_",
]
PESQUISA_PATTERNS = [x.strip() for x in os.getenv("B3_PESQUISA_PATTERNS", ",".join(DEFAULT_PESQUISA_PATTERNS)).split(",") if x.strip()]

INDEX_METHODS = {
    "portfolio_day": "GetPortfolioDay",
    "portfolio_theoretical": "GetTheoricalPortfolio",
    "portfolio_preview": "GetQuartelyPreview",
    "configurations": "GetConfigurations",
}
INDEX_DOWNLOAD_METHODS = {
    "download_day": "GetDownloadPortfolioDay",
    "download_theoretical": "GetDownloadPortfolioTheorical",
    "download_preview": "GetDownloadPreview",
    "download_segment": "GetDownloadPortfolioSegment",
}


@dataclass
class Artifact:
    source: str
    dataset: str
    logical_date: str
    url: str
    path: str
    bytes: int
    sha256: str
    content_type: str | None
    status: str
    collected_at: str
    extra: dict[str, Any]


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def ssl_context():
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "raw").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "state").mkdir(parents=True, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_bytes(data)
    tmp.replace(path)


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def log_error(where: str, err: BaseException, extra: dict[str, Any] | None = None) -> None:
    append_jsonl(ERROR_LOG, {
        "ts": iso_now(),
        "where": where,
        "error": repr(err),
        "traceback": traceback.format_exc(),
        "extra": extra or {},
    })


def request_bytes(url: str, *, accept: str = "*/*") -> tuple[bytes, dict[str, str]]:
    last: BaseException | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": accept,
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ssl_context()) as r:
                data = r.read()
                headers = {k.lower(): v for k, v in r.headers.items()}
                return data, headers
        except urllib.error.HTTPError as e:
            # 404/403 generally means the public file/endpoint is not available;
            # retrying just burns collector time.
            if e.code in (400, 401, 403, 404):
                raise
            last = e
            sleep = min(60, (2 ** (attempt - 1)) + random.random())
            time.sleep(sleep)
        except Exception as e:  # noqa: BLE001
            last = e
            sleep = min(60, (2 ** (attempt - 1)) + random.random())
            time.sleep(sleep)
    assert last is not None
    raise last


def b64_json(obj: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def is_empty_zip(data: bytes) -> bool:
    # B3 sometimes returns an empty zip for bad/missing filelist.
    if len(data) <= 64 and data.startswith(b"PK\x05\x06"):
        return True
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as z:
            return len(z.namelist()) == 0
    except Exception:
        return False


def maybe_upload_s3(local_path: Path, key: str) -> dict[str, Any]:
    bucket = os.getenv("B3_S3_BUCKET")
    if not bucket:
        return {"s3_uploaded": False}
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
        endpoint = os.getenv("B3_S3_ENDPOINT_URL") or None
        style = os.getenv("B3_S3_ADDRESSING_STYLE", "virtual")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            config=Config(s3={"addressing_style": style}),
        )
        client.upload_file(str(local_path), bucket, key)
        if os.getenv("B3_LOG_S3_UPLOADS", "0") == "1":
            print(f"s3_uploaded bucket={bucket} key={key} bytes={local_path.stat().st_size}", flush=True)
        return {"s3_uploaded": True, "s3_bucket": bucket, "s3_key": key, "s3_addressing_style": style}
    except Exception as e:  # noqa: BLE001
        print(f"s3_upload_failed key={key} error={e!r}", flush=True)
        log_error("s3_upload", e, {"path": str(local_path), "key": key})
        return {"s3_uploaded": False, "s3_error": repr(e)}


def store_artifact(
    *,
    source: str,
    dataset: str,
    logical_date: str,
    url: str,
    data: bytes,
    ext: str,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Artifact:
    collected_at = iso_now()
    digest = sha256_bytes(data)
    safe_dataset = dataset.replace("/", "_")
    safe_date = logical_date.replace("/", "-")
    ts = collected_at.replace(":", "").replace("-", "").replace(".", "")
    rel = Path("raw") / source / safe_dataset / safe_date / f"{ts}_{digest[:12]}.{ext.lstrip('.')}"
    path = DATA_DIR / rel
    atomic_write(path, data)
    s3_extra = maybe_upload_s3(path, str(rel))
    artifact = Artifact(
        source=source,
        dataset=dataset,
        logical_date=logical_date,
        url=url,
        path=str(path),
        bytes=len(data),
        sha256=digest,
        content_type=(headers or {}).get("content-type"),
        status="ok",
        collected_at=collected_at,
        extra={**(extra or {}), **s3_extra},
    )
    append_jsonl(MANIFEST, asdict(artifact))
    return artifact


def collect_url(source: str, dataset: str, logical_date: str, url: str, ext: str, *, min_bytes: int = 1, extra=None) -> Artifact | None:
    try:
        data, headers = request_bytes(url)
        if len(data) < min_bytes:
            raise ValueError(f"too small: {len(data)} bytes")
        if data.startswith(b"PK") and is_empty_zip(data):
            # Record as skipped in manifest? For noise control, log only.
            append_jsonl(MANIFEST, {
                "source": source, "dataset": dataset, "logical_date": logical_date,
                "url": url, "bytes": len(data), "status": "empty_zip_skip",
                "collected_at": iso_now(), "extra": extra or {},
            })
            return None
        return store_artifact(source=source, dataset=dataset, logical_date=logical_date, url=url, data=data, ext=ext, headers=headers, extra=extra)
    except Exception as e:  # noqa: BLE001
        log_error("collect_url", e, {"source": source, "dataset": dataset, "logical_date": logical_date, "url": url})
        return None


def collect_index_api() -> list[Artifact]:
    artifacts: list[Artifact] = []
    for index in INDEX_CODES:
        payload = {"pageNumber": 1, "pageSize": 500, "language": "pt-br", "index": index}
        for dataset, method in INDEX_METHODS.items():
            url = B3_INDEX_API + method + "/" + b64_json(payload)
            art = collect_url("b3_index_api", f"{index}_{dataset}", now_utc().date().isoformat(), url, "json", min_bytes=2, extra={"index": index, "method": method, "payload": payload})
            if art:
                artifacts.append(art)
        for dataset, method in INDEX_DOWNLOAD_METHODS.items():
            dl_payload = {"index": index, "language": "pt-br"}
            url = B3_INDEX_API + method + "/" + b64_json(dl_payload)
            art = collect_url("b3_index_api", f"{index}_{dataset}", now_utc().date().isoformat(), url, "b64txt", min_bytes=2, extra={"index": index, "method": method, "payload": dl_payload})
            if art:
                artifacts.append(art)
    return artifacts


def yymmdd(d: dt.date) -> str:
    return d.strftime("%y%m%d")


def collect_pesquisa_pregao() -> list[Artifact]:
    artifacts: list[Artifact] = []
    today = now_utc().date()
    # Include tomorrow too because some B3 files are pre-open for the next session.
    dates = [today + dt.timedelta(days=1)] + [today - dt.timedelta(days=i) for i in range(BACKFILL_DAYS + 1)]
    for d in dates:
        yy = yymmdd(d)
        for pattern in PESQUISA_PATTERNS:
            fname = pattern.replace("{YYMMDD}", yy)
            url = PESQUISA_URL.format(filelist=fname)
            ext = fname.split(".")[-1] if "." in fname else "bin"
            dataset = pattern.replace("{YYMMDD}", "DATE")
            art = collect_url("b3_pesquisa_pregao", dataset, d.isoformat(), url, ext, min_bytes=20, extra={"filename": fname, "pattern": pattern})
            if art:
                artifacts.append(art)
    return artifacts


def collect_cotahist() -> list[Artifact]:
    artifacts: list[Artifact] = []
    current_year = now_utc().year
    start_year = 1986
    years = list(range(start_year, current_year + 1))
    for year in years:
        url = COTAHIST_URL.format(year=year)
        art = collect_url("b3_cotahist", f"COTAHIST_A{year}", str(year), url, "zip", min_bytes=1000, extra={"year": year})
        if art:
            artifacts.append(art)
    return artifacts


def collect_run() -> dict[str, Any]:
    ensure_dirs()
    started = iso_now()
    summary = {"started_at": started, "sources": {}, "errors_before": ERROR_LOG.exists() and sum(1 for _ in ERROR_LOG.open()) or 0}
    sources = []
    if ENABLE_INDEX_API:
        sources.append(("index_api", collect_index_api))
    if ENABLE_PESQUISA:
        sources.append(("pesquisa_pregao", collect_pesquisa_pregao))
    if ENABLE_COTAHIST:
        sources.append(("cotahist", collect_cotahist))
    for name, fn in sources:
        t0 = time.time()
        print(f"starting source={name}", flush=True)
        try:
            arts = fn()
            summary["sources"][name] = {"artifacts": len(arts), "seconds": round(time.time() - t0, 2)}
            print(f"finished source={name} artifacts={len(arts)} seconds={summary['sources'][name]['seconds']}", flush=True)
        except Exception as e:  # noqa: BLE001
            log_error(f"source_{name}", e)
            summary["sources"][name] = {"artifacts": 0, "seconds": round(time.time() - t0, 2), "error": repr(e)}
            print(f"failed source={name} error={e!r}", flush=True)
    summary["finished_at"] = iso_now()
    summary["errors_after"] = ERROR_LOG.exists() and sum(1 for _ in ERROR_LOG.open()) or 0
    append_jsonl(DATA_DIR / "runs.jsonl", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def main() -> int:
    ensure_dirs()
    print(f"B3 collector starting. DATA_DIR={DATA_DIR} RUN_ONCE={RUN_ONCE} interval={INTERVAL_MINUTES}m backfill={BACKFILL_DAYS}d index={ENABLE_INDEX_API} pesquisa={ENABLE_PESQUISA} cotahist={ENABLE_COTAHIST}", flush=True)
    while True:
        collect_run()
        if RUN_ONCE:
            return 0
        sleep_s = max(60, INTERVAL_MINUTES * 60)
        print(f"sleeping {sleep_s}s", flush=True)
        time.sleep(sleep_s)


if __name__ == "__main__":
    raise SystemExit(main())
