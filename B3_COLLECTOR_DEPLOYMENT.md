# B3 Collector Railway Deployment

Deployed: 2026-06-08

## Railway

```text
Project: b3-public-data-collector
Project ID: 9839bfe7-907e-4d6a-8b72-c139229ede79
Service: b3-collector
Service ID: 73425949-4b37-4890-be05-7daf67c622cc
Environment: production
Volume: b3-collector-volume
Volume mount: /data
Railway bucket: b3-public-data-lake
Bucket ID: 55f27472-aa88-41e8-a806-bd8869f52247
Bucket region: iad
```

## Runtime env

```text
B3_DATA_DIR=/data/b3_lake
COLLECT_INTERVAL_MINUTES=360
B3_BACKFILL_DAYS=10
B3_MAX_RETRIES=4
B3_REQUEST_TIMEOUT=90
B3_ENABLE_INDEX_API=1
B3_ENABLE_PESQUISA=1
B3_ENABLE_COTAHIST=1
```

## First successful run

Deployment:

```text
af35559c-9fe7-4e9f-9f72-9f46501a78de
```

Summary:

```json
{
  "started_at": "2026-06-08T23:02:28.558134Z",
  "sources": {
    "index_api": {"artifacts": 212, "seconds": 38.92},
    "pesquisa_pregao": {"artifacts": 138, "seconds": 506.35},
    "cotahist": {"artifacts": 2, "seconds": 126.46}
  },
  "finished_at": "2026-06-08T23:13:40.282035Z"
}
```

Total first-run artifacts: **352**.

A few errors were logged, expected for some public files/endpoints that are not available every day or for every index.

## Useful commands

```bash
railway status
railway logs --service b3-collector --deployment --tail 300
railway variables
railway service restart b3-collector
```

## Railway bucket mirror

Configured via Railway Buckets using S3-compatible credentials.

```text
B3_S3_BUCKET=b3-public-data-lake
B3_S3_ENDPOINT_URL=https://t3.storageapi.dev
AWS_DEFAULT_REGION=auto
B3_S3_ADDRESSING_STYLE=virtual
```

Smoke test deployment uploaded 8 IBOV artifacts successfully. Bucket after smoke test:

```text
objects: 180
storage: 1.3 MB
```

Current clean daemon deployment:

```text
eaabaaf9-1e0c-4261-b5e2-5f102d1bfd34
status: SUCCESS
mode: broad daemon, RUN_ONCE=0, all sources enabled
```
