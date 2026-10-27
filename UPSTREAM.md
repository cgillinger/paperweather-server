# Upstream

*Maintainer notes.* This repository was created from the author's private project `eink_weather_2` (Raspberry Pi e-ink weather display plus a web version). You do not need that project to use paperweather-server; this file only records where the code came from and what was changed.

**Source of truth:** [cgillinger/eink_weather_2](https://github.com/cgillinger/eink_weather_2) (private at the time of writing).

**Based on:** commit `478a7c4` (2026-08-20), branch `main`. No upstream history is included.

## Rule

Upstream is the source of truth for weather logic, rendering and the module/provider system. Bugs and features in that area are fixed upstream first, then carried over here. Changes specific to this edition (below) live only here.

## Removed vs upstream (Raspberry Pi only)

- `main.py`, `main_daemon.py`, `install_daemon.sh`, `systemd/`, `restart.py`, `screenshot.py`, `get-pip.py`, `web_server.py`
- `waveshare_epd/` (display stub)
- One-off scripts and tests: `smhi_wind_test.py/.sh`, `test_gust_triggers.py`, `tests/`, `convert_svg_high_res.py`
- Stale/long docs: `readme.md`, `updated_readme.md`, `module_switching_architecture.md`, `docs/`
- `requirements_web.txt` (replaced by `requirements.txt`)

## Changed vs upstream

- `modules/module_manager.py` (new): `TriggerEvaluator` and `DynamicModuleManager` extracted unchanged from `main_daemon.py`; `main_web.py` imports them from here instead of the daemon.
- `modules/sun_calculator.py`: simplified fallback replaced by the NOAA solar algorithm (stdlib only, `zoneinfo`, `TZ` env var, default `Europe/Stockholm`). Without an ipgeolocation key this is the normal path and not logged as a warning. Polar day/night is handled without errors.
- `main_web.py`: the status box shows data source and observation station when no Netatmo battery data exists (previously empty).
- `modules/weather_client.py`: missing Netatmo credentials are logged at info level, not warning.
- New: `Dockerfile`, `compose.yaml`, `.dockerignore`, `requirements.txt`, `config.example.json`, `README.md`, `UPSTREAM.md`.

## Kept as is

`modules/` (SMHI and Yr providers, renderers, icon manager, weather client), `templates/`, `fonts/`, `icons/`, `weather-icons-master/`, `smhi_stationer.md`, `smhi_stationer_instruktion.md`, `pressure-descriptions.md`.

## Licensing note

Upstream has no license file. This repository is released under The Unlicense (public domain) by the same author, 2026-10-27.
