#!/usr/bin/env python3
"""
SunCalculator - sunrise/sunset times.

* With an ipgeolocation.io key (api_keys.ipgeolocation) the API is used, as in
  upstream (eink_weather_2).
* Without a key (the normal case for paperweather-server) times are computed
  locally with the NOAA solar algorithm (stdlib only), accurate to about a
  minute. Local time follows the TZ environment variable (default
  Europe/Stockholm).
"""

import os
import json
import time
import math
import requests
import logging
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Optional, Any

DEFAULT_TIMEZONE = "Europe/Stockholm"
ZENITH_DEG = 90.833  # official sunrise/sunset: refraction + solar disc radius


def get_local_tz():
    """Timezone from TZ env var, falling back to Europe/Stockholm."""
    for name in (os.environ.get("TZ"), DEFAULT_TIMEZONE):
        if not name:
            continue
        try:
            return ZoneInfo(name.lstrip(":"))
        except Exception:
            continue
    return timezone.utc


def _solar_params(jd: float):
    """Equation of time (minutes) and solar declination (radians) for a Julian day (NOAA)."""
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
         + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    seconds = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))
    obliq0 = 23.0 + (26.0 + seconds / 60.0) / 60.0
    obliq = obliq0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.asin(math.sin(math.radians(obliq)) * math.sin(math.radians(app_long)))
    y = math.tan(math.radians(obliq) / 2.0) ** 2
    l0r = math.radians(l0)
    eq_time = 4.0 * math.degrees(
        y * math.sin(2 * l0r) - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr))
    return eq_time, decl


def _event_utc_minutes(jd_midnight: float, lat: float, lon: float, rising: bool):
    """UTC minutes after 00:00 UTC of the day for sunrise/sunset.

    Returns a float, or the string 'day'/'night' when the sun never sets/rises.
    """
    minutes = 720.0 - 4.0 * lon  # first guess: solar noon
    for _ in range(3):  # iterate: solar parameters at the event time itself
        eq_time, decl = _solar_params(jd_midnight + minutes / 1440.0)
        lat_r = math.radians(lat)
        cos_ha = (math.cos(math.radians(ZENITH_DEG)) / (math.cos(lat_r) * math.cos(decl))
                  - math.tan(lat_r) * math.tan(decl))
        if cos_ha > 1.0:
            return "night"
        if cos_ha < -1.0:
            return "day"
        ha = math.degrees(math.acos(cos_ha))
        minutes = 720.0 - 4.0 * (lon + (ha if rising else -ha)) - eq_time
    return minutes


def calculate_sun_times(latitude: float, longitude: float, target_date: date, tz=None) -> Dict[str, Any]:
    """NOAA sunrise/sunset for a local calendar date.

    Returns {'sunrise': datetime, 'sunset': datetime, 'polar': None|'day'|'night'}.
    Polar day: sunrise 00:00, sunset 23:59:59. Polar night: sunrise == sunset == 12:00
    (zero daylight). Datetimes are naive local time, like datetime.now(),
    rounded to the nearest minute.
    """
    tz = tz or get_local_tz()
    result = {"polar": None}
    for key, rising in (("sunrise", True), ("sunset", False)):
        found = None
        for shift in (0, -1, 1):  # event may fall on a neighbouring UTC day
            d = target_date + timedelta(days=shift)
            jd_mid = d.toordinal() + 1721424.5  # Julian day at 00:00 UTC
            m = _event_utc_minutes(jd_mid, latitude, longitude, rising)
            if isinstance(m, str):
                result["polar"] = m
                break
            utc_dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(minutes=m)
            local = utc_dt.astimezone(tz)
            if local.date() == target_date:
                found = (local + timedelta(seconds=30)).replace(second=0, microsecond=0, tzinfo=None)
                break
        result[key] = found
    midnight = datetime.combine(target_date, datetime.min.time())
    if result["polar"] == "day":
        result["sunrise"], result["sunset"] = midnight, midnight.replace(hour=23, minute=59, second=59)
    elif result["polar"] == "night" or result["sunrise"] is None or result["sunset"] is None:
        noon = midnight.replace(hour=12)
        result["sunrise"], result["sunset"] = noon, noon
        result["polar"] = result["polar"] or "night"
    return result


class SunCalculator:
    """
    Beräknar exakta soltider med ipgeolocation.io API
    Baserad på Väderdisplay-projektets utils.py
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialisera SunCalculator
        
        Args:
            api_key: ipgeolocation.io API-nyckel, läses ur config.json
                     (api_keys.ipgeolocation). Utan nyckel hoppas soltider över.
        """
        self.api_key = api_key
        self.api_base_url = "https://api.ipgeolocation.io/astronomy"
        
        # Cache-konfiguration (24h cache som Väderdisplayen)
        self.cache_file = "cache/sun_cache.json"
        self.cache_duration_hours = 24
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Skapa cache-mapp om den inte finns
        cache_dir = os.path.dirname(self.cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        mode = "ipgeolocation.io API" if self.api_key else "local NOAA calculation (no API key)"
        print(f"☀️ SunCalculator initialised: {mode}")
    
    def get_sun_times(self, latitude: float, longitude: float, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Hämta exakta soltider för given plats och datum
        
        Args:
            latitude: Latitud (ex: 59.3293 för Stockholm)
            longitude: Longitud (ex: 18.0686 för Stockholm)
            target_date: Datum att hämta soltider för (default: idag)
            
        Returns:
            Dict med soldata: {
                'sunrise': '2025-07-24T03:27:15',
                'sunset': '2025-07-24T20:32:41',
                'sunrise_time': datetime-objekt,
                'sunset_time': datetime-objekt,
                'daylight_duration': '17h 5m',
                'source': 'ipgeolocation.io' eller 'fallback',
                'cached': True/False
            }
        """
        if target_date is None:
            target_date = date.today()
            
        # Kontrollera cache först
        cache_key = f"{latitude}_{longitude}_{target_date.isoformat()}"
        cached_data = self._get_cached_data(cache_key)
        
        if cached_data:
            self.logger.info(f"☀️ Använder cachade soltider för {target_date}")
            return cached_data
        
        # No API key: the local NOAA calculation is the normal path (cheap, not cached)
        if not self.api_key:
            self.logger.info("☀️ Using local NOAA sun calculation (no ipgeolocation key configured)")
            return self._calculate_fallback(latitude, longitude, target_date)

        # Try the API
        try:
            api_data = self._fetch_from_api(latitude, longitude, target_date)
            if api_data:
                self._save_to_cache(cache_key, api_data)
                self.logger.info(f"☀️ Nya soltider hämtade från API för {target_date}")
                return api_data

        except Exception as e:
            self.logger.warning(f"⚠️ API-fel för soltider: {e}")

        # API failed: fall back to the local calculation
        self.logger.warning("☀️ ipgeolocation API unavailable - using local NOAA calculation")
        fallback_data = self._calculate_fallback(latitude, longitude, target_date)
        fallback_data['cached'] = False
        self._save_to_cache(cache_key, fallback_data, cache_hours=2)
        return fallback_data

    def _fetch_from_api(self, latitude: float, longitude: float, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Hämta soltider från ipgeolocation.io API
        
        Args:
            latitude: Latitud
            longitude: Longitud  
            target_date: Datum
            
        Returns:
            Dict med API-data eller None vid fel
        """
        if not self.api_key:
            return None

        try:
            # Samma API-anrop som Väderdisplayen
            params = {
                'apiKey': self.api_key,
                'lat': latitude,
                'long': longitude,
                'date': target_date.isoformat()
            }
            
            self.logger.debug(f"🌐 API-anrop: {self.api_base_url} för {latitude}, {longitude}")
            
            response = requests.get(self.api_base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parsea API-svar
            if 'sunrise' in data and 'sunset' in data:
                return self._parse_api_response(data, target_date)
            else:
                self.logger.warning(f"⚠️ Ofullständig API-data: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ API-anropsfel: {e}")
            return None
        except (KeyError, ValueError) as e:
            self.logger.error(f"❌ API-parsningsfel: {e}")
            return None
    
    def _parse_api_response(self, api_data: Dict, target_date: date) -> Dict[str, Any]:
        """
        Parsea API-svar till standardformat
        
        Args:
            api_data: Rå API-data
            target_date: Datum
            
        Returns:
            Standardiserat soldata-dict
        """
        try:
            # API returnerar tider i format "03:27" eller "03:27:15"
            sunrise_str = api_data['sunrise']
            sunset_str = api_data['sunset']
            
            # Konvertera till full ISO-format med datum
            sunrise_time = self._parse_time_string(sunrise_str, target_date)
            sunset_time = self._parse_time_string(sunset_str, target_date)
            
            # Beräkna dagsljuslängd
            daylight_duration = self._calculate_daylight_duration(sunrise_time, sunset_time)
            
            return {
                'sunrise': sunrise_time.isoformat(),
                'sunset': sunset_time.isoformat(),
                'sunrise_time': sunrise_time,
                'sunset_time': sunset_time,
                'daylight_duration': daylight_duration,
                'source': 'ipgeolocation.io',
                'cached': False,
                'api_raw': api_data  # För debug
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fel vid parsning av API-data: {e}")
            raise
    
    def _parse_time_string(self, time_str: str, target_date: date) -> datetime:
        """
        Konvertera tidsträng från API till datetime-objekt
        
        Args:
            time_str: Tid från API (ex: "03:27" eller "03:27:15")
            target_date: Datum
            
        Returns:
            datetime-objekt
        """
        try:
            # Hantera olika format från API
            if len(time_str.split(':')) == 2:
                # Format: "03:27"
                hour, minute = map(int, time_str.split(':'))
                second = 0
            else:
                # Format: "03:27:15"
                hour, minute, second = map(int, time_str.split(':'))
            
            return datetime.combine(target_date, datetime.min.time().replace(
                hour=hour, minute=minute, second=second
            ))
            
        except Exception as e:
            self.logger.error(f"❌ Fel vid parsning av tid '{time_str}': {e}")
            # Fallback: midnatt
            return datetime.combine(target_date, datetime.min.time())
    
    def _calculate_daylight_duration(self, sunrise: datetime, sunset: datetime) -> str:
        """
        Beräkna dagsljuslängd i timmar och minuter
        
        Args:
            sunrise: Soluppgång datetime
            sunset: Solnedgång datetime
            
        Returns:
            Formaterad sträng (ex: "17h 5m")
        """
        try:
            duration = sunset - sunrise
            total_seconds = int(duration.total_seconds())
            
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            return f"{hours}h {minutes}m"
            
        except Exception as e:
            self.logger.error(f"❌ Fel vid beräkning av dagsljuslängd: {e}")
            return "N/A"
    
    def _calculate_fallback(self, latitude: float, longitude: float, target_date: date) -> Dict[str, Any]:
        """Local NOAA sunrise/sunset calculation (stdlib only)."""
        try:
            r = calculate_sun_times(latitude, longitude, target_date)
            sunrise_time, sunset_time = r['sunrise'], r['sunset']
            if r['polar'] == 'day':
                duration = "24h 0m"
            elif r['polar'] == 'night':
                duration = "0h 0m"
            else:
                duration = self._calculate_daylight_duration(sunrise_time, sunset_time)
            return {
                'sunrise': sunrise_time.isoformat(),
                'sunset': sunset_time.isoformat(),
                'sunrise_time': sunrise_time,
                'sunset_time': sunset_time,
                'daylight_duration': duration,
                'source': 'local-noaa',
                'polar': r['polar'],
                'cached': False
            }

        except Exception as e:
            self.logger.error(f"❌ Local sun calculation failed: {e}")
            now = datetime.now()
            sunrise_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
            sunset_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
            return {
                'sunrise': sunrise_time.isoformat(),
                'sunset': sunset_time.isoformat(),
                'sunrise_time': sunrise_time,
                'sunset_time': sunset_time,
                'daylight_duration': '12h 0m',
                'source': 'static_fallback',
                'cached': False
            }

    def _get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Hämta data från cache om tillgänglig och giltig
        
        Args:
            cache_key: Nyckel för cache-uppslagning
            
        Returns:
            Cachad data eller None
        """
        try:
            if not os.path.exists(self.cache_file):
                return None
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if cache_key not in cache_data:
                return None
            
            entry = cache_data[cache_key]
            
            # Kontrollera om cache är giltig
            cache_time = datetime.fromisoformat(entry['cached_at'])
            cache_age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            
            max_age = entry.get('cache_hours', self.cache_duration_hours)
            
            if cache_age_hours < max_age:
                # Konvertera tillbaka till datetime-objekt
                entry['data']['sunrise_time'] = datetime.fromisoformat(entry['data']['sunrise'])
                entry['data']['sunset_time'] = datetime.fromisoformat(entry['data']['sunset'])
                entry['data']['cached'] = True
                
                return entry['data']
            else:
                self.logger.debug(f"🗑️ Cache utgången för {cache_key} ({cache_age_hours:.1f}h)")
                return None
                
        except Exception as e:
            self.logger.warning(f"⚠️ Cache-läsningsfel: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any], cache_hours: Optional[int] = None):
        """
        Spara data i cache
        
        Args:
            cache_key: Nyckel för cache
            data: Data att cacha
            cache_hours: Cache-tid i timmar (default: 24h)
        """
        try:
            # Ladda befintlig cache
            cache_data = {}
            if os.path.exists(self.cache_file):
                try:
                    with open(self.cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                except:
                    cache_data = {}
            
            # Förbered data för JSON (ta bort datetime-objekt)
            json_data = data.copy()
            json_data.pop('sunrise_time', None)
            json_data.pop('sunset_time', None)
            
            # Lägg till cache-metadata
            cache_data[cache_key] = {
                'data': json_data,
                'cached_at': datetime.now().isoformat(),
                'cache_hours': cache_hours or self.cache_duration_hours
            }
            
            # Spara till fil
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
            self.logger.debug(f"💾 Soldata cachad för {cache_key}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Cache-sparningsfel: {e}")
    
    def clear_cache(self):
        """Rensa all cache"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                print("🗑️ Soldata-cache rensad")
            else:
                print("💭 Ingen cache att rensa")
        except Exception as e:
            self.logger.error(f"❌ Fel vid cache-rensning: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Få statistik om cache
        
        Returns:
            Dict med cache-info
        """
        try:
            if not os.path.exists(self.cache_file):
                return {'entries': 0, 'file_exists': False}
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Räkna giltiga vs utgångna entries
            now = datetime.now()
            valid_entries = 0
            expired_entries = 0
            
            for cache_key, entry in cache_data.items():
                try:
                    cache_time = datetime.fromisoformat(entry['cached_at'])
                    cache_age_hours = (now - cache_time).total_seconds() / 3600
                    max_age = entry.get('cache_hours', self.cache_duration_hours)
                    
                    if cache_age_hours < max_age:
                        valid_entries += 1
                    else:
                        expired_entries += 1
                except:
                    expired_entries += 1
            
            return {
                'entries': len(cache_data),
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'file_exists': True
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fel vid cache-statistik: {e}")
            return {'entries': 0, 'error': str(e)}


def test_sun_calculator():
    """Test SunCalculator med Stockholm-koordinater"""
    print("🧪 Testar SunCalculator...")

    # Nyckeln läses ur config.json — samma källa som daemonen använder
    api_key = None
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            api_key = json.load(f).get('api_keys', {}).get('ipgeolocation')
    except (OSError, ValueError) as e:
        print(f"⚠️ Kunde inte läsa config.json: {e}")
    if not api_key:
        print("⚠️ api_keys.ipgeolocation saknas i config.json — API-anrop hoppas över")

    # Skapa calculator
    sun_calc = SunCalculator(api_key=api_key)
    
    # Test Stockholm
    stockholm_lat = 59.3293
    stockholm_lon = 18.0686
    
    print(f"📍 Testar för Stockholm ({stockholm_lat}, {stockholm_lon})")
    
    # Hämta soltider
    sun_data = sun_calc.get_sun_times(stockholm_lat, stockholm_lon)
    
    print("\n☀️ Soldata-resultat:")
    print(f"  🌅 Soluppgång: {sun_data['sunrise']}")
    print(f"  🌇 Solnedgång: {sun_data['sunset']}")
    print(f"  ⏱️ Dagsljuslängd: {sun_data['daylight_duration']}")
    print(f"  🔍 Källa: {sun_data['source']}")
    print(f"  💾 Cachad: {sun_data['cached']}")
    
    # Cache-statistik
    cache_stats = sun_calc.get_cache_stats()
    print(f"\n💾 Cache-statistik: {cache_stats}")
    
    return sun_calc


if __name__ == "__main__":
    test_sun_calculator()
