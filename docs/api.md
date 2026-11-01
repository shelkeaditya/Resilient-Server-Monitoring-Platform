# API reference

All endpoints are `GET` and return JSON with `Cache-Control: no-store`. Behind nginx they need the same login as the dashboard. Examples use the foreground address `http://127.0.0.1:5000`.

| Endpoint | Purpose |
|---|---|
| `GET /` | The dashboard (HTML) |
| `GET /healthz` | Liveness check |
| `GET /api/v1/snapshot` | Latest sample plus health evaluation |
| `GET /api/v1/history` | Recent samples for the charts |

## `GET /healthz`

Returns `200 {"ok": true}` when the collector has produced a recent sample, and `503 {"ok": false}` when it has not (for example while starting, or if the collector thread stopped). Use it for uptime checkers.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/healthz
```

## `GET /api/v1/snapshot`

The newest sample, with a `health` block added. While the first sample is still being collected the response is `{"status": "starting"}`.

```bash
curl -s http://127.0.0.1:5000/api/v1/snapshot | python3 -m json.tool
```

### Top-level fields

| Field | Meaning |
|---|---|
| `status` | `ok` once a sample exists |
| `collected_at` | Unix time the sample was taken |
| `interval` | Sampling interval in seconds |
| `age_seconds` | How old the sample is right now |
| `stale` | `true` if the sample is older than 3 times the interval |
| `cpu`, `memory`, `disks`, `network`, `interfaces`, `uptime`, `system` | Metric sections (below) |
| `health` | Evaluated status (below) |

Every section has `status` set to `ok` or `error`. If a value cannot be measured, it is `null`. Rates (`*_bps`, `*_iops`) are `null` in the very first sample, because a rate needs two readings.

### Example (trimmed)

```json
{
  "status": "ok",
  "collected_at": 1793462633.31,
  "interval": 3.0,
  "age_seconds": 1.8,
  "stale": false,
  "cpu": {
    "status": "ok", "percent": 4.2, "cores": 2, "per_core": [3.1, 5.3],
    "load1": 0.12, "load5": 0.10, "load15": 0.09,
    "user_percent": 3.0, "system_percent": 1.0, "iowait_percent": 0.1, "steal_percent": 0.0,
    "psi_some_avg10": 0.0, "source": "psutil"
  },
  "memory": {
    "status": "ok", "total": 998000000, "available": 700000000, "used": 298000000, "percent": 29.9,
    "cached": 0, "buffers": 0,
    "swap_total": 6442450944, "swap_used": 2717696, "swap_percent": 0.04,
    "swap_in_bps": 0.0, "swap_out_bps": 0.0, "psi_some_avg10": 0.0
  },
  "disks": {
    "status": "ok",
    "mounts": [{ "mount": "/", "device": "/dev/sda1", "fstype": "ext4", "total": 47000000000,
                 "used": 9400000000, "free": 35000000000, "percent": 20.0,
                 "inode_percent": 1.7, "aliases": ["/tmp", "/var/tmp"] }],
    "devices": [{ "name": "sda", "read_bps": 0.0, "write_bps": 331000.0,
                  "read_iops": 0.0, "write_iops": 14.7, "busy_percent": 1.0 }],
    "read_bps": 0.0, "write_bps": 331000.0, "io_psi_some_avg10": 0.0
  },
  "network": { "status": "ok", "rx_bps": 666.0, "tx_bps": 3880.0, "rx_total": 90000000, "tx_total": 300000 },
  "interfaces": {
    "status": "ok",
    "interfaces": [{ "name": "ens3", "is_up": true, "mtu": 9000, "speed_mbps": null, "ipv4": ["10.0.0.64"],
                     "rx_bps": 0.0, "tx_bps": 0.0, "rx_total": 0, "tx_total": 0,
                     "rx_errors": 0, "tx_errors": 0, "rx_drops": 0, "tx_drops": 0 }]
  },
  "uptime": { "status": "ok", "seconds": 87100.0 },
  "system": {
    "status": "ok", "hostname": "berserk", "os": "Ubuntu 24.04.5 LTS", "kernel": "7.0.0-1013-oracle",
    "arch": "x86_64", "cpu_model": "AMD EPYC 7551 32-Core Processor",
    "cores_logical": 2, "cores_physical": 1, "boot_time": 1793400000.0
  },
  "health": {
    "overall": "ok",
    "counts": { "ok": 11, "warn": 0, "crit": 0, "unknown": 0 },
    "items": [{ "id": "cpu", "label": "CPU usage", "level": "ok", "value": 4.2, "unit": "%",
                "message": "4% of capacity", "threshold": [75.0, 90.0] }]
  }
}
```

### The `health` block

| Field | Meaning |
|---|---|
| `overall` | `ok`, `warn`, `crit` or `unknown`. The worst level among measurable indicators. |
| `counts` | How many indicators are at each level |
| `items[].id` | `cpu`, `steal`, `load`, `memory`, `swap`, `disk`, `inode`, `psi_cpu`, `psi_memory`, `psi_io`, `collection` |
| `items[].level` | `ok`, `warn`, `crit` or `unknown` (not measurable) |
| `items[].value`, `unit` | The measurement behind the level |
| `items[].message` | A short human-readable explanation |
| `items[].threshold` | `[warning, critical]` used for the level, when applicable |

### Quick scripting examples

```bash
# Overall health as a single word
curl -s http://127.0.0.1:5000/api/v1/snapshot | python3 -c "import sys,json; print(json.load(sys.stdin)['health']['overall'])"

# Only the indicators that are not ok
curl -s http://127.0.0.1:5000/api/v1/snapshot | python3 -c "
import sys, json
for i in json.load(sys.stdin)['health']['items']:
    if i['level'] != 'ok': print(i['label'], i['level'], i['message'])"
```

## `GET /api/v1/history`

Recent samples in a compact, column-oriented form. The dashboard loads it once when the page opens so that the charts are not empty after a reload.

```bash
curl -s http://127.0.0.1:5000/api/v1/history | python3 -m json.tool | head -30
```

```json
{
  "interval": 3.0,
  "max_points": 300,
  "count": 120,
  "cores": 2,
  "t": [1793462400.0, 1793462403.0],
  "series": {
    "cpu":    [3.1, 4.2],
    "mem":    [29.8, 29.9],
    "swap":   [0.04, 0.04],
    "load1":  [0.10, 0.12],
    "load5":  [0.10, 0.10],
    "load15": [0.09, 0.09],
    "net_rx": [500.0, 666.0],
    "net_tx": [3000.0, 3880.0],
    "disk_r": [0.0, 0.0],
    "disk_w": [0.0, 331000.0]
  }
}
```

Every array in `series` has exactly `count` entries, aligned with `t`. A missing measurement is `null`. `net_*` and `disk_*` are bytes per second. The history lives in memory, so it resets when the service restarts.

## Stability

The API is versioned in the path (`/v1`). Existing fields are not removed or renamed within a version. New fields may be added, so clients should ignore fields they do not recognise.
