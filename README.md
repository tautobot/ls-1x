# livescores-8x

# Streamlit app

Introduce streamlit app

## Data store

Match data is stored in a local, in-process JSON file (`db.json` at the repo root) —
there is **no external JSON server** and no network dependency. The store is read and
written directly by `livescore/json_server.py` (via `livescore/jsondb.py`), which emulates the
json-server query/id semantics the app relies on.

- The file is auto-created (seeded as `{"1x": [], "8x": []}`) on first use if missing.
- The path is configurable via `JSON_DB_PATH` in `.env` (leave empty to use `<repo>/db.json`).
- Concurrent access from the Streamlit app and the sync service is made safe with
  file locking (`filelock`) plus atomic writes.

## Live-match sync (`sync_matches.py`)

Match data is produced **in-process** by a self-contained sync service — ls-1x runs
completely alone, with **no external json-server and no separate sync container**.

```
poetry run python sync_matches.py
```

What it does (`livescore/json_sync/`):

- **Fetches** live football matches from the bookmaker providers (`1xbet`, `8xbet`)
  over HTTP (`livescore/providers/`). The providers need no secrets — only base URLs.
- **Converts** each match to the exact autobet JSON shape the Streamlit app renders
  (`livescore/json_sync/converter.py`) — all values as strings, keyed on the `id` field.
- **Writes** directly into the in-process store (`livescore/jsondb.py`) via an async
  in-process client (`livescore/json_sync/local_client.py`), with upsert on POST and
  idempotent DELETE.
- A **finder loop** discovers new live matches; an **updater loop** updates them and
  robustly deletes ended matches (freeze-time / wall-clock / orphan detection). Both
  run concurrently in one process, so there is **no separate cleanup service**.

This supersedes the legacy `fetch_matches.py` + `delete_ended_matches.py` scripts
(now deprecated, retained for reference only) and their systemd units.

### Sync configuration (`.env`)

Provider settings use `SYNC_*` env names to avoid colliding with the legacy `X8_*`
vars (which the retired fetch code used). All have sensible defaults — override only
if a provider host changes:

| Env var | Default | Purpose |
|---|---|---|
| `SYNC_X1_BASE_URL` | `https://1xbet.mobi` | 1xbet API base URL |
| `SYNC_X8_BASE_URL` | `https://api.8xbet.com` | 8xbet API base URL |
| `SYNC_X8_ORIGIN` | `https://8xbet.com` | 8xbet origin header |
| `SYNC_X8_DOMAIN` | `api.8xbet.com` | 8xbet authority header |
| `SYNC_MATCH_FINDER_INTERVAL` | `30` | seconds between finder cycles |
| `SYNC_MATCH_UPDATER_INTERVAL` | `10` | seconds between updater cycles |
| `SYNC_LOG_LEVEL` | `INFO` | `DEBUG` => human-readable console logs |
| `SYNC_HTTP_PROXY` | _(unset)_ | route provider requests via a proxy when the host IP is blocked (see note) |
| `JSON_SYNC_SOURCE` | `1x` | store collection the service writes into |
| `EMBEDDED_SYNC` | `1` | run the sync in-process inside the Streamlit app (see below) |

> **Bookmaker IP blocking:** the providers fetch directly from the bookmaker APIs,
> which commonly **block datacenter IP ranges** — including Streamlit Community
> Cloud. If `db.json` stays empty on Cloud and the logs show `x1_http_error` /
> `x1_json_error` (a 403/451 or an HTML block page), the host IP is blocked. Set
> `SYNC_HTTP_PROXY` to an HTTP(S) proxy in an allowed region (Streamlit → Settings →
> Secrets: `SYNC_HTTP_PROXY = "http://user:pass@host:port"`), or run the sync from a
> host/region the bookmaker allows.

### How the sync runs — two modes

The same finder+updater loops can run either way; pick per host:

1. **In-process (default, `EMBEDDED_SYNC=1`)** — the Streamlit app starts the sync in a
   daemon background thread on first load (`livescore/json_sync/embedded.py`, wired into
   `app.py`), once per server process and supervised (auto-restarts if it ever exits).
   **This is what makes the app work on Streamlit Community Cloud**, which runs only
   `streamlit run` and cannot host a separate service. No extra config or secrets are
   needed — the committed `.env` plus built-in provider defaults are enough; the store
   populates within a second or two of the app loading. Note Community Cloud apps sleep
   when idle, so the sync runs while the app is awake (i.e. while someone is viewing it).

2. **Standalone service (`EMBEDDED_SYNC=0`)** — run `sync_matches.py` as its own process
   (systemd unit below) and set `EMBEDDED_SYNC=0` on the app so the two don't both write.
   Use this on a VM/always-on host where you want the sync running independently of viewers.

### Deployment

`devops/deploy.sh` installs/enables a single systemd unit `systemds/1xbet.sync.service`
running `sync_matches.py`, and retires the old `1xbet` / `1xbet.clean` units. The unit is
a template — its `__APP_HOME__` / `__VENV_PYTHON__` placeholders are substituted at install
time with the real clone path and the poetry virtualenv's python, so the service points at
the actual deploy location regardless of where the repo lives.

Because the sync service handles both discovery and ended-match cleanup, and its `run()`
fails fast (exits) if either internal loop dies, systemd's `Restart=always` cleanly relaunches
a healthy service on any unexpected crash.

## Install Python, Poetry
  
1. Install Python 3.10.11 or above
```
pyenv install 3.10.11
echo "3.10.11" >> .python-version
```
 
2. Install Poetry
```
pip install poetry
```

3. Configure project
```
cp .env-template .env
```
then install dependencies
```
poetry install
```
4. Run Streamlit app (stapp.py)
```
poetry shell
python -m streamlit run app.py
```

Configure Streamlit to Run on Public IP
```
mkdir -p ~/.streamlit
nano ~/.streamlit/config.toml
```

Add the following to the config.toml file:
```
[server]
headless = true
enableCORS = false
port = 8501
enableXsrfProtection = false
address = "0.0.0.0"
```

Allow Port 8501 Through Firewall
```
sudo ufw allow 8501
```

Run Streamlit app headless
```
nohup poetry run streamlit run app.py > app.log 2>&1 &
```

Kill streamlit process (if needed)
```
pkill -f "streamlit run"
```

Check streamlit process
```
ps aux | grep streamlit
```

Here’s How to Fix It on GCP

🔧 Step-by-Step: Open Port 8501 on GCP
	1.	Go to your Google Cloud Console
https://console.cloud.google.com/
	2.	Navigate to:
VPC network → Firewall
	3.	Click “Create Firewall Rule”
	4.	Fill in the form:
Name: streamlit
Target tags: streamlit
Allow 
    Targets: All instances in the network
    Source filter: IPv4 ranges
    Source IPv4 ranges: 0.0.0.0/0
    Protocol and ports:
        √ Specified protocols and ports
        √ TCP 
        Ports:8501


# NGINX
Optional: Setup with Domain + HTTPS (via Nginx + Let’s Encrypt)
Install Nginx
```
sudo apt install nginx -y
```

Set Up Reverse Proxy for Streamlit
Create a config file:
```
sudo nano /etc/nginx/sites-available/streamlit
```

Example config:
```
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the config file and restart nginx:
```
sudo ln -s /etc/nginx/sites-available/streamlit /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Set Up HTTPS (Let’s Encrypt)
```
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your_domain.com
```
