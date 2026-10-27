# paperweather-server

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)
![Platform](https://img.shields.io/badge/platform-Synology%20%7C%20Docker%20%7C%20Linux-lightgrey)
![Data](https://img.shields.io/badge/data-SMHI%20%7C%20Yr-green)
![Netatmo](https://img.shields.io/badge/Netatmo-valfritt-orange)
![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue)

> **In English:** paperweather-server draws a weather dashboard as an 800×480 black-and-white PNG for e-ink screens and serves it over HTTP (Docker, runs on a NAS). The text on the image is **Swedish only** and the default data source (SMHI) covers Sweden; the Yr provider works worldwide. No API keys required. Public domain ([Unlicense](LICENSE)).

En liten webbserver som ritar en **väderpanel som en svartvit bild på 800×480 pixlar** och visar den via HTTP. Den är gjord för e-ink-skärmar (e-papper), som bara kan visa svart och vitt och uppdateras långsamt, men fungerar på vilken skärm som helst som kan visa en bild.

Allt som behövs finns i det här repot. Servern körs på en NAS eller annan Docker-värd — **ingen Raspberry Pi, ingen särskild skärmhårdvara, inga API-nycklar och ingen egen väderstation behövs**.

![Exempel](docs/example.png)

Bilden visar:

- **Aktuellt väder** för din plats: temperatur, vädersymbol och beskrivning, soluppgång och solnedgång samt UV-index.
- **Vind**: medelvind i m/s med byvind inom parentes, beskrivning och riktning.
- **I morgon**: prognos för temperatur och väder.
- **Datum** och en **statusruta** med tid för senaste uppdatering och datakälla.

Bilden ritas om var tionde minut.

Användning:

- e-ink- eller andra små skärmar (till exempel ESP32-baserade) som hämtar en PNG med jämna mellanrum,
- en surfplatta på väggen eller en mobil i liggande läge,
- allt som kan visa en bild från en URL.

> **Licens:** public domain via [The Unlicense](LICENSE) — använd, kopiera, ändra och sälj fritt, utan krav på att ange källa. Medföljande material från tredje part har kvar sina egna licenser: Weather Icons (SIL OFL 1.1 / MIT, se `weather-icons-master/README.md`) och typsnittet DejaVu Sans (Bitstream Vera-licens).

## Datakällor

| Källa | Vad | Nyckel | Täckning |
|-------|-----|--------|----------|
| [SMHI](https://www.smhi.se) | Prognos och senaste observationer | Nej | Sverige (standard) |
| [Yr / MET Norway](https://api.met.no) | Prognos (alternativ till SMHI) | Nej | Hela världen |
| [currentuvindex.com](https://currentuvindex.com) | UV-index | Nej | Hela världen |
| Beräknas lokalt | Soluppgång och solnedgång (NOAA-algoritm, rätt på ungefär en minut) | Nej | Hela världen |
| [Netatmo](https://www.netatmo.com) *(valfritt)* | Mätvärden från din egen Netatmo-väderstation | Ja, din egen | Där du har en |
| [ipgeolocation.io](https://ipgeolocation.io) *(valfritt)* | Soltider från ett API i stället för lokal beräkning | Ja | Hela världen |

Utanför Sverige väljer du `yr` som källa. YR ger bara prognoser: "regnar nu" bygger då på prognosen för den närmaste timmen i stället för på mätningar från en SMHI-station. YR-läget är provkört (Oslo, 2026-10-27) men mindre beprövat än SMHI.

## Adresser

| Sökväg | Beskrivning |
|--------|-------------|
| `/` | HTML-sida som visar bilden (uppdateras automatiskt, tryck för att uppdatera) |
| `/weather.png` | PNG-bilden, 800×480 |
| `/api/weather` | Aktuell väderdata som JSON |
| `/api/refresh` | `POST` — tvinga fram ny hämtning och omritning |

Standardport: **8037**.

## Installera på Synology (Container Manager)

Kräver DSM 7.2 eller senare och paketet **Container Manager** (finns för Synology-modeller med x86- eller ARM64-processor; kolla i *Paketcenter*). Stegen är skrivna så att du kan följa dem själv eller lämna dem till en AI-assistent.

1. **Skapa en mapp** på NAS:en, t.ex. `/docker/paperweather-server`, med File Station.
2. **Lägg projektet i mappen.** Ladda antingen ner repot som ZIP (*Code* → *Download ZIP* på GitHub) och packa upp det där, eller kör `git clone` via SSH. Mappen ska innehålla `Dockerfile`, `compose.yaml`, `main_web.py`, `modules/`, `templates/`, `fonts/` och `icons/`.
3. **Skapa din config.** Kopiera `config.example.json` till `config.json` i samma mapp (File Station: kopiera och byt namn). Redigera:
   - `location`: ortnamn, latitud och longitud (se [Inställningar](#inställningar)).
   - `smhi_observations`: närmaste SMHI-station (se `smhi_stationer.md`).
   - Lämna `api_keys` tomt — inga nycklar behövs.
4. **Skapa projektet.** Container Manager → *Projekt* → *Skapa*:
   - Projektnamn: `paperweather-server`
   - Sökväg: mappen från steg 1
   - Källa: *Använd befintlig docker-compose.yml* (den hittar `compose.yaml`; om guiden kräver det namnet, byt namn på filen till `docker-compose.yml`).
5. Klicka dig igenom guiden och **bygg/starta** projektet. Första bygget laddar ner Python och beroenden och tar några minuter.
6. **Kontrollera att det fungerar.** Öppna `http://<nas-ip>:8037/` i en webbläsare — bilden ska synas inom 10–20 sekunder efter start. `http://<nas-ip>:8037/weather.png` är själva bilden.
7. **Brandvägg (om den är på):** tillåt TCP 8037 från ditt lokala nätverk. Öppna inte porten mot internet.

Om något går fel: öppna fliken *Logg* för containern i Container Manager. Vanligaste orsaken är att `config.json` saknas eller är felaktig (filen måste finnas innan containern startar, annars skapar Docker en mapp med det namnet — ta bort mappen och skapa filen).

Med vanlig Docker fungerar det likadant: `docker compose up -d --build` i projektmappen.

> Synology-stegen följer Container Managers projektguide men är inte testade på alla DSM-versioner. Skiljer sig något steg på din NAS, öppna gärna ett issue.

### Vad compose-filen gör

- Publicerar port `8037`.
- Monterar `./config.json` skrivskyddad som `/app/config.json`.
- Sparar cache och loggar i volymen `paperweather-data` (monterad på `/data`).
- Sätter `TZ=Europe/Stockholm` (klocka, datum och soltider använder den) och `restart: unless-stopped`. Bor du i en annan tidszon, ändra `TZ` i `compose.yaml` (t.ex. `Europe/Oslo`).
- Kör som en användare utan root-rättigheter.

## Inställningar

Allt ställs in i `config.json` (utgå från `config.example.json`; nycklar som börjar med `_comment` är anteckningar och ignoreras). Starta om containern efter ändringar.

- **Plats** (`location`): namnet som visas på bilden samt `latitude` och `longitude` i decimalgrader (slå upp platsen på en karta). Soltiderna räknas ut från dessa.
- **Källa** (`weather_provider`): `smhi` för Sverige (standard, mest testat) eller `yr` för hela världen.
- **SMHI-observationsstation** (`smhi_observations`): används för "har det regnat senaste timmen?" och visas i statusrutan. Välj närmaste station i `smhi_stationer.md` (stations-id för större svenska städer) eller följ `smhi_stationer_instruktion.md` för att hitta en var som helst i Sverige. Ange `primary_station_id`/`primary_station_name` och en reserv i `fallback_station_*`. Med `yr` används inte stationen, så exempelvärdena kan stå kvar.
- **Netatmo (valfritt)**: bara om du har en Netatmo-väderstation. Skapa en app på <https://dev.netatmo.com>, generera en token med behörigheten `read_station` i appens token-generator och fyll i `client_id`, `client_secret` och `refresh_token` under `api_keys.netatmo`. Temperatur, lufttryck och regn hämtas då från din egen station och statusrutan visar dess batterinivåer. Lämna alla tre tomma för att stänga av Netatmo.
- **ipgeolocation.io (valfritt)**: lägg en nyckel i `api_keys.ipgeolocation` för att hämta soltider från det API:et. Behövs inte — utan nyckel räknas soltiderna ut lokalt.
- **Layout, moduler, triggers**: styr vilka rutor som visas och när (t.ex. ersätts vindrutan av en nederbördsruta när regn väntas). Låt dem vara om du inte vill experimentera.

Håll `config.json` privat om du lägger in nycklar — den är undantagen från git och från Docker-avbildningen.

## Uppdatera

```bash
cd /sökväg/till/paperweather-server
git pull            # eller ersätt mappens innehåll med en ny ZIP; behåll din config.json
docker compose up -d --build
```

På Synology: Container Manager → Projekt → välj projektet → *Åtgärd* → *Bygg*, starta sedan. Din `config.json` och datavolymen behålls.

## Köra utan Docker

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json   # redigera
python main_web.py                    # http://localhost:8037
```

Cache och loggar hamnar i `./cache` och `./logs` relativt mappen du startar från.

## Ursprung

Layouten gjordes först för en fysisk väderskärm — en Raspberry Pi med en 4,26-tums e-ink-skärm från Waveshare — i upphovspersonens privata projekt `eink_weather_2`. Det projektet har också en webbversion som ritar samma bild; **paperweather-server är en fristående, publik kopia av den webbversionen**, paketerad för Docker. Originalprojektet behövs inte till något. Anteckningar om hur de två hålls i takt finns i [UPSTREAM.md](UPSTREAM.md) (på engelska).

Buggar och frågor: öppna ett issue i det här repot.
