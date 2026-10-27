> **Downstream project** — server/Docker edition of [cgillinger/eink_weather_2](https://github.com/cgillinger/eink_weather_2) (private repository). Upstream contains both the Raspberry Pi e-ink daemon (`main_daemon.py`) and the original web version (`main_web.py`); this repo is a standalone copy of the web version only. Weather logic lives upstream; fix bugs there first, then carry them over.

# paperweather-server

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)
![Platform](https://img.shields.io/badge/platform-Synology%20%7C%20Docker%20%7C%20Linux-lightgrey)
![Data](https://img.shields.io/badge/data-SMHI%20%7C%20Yr-green)
![Netatmo](https://img.shields.io/badge/Netatmo-optional-orange)

A small web server that renders an **800×480 black-and-white weather image**, the same layout as the e-ink station, and serves it over HTTP. Use it for:

- e-ink clients or ESP32/Pi displays that fetch a PNG on a schedule,
- a wall tablet or phone browser (landscape),
- anything that can show an image from a URL.

It runs on a NAS or any Docker host — **no Raspberry Pi, no Waveshare display and no Netatmo station required**. Netatmo is an optional extra.

Data sources: SMHI (forecast and observations) or Yr/MET Norway, UV index from currentuvindex.com (no key), sunrise/sunset calculated locally (NOAA algorithm, no key needed). Optional: Netatmo (home weather station) and ipgeolocation.io (sun times via API).

> **License:** the upstream project has no license file, so none is granted here either. This repository is published for transparency and personal use; no license has been invented. Bundled third-party material keeps its own license (Weather Icons: SIL OFL 1.1 / MIT, see `weather-icons-master/README.md`; DejaVu Sans font).

## Endpoints

| Path | Description |
|------|-------------|
| `/` | HTML page showing the image (auto-refreshing, tap to refresh) |
| `/weather.png` | The 800×480 PNG |
| `/api/weather` | Current weather data as JSON |
| `/api/refresh` | `POST` — force a data refresh and re-render |

Default port: **8037**.

## Install on Synology (Container Manager)

Requires DSM 7.2+ with **Container Manager** installed. These steps are written so you can follow them yourself or hand them to an AI assistant.

1. **Create a folder** on the NAS, e.g. `/docker/paperweather-server`, using File Station.
2. **Get the project into that folder.** Either download this repository as a ZIP and extract it there, or `git clone` it over SSH. The folder must contain `Dockerfile`, `compose.yaml`, `main_web.py`, `modules/`, `templates/`, `fonts/` and `icons/`.
3. **Create your config.** Copy `config.example.json` to `config.json` in the same folder (File Station: copy and rename). Edit it:
   - `location`: your place name, latitude and longitude (see [Configuration](#configuration)).
   - `smhi_observations`: your nearest SMHI station (see `smhi_stationer.md`).
   - Leave `api_keys` empty for SMHI-only mode.
4. **Create the project.** Container Manager → *Project* → *Create*:
   - Project name: `paperweather-server`
   - Path: the folder from step 1
   - Source: *Use existing docker-compose.yml* (it detects `compose.yaml`; if the wizard insists on that name, rename the file to `docker-compose.yml`).
5. Click through the wizard and **build/start** the project. The first build downloads Python and the dependencies and takes a few minutes.
6. **Check it works.** Open `http://<nas-ip>:8037/` in a browser — you should see the weather image within about 10–20 seconds of start. `http://<nas-ip>:8037/weather.png` is the raw image.
7. **Firewall (if enabled):** allow TCP 8037 from your local network only. Do not expose this port to the internet.

If something fails, open the container's *Log* tab in Container Manager. A missing or invalid `config.json` is the most common cause (the file must exist before the container starts, otherwise Docker creates a directory with that name — delete it and create the file).

Plain Docker works the same way: `docker compose up -d --build` in the project folder.

### What the compose file does

- Publishes port `8037`.
- Mounts `./config.json` read-only at `/app/config.json`.
- Keeps cache and logs in the named volume `paperweather-data` (mounted at `/data`).
- Sets `TZ=Europe/Stockholm` (clock, date and sunrise/sunset use this) and `restart: unless-stopped`.
- Runs as a non-root user.

Change `TZ` in `compose.yaml` if you live elsewhere.

## Configuration

Everything is in `config.json` (start from `config.example.json`; keys starting with `_comment` are notes and ignored).

- **Location** (`location`): name shown on the display, `latitude`, `longitude` in decimal degrees. Sunrise/sunset is calculated from these.
- **Provider** (`weather_provider`): `smhi` for Sweden (default, best tested) or `yr` for anywhere in the world.
- **SMHI observation station** (`smhi_observations`): used for "has it rained recently?" and shown in the status box when Netatmo is off. Pick the nearest station from `smhi_stationer.md` (ready-made list per city) or follow `smhi_stationer_instruktion.md` (in Swedish) to find one. Set `primary_station_id`/`primary_station_name` and a reserve in `fallback_station_*`. Only meaningful in Sweden.
- **Netatmo (optional)**: under `api_keys.netatmo` fill `client_id`, `client_secret`, `refresh_token` (create an app at <https://dev.netatmo.com>). With all three empty, Netatmo is disabled and the status box shows data source and station instead of battery levels.
- **ipgeolocation.io (optional)**: put a key in `api_keys.ipgeolocation` to fetch sun times from the API. Without it, sun times are calculated locally and are accurate to about a minute.
- **Layout, modules, triggers**: inherited from upstream; leave as is unless you know what you are changing. Restart the container after editing `config.json`.

Keep `config.json` private — it may contain API credentials and is excluded from git and from the Docker image.

## Updating

```bash
cd /path/to/paperweather-server
git pull            # or replace the folder contents with a new ZIP; keep your config.json
docker compose up -d --build
```

On Synology: Container Manager → Project → select the project → *Action* → *Build*, then start. Your `config.json` and the data volume are kept.

Weather logic comes from upstream — see [UPSTREAM.md](UPSTREAM.md) for how changes are carried over.

## Running without Docker

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json   # edit
python main_web.py                    # http://localhost:8037
```

Cache and logs go to `./cache` and `./logs` relative to where you start it.
