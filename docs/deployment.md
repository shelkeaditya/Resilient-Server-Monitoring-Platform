# Deployment guide

This guide turns the quick start into a permanent setup:

```
Internet ──► nginx (:80 / :443, password, TLS) ──► waitress (127.0.0.1:5000) ──► Server Monitor
```

Commands assume Ubuntu 24.04 (nginx 1.24) and a normal user with `sudo`. Examples use `/opt/monitor`, port `5000`, the domain `monitor.example.com` and the login `admin`. Replace them with your own values and keep them consistent: **the port in the systemd unit and the port in the nginx `proxy_pass` line must match.**

**Contents**

1. [Install the application](#1-install-the-application)
2. [Run it as a systemd service](#2-run-it-as-a-systemd-service)
3. [Install nginx and create a login](#3-install-nginx-and-create-a-login)
4. [Option A: HTTP site](#4-option-a-http-site)
5. [Open the firewall](#5-open-the-firewall)
6. [Option B: HTTPS with Let's Encrypt](#6-option-b-https-with-lets-encrypt)
7. [Option C: no nginx, use an SSH tunnel](#7-option-c-no-nginx-use-an-ssh-tunnel)
8. [Security checklist](#8-security-checklist)
9. [Day-to-day operations](#9-day-to-day-operations)

---

## 1. Install the application

```bash
sudo apt update
sudo apt install -y python3 python3-venv git curl
sudo git clone https://github.com/shelkeaditya/Resilient-Server-Monitoring-Platform.git /opt/monitor
sudo chown -R "$USER": /opt/monitor
cd /opt/monitor

python3 -m venv venv
source venv/bin/activate
pip install -r app/requirements.txt
```

Confirm the vendored Chart.js is a real JavaScript file and not a saved error page:

```bash
ls -l app/static/vendor/chart.umd.min.js        # roughly 200 KB
head -c 60 app/static/vendor/chart.umd.min.js    # begins with a /*! Chart.js comment
```

If it is missing or tiny, download it again:

```bash
mkdir -p app/static/vendor
curl -L https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js \
     -o app/static/vendor/chart.umd.min.js
```

## 2. Run it as a systemd service

systemd keeps the monitor running after you log out, restarts it if it crashes, and starts it at boot. It runs under **waitress**, a production WSGI server.

Create `/etc/systemd/system/monitor.service`. Adjust the user and the three `/opt/monitor` paths.

```ini
[Unit]
Description=Server Monitor
After=network.target
RequiresMountsFor=/opt/monitor

[Service]
User=ubuntu
WorkingDirectory=/opt/monitor/app
ExecStart=/opt/monitor/venv/bin/waitress-serve --listen=127.0.0.1:5000 --threads=2 --call app:create_app
Restart=on-failure
RestartSec=5
MemoryMax=150M
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

What the important lines do:

| Line | Why |
|---|---|
| `--listen=127.0.0.1:5000` | Loopback only. Never change this to `0.0.0.0`, because nginx is the public entry point. |
| `--call app:create_app` | Tells waitress to call the app factory in `app/app.py`. |
| `RequiresMountsFor=` | Waits for the disk that holds the project. Delete this line if the project is on the root disk. |
| `MemoryMax=150M` | Safety cap. The service normally uses about 25 MB. |
| `User=` | The service runs as an ordinary user, never as root. |

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now monitor
systemctl status monitor --no-pager        # should say active (running)
sleep 5; curl -s http://127.0.0.1:5000/healthz    # {"ok":true}
```

To change settings such as the sampling interval, add `Environment=MONITOR_INTERVAL=5` lines under `[Service]`, then run `sudo systemctl daemon-reload && sudo systemctl restart monitor`. See [configuration.md](configuration.md).

## 3. Install nginx and create a login

```bash
sudo apt install -y nginx apache2-utils
sudo htpasswd -c /etc/nginx/.monitor_htpasswd admin
```

- nginx is a system package. Its files live in `/usr/sbin/nginx`, `/etc/nginx` and `/var/log/nginx`, on the system disk and not in your project folder.
- Choose a long, unique password (16 or more characters).
- Use `-c` only the first time, because it creates the file. To add or change a user later, run the same command without `-c`.

## 4. Option A: HTTP site

Use this for testing or on a private network. **Plain HTTP sends your password unencrypted.** For anything reachable from the internet, use [Option B](#6-option-b-https-with-lets-encrypt).

Create `/etc/nginx/sites-available/monitor`:

```nginx
server {
    listen 80;
    server_name _;
    server_tokens off;

    auth_basic "Monitor";
    auth_basic_user_file /etc/nginx/.monitor_htpasswd;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 10s;
    }
}
```

Enable it and check the syntax before reloading:

```bash
sudo ln -sf /etc/nginx/sites-available/monitor /etc/nginx/sites-enabled/monitor
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Test it on the server:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/                       # 401, login required
curl -s -u admin:YOUR_PASSWORD http://127.0.0.1/healthz                          # {"ok":true}
```

## 5. Open the firewall

Traffic has to be allowed in **two** places.

**Cloud firewall.** Add an ingress rule for TCP port `80` (and `443` for HTTPS). Depending on your provider this is a Security List or Network Security Group (Oracle Cloud), a Security Group (AWS) or a Network Security Group (Azure). While you use plain HTTP, restrict the source to your own public IP with a `/32` suffix.

**Server firewall.** Ubuntu images on Oracle Cloud use iptables with a final `REJECT` rule. Your `ACCEPT` rules must sit **above** it, because rules are read top to bottom and anything after `REJECT` is never reached.

```bash
sudo iptables -L INPUT -n --line-numbers                      # note the line number of the REJECT rule, e.g. 5
sudo iptables -I INPUT 5 -p tcp --dport 80  -j ACCEPT         # use that number
sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
sudo iptables -L INPUT -n --line-numbers                      # both ACCEPT lines must appear above REJECT
sudo apt install -y iptables-persistent                       # accept the prompts
sudo netfilter-persistent save                                # survive a reboot
```

Using `ufw` instead? Run `sudo ufw allow 80/tcp` and `sudo ufw allow 443/tcp`.

Check from your own computer (PowerShell shown):

```powershell
Test-NetConnection YOUR_SERVER_IP -Port 80
```

`TcpTestSucceeded : True` means the path is open. `False` means the cloud rule is missing or the iptables order is wrong.

## 6. Option B: HTTPS with Let's Encrypt

You need a domain name that points at the server.

**1. Create a DNS record.** Add an `A` record, for example `monitor.example.com`, pointing to the server's public IP. Verify it:

```bash
dig +short monitor.example.com        # prints your server IP
```

If `dig` is missing, use `getent hosts monitor.example.com`.

**2. Open ports 80 and 443 to everyone** (`0.0.0.0/0`) in the cloud firewall. Let's Encrypt validates from many addresses, so a single-IP rule would make issuance fail. The password and TLS protect the dashboard from here on.

**3. Stage one: HTTP config used to get the certificate.** Replace the contents of `/etc/nginx/sites-available/monitor`:

```nginx
server {
    listen 80;
    server_name monitor.example.com;
    server_tokens off;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
        auth_basic off;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}
```

```bash
sudo apt install -y certbot
sudo mkdir -p /var/www/html
sudo nginx -t && sudo systemctl reload nginx

sudo certbot certonly --webroot -w /var/www/html \
  -d monitor.example.com \
  --email you@example.com --agree-tos --no-eff-email \
  --deploy-hook "systemctl reload nginx"
```

It should end with "Successfully received certificate".

**4. Stage two: the final HTTPS config.** Replace the file again:

```nginx
limit_req_zone $binary_remote_addr zone=monitor:1m rate=10r/s;

server {
    listen 80;
    server_name monitor.example.com;
    server_tokens off;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
        auth_basic off;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name monitor.example.com;
    server_tokens off;

    ssl_certificate     /etc/letsencrypt/live/monitor.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/monitor.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    add_header Strict-Transport-Security "max-age=31536000" always;

    auth_basic "Monitor";
    auth_basic_user_file /etc/nginx/.monitor_htpasswd;
    limit_req zone=monitor burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 10s;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> **nginx version note.** The line `listen 443 ssl http2;` works on nginx 1.24, which Ubuntu 24.04 ships. From nginx 1.25.1 the newer form is a separate `http2 on;` directive, and the old form still works but prints a deprecation warning. Do not use `http2 on;` on 1.24, because it fails with `unknown directive "http2"`. Check your version with `nginx -v`.

**5. Verify.**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://monitor.example.com/    # 401
curl -s -o /dev/null -w "%{http_code}\n" http://monitor.example.com/     # 301
sudo certbot renew --dry-run                                             # auto-renewal works
```

Open `https://monitor.example.com` and log in. Certbot installs a timer that renews the certificate automatically and reloads nginx afterwards.

## 7. Option C: no nginx, use an SSH tunnel

If you are the only user, you do not need nginx, a firewall change or a password. Forward the port over SSH while you want to look at the dashboard:

```bash
ssh -L 5000:127.0.0.1:5000 youruser@YOUR_SERVER_IP
# then browse to http://localhost:5000 while this session stays open
```

With PuTTY, set this under Connection, SSH, Tunnels: source port `5000`, destination `127.0.0.1:5000`, then click Add.

## 8. Security checklist

- [ ] The service listens on `127.0.0.1` only, and the app port is not open in any firewall.
- [ ] nginx requires a password (`auth_basic`) and the password is long and unique.
- [ ] HTTPS is on for anything reachable from the internet.
- [ ] The service runs as a normal user, not root.
- [ ] Debug mode is off. The Werkzeug debugger allows remote code execution.
- [ ] `.htpasswd` and `.env` files are not committed to git.
- [ ] Consider `fail2ban` for repeated failed logins on public servers.
- [ ] Remember the dashboard shows the host name, OS, kernel and interface IP addresses. That is a reason to keep it behind a login.

The app also sends a Content-Security-Policy, `X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy` headers by itself.

## 9. Day-to-day operations

**reload or restart nginx?** Use `reload` after changing nginx config, the password file or the certificate. It applies changes without dropping connections. Use `restart` only if a reload does not fix the problem.

```bash
sudo nginx -t && sudo systemctl reload nginx
```

**Restart the monitor** after code or settings changes. You do not need to touch nginx for that.

```bash
sudo systemctl restart monitor
journalctl -u monitor -n 50 --no-pager      # recent logs
journalctl -u monitor -f                    # follow live
```

**Update to a newer version:**

```bash
cd /opt/monitor
git pull
source venv/bin/activate
pip install -r app/requirements.txt
pytest verification -q                      # needs: pip install pytest
sudo systemctl restart monitor
```

Then hard-refresh the browser with `Ctrl+Shift+R` so it drops the cached CSS and JavaScript.

**Roll back:**

```bash
git log --oneline -5
git checkout <previous-commit>
sudo systemctl restart monitor
```

For problems, see [troubleshooting.md](troubleshooting.md).
