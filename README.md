# Server Monitor

**A lightweight, real-time monitoring dashboard for a single Linux server.** It reads genuine metrics with `psutil` and `/proc`, judges their health on the server, and shows them in a fast dark-theme web UI. Built to run comfortably on a 1 GB VPS.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.1-black)
![psutil](https://img.shields.io/badge/psutil-7.2-informational)
![nginx](https://img.shields.io/badge/Reverse%20proxy-nginx-009639)

<img width="1898" height="977" alt="image" src="https://github.com/user-attachments/assets/41a18724-325d-4416-8c52-8b03da6ebff2" />

Why it exists: Prometheus plus Grafana is a great stack, but it costs more memory than a small VPS can spare. Server Monitor is one small Python process with no database and no frontend build step.

**Design rules:** real data only (a test fails if `Math.random` ever appears in the frontend), a metric that cannot be measured is shown as "—" instead of a made-up zero, and the app binds to `127.0.0.1` with nginx in front.

## Features

- **Health overview:** overall status, per-indicator messages, and kernel resource-pressure meters.
- **Live metrics:** CPU (overall and per core), memory, swap, disk and inodes, disk I/O per device, network rates per interface, load average and uptime.
- **Charts:** CPU, memory and swap, system load, network and disk throughput. They survive a page reload because the server keeps 15 minutes of history.
- **System details:** OS, kernel, CPU model, filesystems, disk devices and network interfaces.
- **Honest states:** loading, stale-data and disconnected banners. `/healthz` returns `503` if the collector stops.
- **Light on resources:** about 25 MB of RAM for the service. Mobile-friendly and keyboard accessible.
- **Verified:** a 45-test suite checks values against `/proc`, `/sys` and the OS ([details](docs/testing.md)).

## Quick start

Try it in the foreground. This takes about a minute and needs no root access after the packages.

```bash
sudo apt install -y python3 python3-venv git
git clone https://github.com/shelkeaditya/Resilient-Server-Monitoring-Platform.git
cd Resilient-Server-Monitoring-Platform

python3 -m venv venv && source venv/bin/activate
pip install -r app/requirements.txt

cd app && python app.py
```

In a second terminal on the same machine:

```bash
curl -s http://127.0.0.1:5000/healthz        # {"ok":true}  (give it a few seconds after start)
```

Open `http://127.0.0.1:5000` in a browser. On a remote server, forward the port over SSH and browse to `http://localhost:5000`:

```bash
ssh -L 5000:127.0.0.1:5000 youruser@YOUR_SERVER_IP
```

`python app.py` is for trying things out. For real use, follow [Deployment](#deployment).

## Requirements

| | |
|---|---|
| OS | Linux. Tested on Ubuntu 24.04. |
| Python | 3.12 (tested) |
| Packages | `flask`, `psutil`, `waitress`, pinned in [`app/requirements.txt`](app/requirements.txt) |
| nginx | Optional, recommended for a password and HTTPS |

The monitor is read-only and does not need root.

## Deployment

For a permanent setup, run it as a systemd service behind nginx:

1. **systemd service** keeps it running, restarts it after a crash and starts it at boot, using waitress instead of Flask's development server.
2. **nginx reverse proxy** adds a password and optional HTTPS, and forwards requests to `127.0.0.1`.
3. **Firewall** rules for ports 80 and 443, both at your cloud provider and on the server.
4. **HTTPS** with a free Let's Encrypt certificate (needs a domain name).

The full step-by-step guide is in **[docs/deployment.md](docs/deployment.md)**.

> Never expose the app port directly. The app has no login of its own, so nginx provides the authentication.

## Configuration

Set these as environment variables (for systemd, as `Environment=` lines).

| Variable | Default | Meaning |
|---|---|---|
| `MONITOR_INTERVAL` | `3` | Seconds between samples |
| `MONITOR_HISTORY` | `300` | Samples kept for the charts (300 at 3 s is 15 minutes) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `MONITOR_HOST` / `MONITOR_PORT` | `127.0.0.1` / `5000` | Bind address, used only by `python app.py` |

Health thresholds are defined in `app/monitor/health.py`. See **[docs/configuration.md](docs/configuration.md)** for the full list.

## Usage and API

| Endpoint | Purpose |
|---|---|
| `GET /` | The dashboard |
| `GET /healthz` | `200 {"ok":true}` if the collector is fresh, otherwise `503` |
| `GET /api/v1/snapshot` | Latest metrics plus the health evaluation |
| `GET /api/v1/history` | Recent samples used by the charts |

```bash
curl -s http://127.0.0.1:5000/api/v1/snapshot | python3 -m json.tool | head -20
```

Field-by-field reference and examples: **[docs/api.md](docs/api.md)**.

## Architecture

```
Browser ──► nginx (password, TLS) ──► waitress ──► Flask app ──► sampler thread (psutil, /proc)
                                                        │               │
                                                        └─ health.py ◄──┴─ latest snapshot + history buffer
```

One background thread samples the host every few seconds and keeps the latest snapshot and a bounded history. A pure function turns the snapshot into ok, warning or critical levels. The page polls the API and draws charts with a vendored copy of Chart.js, so there is no CDN dependency. Details and design decisions: **[docs/architecture.md](docs/architecture.md)**.

## Testing

```bash
source venv/bin/activate
pip install pytest
pytest verification -v
```

The suite includes live checks against the real machine, so run it on a Linux host. What each test proves: **[docs/testing.md](docs/testing.md)**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser shows **502 Bad Gateway** | The `proxy_pass` port in nginx does not match the service port, or the service is down. Check `systemctl status monitor`. |
| Browser times out | Open the port at both the cloud firewall and the server firewall. The iptables `ACCEPT` rule must sit above `REJECT`. |
| Login keeps reappearing | Wrong password. Reset it with `sudo htpasswd /etc/nginx/.monitor_htpasswd admin` (no `-c`). |
| Every value shows "—" | Check the browser console (F12). A 404 on a `/static/` file means a missing file. |
| "Stale data" banner | The collector stopped. Read `journalctl -u monitor -n 50`. |

More cases and diagnostic commands: **[docs/troubleshooting.md](docs/troubleshooting.md)**.

## Project layout

```
app/
  app.py                  Flask routes and security headers
  requirements.txt
  monitor/collector.py    Sampler thread, metrics, history buffer
  monitor/health.py       Threshold evaluation
  templates/dashboard.html
  static/css, js, vendor  Styles, scripts, vendored Chart.js
verification/             Test suite
docs/                     Guides
```

## Contributing

1. Fork the repository and create a branch: `git checkout -b feature/your-change`.
2. Make your change and run `pytest verification -q`. All tests should pass.
3. Open a pull request describing what changed and why.

Please keep to the project rules: no simulated data, no unnecessary dependencies, and low memory use.

## License

See the [LICENSE](LICENSE) file.

## Author

**Aditya Shelke** · [GitHub](https://github.com/shelkeaditya) · [LinkedIn](https://linkedin.com/in/shelkeaditya)
