# Configuration

Server Monitor is configured with environment variables and one thresholds table in the source code.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `MONITOR_INTERVAL` | `3` | Seconds between samples. The dashboard polls at the same rate. |
| `MONITOR_HISTORY` | `300` | Samples kept in memory for the charts. At 3 s, 300 samples is 15 minutes. The minimum is 10. |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MONITOR_HOST` | `127.0.0.1` | Bind address. Used **only** by `python app.py`. |
| `MONITOR_PORT` | `5000` | Port. Used **only** by `python app.py`. |

Under waitress (the systemd setup), the address and port come from the `--listen=` option in the service file, so `MONITOR_HOST` and `MONITOR_PORT` have no effect there.

### Setting them for the systemd service

Add `Environment=` lines under `[Service]` in `/etc/systemd/system/monitor.service`:

```ini
[Service]
Environment=MONITOR_INTERVAL=5
Environment=MONITOR_HISTORY=360
```

Then apply the change:

```bash
sudo systemctl daemon-reload
sudo systemctl restart monitor
```

A stale-data warning appears when no new sample has arrived for three times `MONITOR_INTERVAL`.

### Memory cost of history

Each history sample is a few hundred bytes, so the default of 300 samples uses well under 1 MB. Raising `MONITOR_HISTORY` to several thousand is still cheap, but the chart only draws what the browser receives, so very long windows make the charts denser, not more detailed.

## Health thresholds

Thresholds live in `DEFAULT_THRESHOLDS` in [`app/monitor/health.py`](../app/monitor/health.py). Each entry is a `(warning, critical)` pair, and a value **at or above** the number triggers that level.

| Indicator | Warning | Critical | What is measured |
|---|---|---|---|
| `cpu` | 75 | 90 | CPU busy, in % |
| `memory` | 80 | 90 | RAM in use, in %. Excludes reclaimable cache (`total - available`). |
| `swap` | 30 | 60 | Swap in use, in % |
| `disk` | 80 | 90 | Fullest filesystem, in % |
| `inode` | 80 | 90 | Fullest filesystem by inode use, in % |
| `load_per_core` | 1.0 | 2.0 | 1-minute load average divided by the number of vCPUs |
| `steal` | 10 | 25 | CPU time taken by the hypervisor, in % |
| `psi` | 10 | 25 | Time tasks were stalled waiting for CPU, memory or I/O (10 s average), in % |

Collector status is also an indicator: it becomes critical when no new sample has arrived for three times the interval, and a warning if any collector section fails.

To change a threshold, edit the file and restart the service:

```bash
nano app/monitor/health.py
sudo systemctl restart monitor
pytest verification -q        # the health tests still describe the expected behaviour
```

**How levels combine.** The overall status is the worst level among the indicators that could be measured. An indicator whose data is unavailable is `unknown`, which is shown separately and never counts as healthy.

## What is shown and what is hidden

| Area | Included | Excluded |
|---|---|---|
| Filesystems | `ext4`, `xfs`, `btrfs`, `zfs` | Other types (for example `vfat` for `/boot/efi`, `tmpfs`) |
| Bind mounts | Reported once per device, using the shortest mount path, with a `+N` tag for the others | The duplicate rows |
| Network interfaces | All real interfaces | Loopback and virtual ones, with names starting `lo`, `docker`, `veth`, `br-`, `cni`, `flannel`, `cali`, `virbr` |
| Disk devices | Whole disks (`sda`, `vdb`, `nvme0n1`) | `loop*`, `ram*`, and partitions, which are counted under their parent disk |

These lists are the constants `REAL_FS`, `SKIP_NIC` and `SKIP_DISK` at the top of [`app/monitor/collector.py`](../app/monitor/collector.py).

## Files that are not configuration

- `/etc/nginx/.monitor_htpasswd` holds the dashboard logins. Manage it with `htpasswd` (see [deployment.md](deployment.md)).
- `/etc/systemd/system/monitor.service` controls how the service starts.
