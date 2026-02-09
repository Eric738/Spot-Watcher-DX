import time
import telnetlib
import threading
import json
import os
import urllib.request
import feedparser
import ssl
import math
import re
import logging
import html
import calendar
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from collections import deque, Counter, defaultdict
from flask import Flask, render_template, jsonify, request, abort, redirect, url_for, Response
from pathlib import Path
import subprocess

META_DIR = Path("data/meta")
META_SUMMARY = META_DIR / "summary.json"
LOG_PATH_DEFAULT = Path("radio_spot_watcher.log")  # log courant
ANALYZER = Path("tools/log_meta_analyzer.py")

META_RUN_TOKEN = os.getenv("META_RUN_TOKEN", "")  # optionnel

# --- CLUSTER TX (Spot) ---
tn_lock = threading.Lock()
tn_current = None  # telnetlib.Telnet when connected
# --- FIN CLUSTER TX ---
# --- CONFIGURATION GENERALE ---
APP_VERSION = "NEURAL v6.0"
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 900
SPD_THRESHOLD = 70



# --- LISTE DES PRÉFIXES RARES (pour entités réellement rares) ---
RARE_PREFIXES = [
    'DP0', 'DP1', 'RI1', '8J1', 'VP8', 'KC4',
    '3Y', '3C', 'P5', 'BS7', 'BV9', 'CE0', 'CY9', 'EZ', 'FT5', 'FT8', 'VK0', 'VK7',
    'HV', '1A', '4U', 'E4', 'SV/A', 'T88', '9J', 'XU', '3D2', 'S21', 'H40',
    'KH0', 'KH1', 'KH3', 'KH4', 'KH7', 'KH9', 'KP1', 'KP5', 'T5', 'T31', 'T33', 'YV0',
    'YK', 'VK0', 'VK9', 'VP0', 'V21', 'XF4', 'XZ', 'ZK', 'ZL8', 'ZL7', 'ZL9',
]

TOP_RANKING_LIMIT = 10
DEFAULT_QRA = "JN23"

# --- THEMES/COULEURS RESTAURÉES ---
TEXT_MAIN = "#a0a0a0" # Gris clair
ACCENT = "#00f3ff"    # Cyan vif
ALERT = "#ff003c"     # Rouge
SUCCESS = "#00ff80"   # Vert
WARNING = "#ffcc00"   # Jaune
# --- FIN THEMES/COULEURS RESTAURÉES ---

# --- CONFIGURATION HISTORIQUE ---
HISTORY_BANDS = ['12m', '10m', '6m']
HISTORY_PERIOD_MINUTES = 30  # Granularité de 30 minutes
HISTORY_WINDOW_HOURS = 12    # Fenêtre de 12 heures
HISTORY_SLOTS = (HISTORY_WINDOW_HOURS * 60) // HISTORY_PERIOD_MINUTES  # 24 slots pour 12h/30min

# --- FICHIER DE LOG ---
LOG_FILE = "radio_spot_watcher.log"

# --- CONFIGURATION SURGE ---
SURGE_WINDOW = 900
SURGE_THRESHOLD = 3.0
MIN_SPOTS_FOR_SURGE = 3

# --- CONFIGURATION ASTRO/MÉTEOR SCATTER ---
METEOR_SHOWERS = [
    {"name": "Quadrantides", "start": (1, 1), "end": (1, 7), "peak": (1, 3)},
    {"name": "Lyrides", "start": (4, 16), "end": (4, 25), "peak": (4, 22)},
    {"name": "Êta Aquarides", "start": (4, 20), "end": (5, 30), "peak": (5, 6)},
    {"name": "Perséides", "start": (7, 15), "end": (8, 24), "peak": (8, 12)},
    {"name": "Orionides", "start": (10, 1), "end": (11, 7), "peak": (10, 21)},
    {"name": "Léonides", "start": (11, 10), "end": (11, 23), "peak": (11, 17)},
    {"name": "Géminides", "start": (12, 4), "end": (12, 17), "peak": (12, 14)},
]
MSK144_FREQ = 144.360
MSK144_TOLERANCE_KHZ = 10 / 1000

# --- DEFINITIONS BANDES ---
HF_BANDS = ['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
VHF_BANDS = ['4m', '2m', '70cm', '23cm', '13cm', 'QO-100']
BAND_COLORS = {
    '160m': '#5c4b51', '80m': '#8e44ad', '60m': '#2c3e50',
    '40m': '#2980b9', '30m': '#16a085', '20m': '#27ae60',
    '17m': '#f1c40f', '15m': '#e67e22', '12m': '#d35400',
    '10m': '#c0392b',
    '6m': '#e84393',
    '4m': '#ff9ff3', '2m': '#f1c40f',
    '70cm': '#c0392b', '23cm': '#8e44ad', '13cm': '#bdc3c7',
    'QO-100': '#00a8ff'
}

# --- DX CLUSTER CONFIGURATION ---
RSS_URLS = ["https://www.dx-world.net/feed/"]
CLUSTERS = [
    ("dxfun.com", 8000),
    ("cluster.dx.de", 7300),
    ("telnet.wxc.kr", 23)
]
CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"
WATCHLIST_FILE = "watchlist.json"
SOLAR_URL = "https://services.swpc.noaa.gov/text/wwv.txt"
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
BRIEFING_SOURCES_FILE = Path("data/briefing_sources.json")
BRIEFING_CACHE_TTL = 60 * 60 * 12
BRIEFING_FEED_TIMEOUT = 15
BRIEFING_ITEM_LIMIT = 8
BRIEFING_USER_AGENT = "Spot-Watcher-DX/6.0 (+https://github.com/)"
QO100_NEWS_URL = "https://qo100dx.club/news"
QO100_HEADERS = {
    "User-Agent": "RadioSpotWatcherDX/1.0 (+https://example.local)"
}
BRIEFING_DEFAULT_SOURCES = [
    {
        "id": "dxworld",
        "name": "DX-World",
        "url": "https://www.dx-world.net/feed/",
        "site": "https://www.dx-world.net/",
        "type": "rss",
    },
    {
        "id": "dxnews",
        "name": "DXNews",
        "url": "https://dxnews.com/",
        "site": "https://dxnews.com/",
        "type": "html",
    },
    {
        "id": "ng3k",
        "name": "NG3K ADXO",
        "url": "https://www.ng3k.com/misc/adxo.html",
        "site": "https://www.ng3k.com/misc/adxo.html",
        "type": "html",
    },
    {
        "id": "qo100dx",
        "name": "QO-100 DX Club",
        "url": "https://qo100dx.club",
        "site": "https://qo100dx.club",
        "type": "html",
    },
]

# --- SOLAR (XML) FETCHER ---

def fetch_noaa_kp_latest(timeout=10):
    """Fetch latest NOAA planetary Kp index (table JSON). Returns dict or None."""
    try:
        req = urllib.request.Request(NOAA_KP_URL, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8', errors='ignore'))

        # Expected format: [ ["time_tag","Kp","a_running","station_count"], ["2026-...","3.67","22","8"], ... ]
        if not isinstance(data, list) or len(data) < 2 or not isinstance(data[0], list):
            return None

        header = data[0]
        def _h(name, default=None):
            return header.index(name) if name in header else default

        i_time = _h("time_tag", 0)
        i_kp = _h("Kp", 1)
        i_a = _h("a_running", None)
        i_sc = _h("station_count", None)

        row = data[-1]
        time_tag = str(row[i_time]).replace(".000", "")
        kp = float(str(row[i_kp]).replace(",", "."))
        a_running = int(row[i_a]) if i_a is not None and str(row[i_a]).strip() else None
        station_count = int(row[i_sc]) if i_sc is not None and str(row[i_sc]).strip() else None

        return {
            "kp": kp,
            "kp_time_utc": time_tag,
            "kp_a_running": a_running,
            "kp_station_count": station_count,
        }
    except Exception as e:
        logging.getLogger(__name__).warning(f"Kp NOAA fetch failed: {e}")
        return None

def fetch_solar_from_wwv_txt():
    """
    Fetch solar indices from NOAA SWPC wwv.txt and NOAA planetary Kp (JSON table),
    then update solar_cache + solar_xml_cache.
    Runs hourly in solar_worker().
    """
    global solar_cache, solar_xml_cache
    try:
        req = urllib.request.Request(SOLAR_URL, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode('utf-8', errors='ignore')

        # Robust parsing (wwv.txt format varies)
        sfi = a_idx = k_idx = "N/A"

        m_sfi = re.search(r"Solar\s+flux\s*[:=]?\s*([0-9]+)", raw, re.IGNORECASE)
        if m_sfi:
            sfi = m_sfi.group(1)

        m_a = re.search(r"\bA[-\s]?index\s*[:=]?\s*([0-9]+)", raw, re.IGNORECASE)
        if m_a:
            a_idx = m_a.group(1)

        m_k = re.search(r"\bK[-\s]?index\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", raw, re.IGNORECASE)
        if m_k:
            k_idx = m_k.group(1)

        # Timestamp
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # NOAA Planetary Kp (robust JSON table)
        kp_info = fetch_noaa_kp_latest()
        kp_val = kp_info.get("kp") if kp_info else None
        kp_time_utc = kp_info.get("kp_time_utc") if kp_info else None
        kp_a_running = kp_info.get("kp_a_running") if kp_info else None
        kp_station_count = kp_info.get("kp_station_count") if kp_info else None

        # Backward-compat: keep 'k' field but prefer planetary Kp when available
        k_display = f"{kp_val:.2f}" if isinstance(kp_val, (int, float)) else k_idx

        with solar_lock:
            solar_cache = {
                "sfi": sfi,
                "a": a_idx,
                "k": k_display,           # legacy field used by older UIs
                "kp": kp_val,             # numeric
                "kp_time_utc": kp_time_utc,
                "kp_a_running": kp_a_running,
                "kp_station_count": kp_station_count,
                "ts_utc": ts
            }

            solar_xml_cache = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<solar>'
                f'<sfi>{sfi}</sfi>'
                f'<a>{a_idx}</a>'
                f'<k>{k_display}</k>'
                f'<kp>{"" if kp_val is None else kp_val}</kp>'
                f'<kp_time_utc>{"" if kp_time_utc is None else kp_time_utc}</kp_time_utc>'
                f'<updated_utc>{ts}</updated_utc>'
                '</solar>'
            )

        logger.info(f"SOLAR updated: SFI={sfi} A={a_idx} K={k_display} (Kp={kp_val})")

    except Exception as e:
        logger.error(f"SolarWorker: impossible de récupérer/produire solar.xml: {e}")
def solar_worker():
    threading.current_thread().name = 'SolarWorker'
    logger.info("SolarWorker démarré (update solar.xml toutes les heures).")
    # run once immediately
    fetch_solar_from_wwv_txt()
    while True:
        time.sleep(3600)
        fetch_solar_from_wwv_txt()

def geo_distance_km(a, b):
    return calculate_distance(a["lat"], a["lon"], b["lat"], b["lon"])


def cluster_spots(spots, max_dist_km=800):
    clusters = []

    for s in spots:
        placed = False
        for c in clusters:
            if geo_distance_km(s, c["center"]) <= max_dist_km:
                c["spots"].append(s)
                # recalcul centre
                c["center"]["lat"] = sum(x["lat"] for x in c["spots"]) / len(c["spots"])
                c["center"]["lon"] = sum(x["lon"] for x in c["spots"]) / len(c["spots"])
                placed = True
                break
        if not placed:
            clusters.append({
                "center": {"lat": s["lat"], "lon": s["lon"]},
                "spots": [s]
            })

    return clusters
# --- END SOLAR (XML) FETCHER ---


# --- CACHES GLOBAUX et INITIALISATION QTH ---
spots_buffer = deque(maxlen=6000)
# --- SPOT HISTORY (Tracking Watchlist) ---
SPOT_HISTORY_MAX = 20000
spot_history = deque(maxlen=SPOT_HISTORY_MAX)
spot_history_lock = threading.Lock()
# --- END SPOT HISTORY ---
band_history = {}
prefix_db = {}
ticker_info = {"text": "SYSTEM INITIALIZATION... (Waiting for RSS/Solar data)"}

# --- SOLAR CACHE (XML/JSON) ---
solar_lock = threading.Lock()
solar_cache = {"sfi": "N/A", "a": "N/A", "k": "N/A", "kp": None, "kp_time_utc": None, "kp_a_running": None, "kp_station_count": None, "ts_utc": None}
solar_xml_cache = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><solar><sfi>N/A</sfi><a>N/A</a><k>N/A</k><kp></kp><kp_time_utc></kp_time_utc><updated_utc></updated_utc></solar>"
# --- END SOLAR CACHE ---
watchlist = set()
surge_bands = []
history_30min = {band: [0] * HISTORY_SLOTS for band in HISTORY_BANDS}
history_lock = threading.Lock()
surge_lock = threading.Lock()

# --- CONFIGURATION DU LOGGER ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(threadName)s: %(message)s'
formatter = logging.Formatter(LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when='midnight',
    interval=1,
    backupCount=1,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__, template_folder="templates")

# --- PLAGES DE FREQUENCES CW ---
CW_RANGES = [
    ('160m', 1.810, 1.838), ('80m', 3.500, 3.560), ('40m', 7.000, 7.035),
    ('30m', 10.100, 10.134), ('20m', 14.000, 14.069), ('17m', 18.068, 18.095),
    ('15m', 21.000, 21.070), ('12m', 24.890, 24.913), ('10m', 28.000, 28.070),
]

# --- FRÉQUENCES FT4/FT8 (en kHz) ---
FT8_VHF_FREQ_RANGE_KHZ = (144171, 144177)

# --- FRÉQUENCES PSK31 (en kHz) ---
PSK31_HF_FREQ_RANGE_KHZ = (14.069, 14.071)

# --- SSL BYPASS ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- FONCTIONS UTILITAIRES ---
def qra_to_lat_lon(qra):
    try:
        qra = qra.upper().strip()
        if len(qra) < 4:
            return None, None
        lon = -180 + (ord(qra[0]) - ord('A')) * 20
        lat = -90 + (ord(qra[1]) - ord('A')) * 10
        if len(qra) >= 4:
            lon += int(qra[2]) * 2
            lat += int(qra[3]) * 1
        if len(qra) >= 6:
            lon += (ord(qra[4]) - ord('A')) * (2/24) + (1/24)
            lat += (ord(qra[5]) - ord('A')) * (1/24) + (1/48)
        else:
            lon += 1
            lat += 0.5
        return lat, lon
    except Exception:
        return None, None

# Initialisation du QTH utilisateur
initial_lat, initial_lon = qra_to_lat_lon(DEFAULT_QRA)
user_qra = DEFAULT_QRA
user_lat = initial_lat if initial_lat is not None else 43.10
user_lon = initial_lon if initial_lon is not None else 5.88

def is_meteor_shower_active():
    now = time.gmtime(time.time())
    current_month = now.tm_mon
    current_day = now.tm_mday
    for shower in METEOR_SHOWERS:
        start_m, start_d = shower["start"]
        end_m, end_d = shower["end"]
        if start_m > end_m:
            if (current_month == start_m and current_day >= start_d) or \
               (current_month == end_m and current_day <= end_d) or \
               (start_m == 12 and current_month == 1):
                return True, shower["name"]
        else:
            if (start_m == current_month and current_day >= start_d) or \
               (end_m == current_month and current_day <= end_d) or \
               (start_m < current_month < end_m):
                return True, shower["name"]
    return False, None

# --- Watchlist ---
def load_watchlist():
    global watchlist
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                watchlist = set([c.upper() for c in data if isinstance(c, str)])
            logger.info(f"Watchlist chargée: {len(watchlist)} indicatifs.")
        except Exception as e:
            logger.error(f"Impossible de charger la Watchlist, elle sera réinitialisée: {e}")
            watchlist = set()

def save_watchlist():
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(sorted(list(watchlist)), f, indent=2)
        logger.info(f"Watchlist sauvegardée avec {len(watchlist)} indicatifs.")
    except Exception as e:
        logger.error(f"Impossible de sauvegarder la Watchlist: {e}")

# --- SURGE & HISTORY ---
def record_surge_data(band):
    if band not in band_history:
        band_history[band] = deque()
    band_history[band].append(time.time())

    if band in HISTORY_BANDS:
        now_utc = time.gmtime(time.time())
        current_slot = ((now_utc.tm_hour * 2) + (now_utc.tm_min // 30)) % HISTORY_SLOTS
        with history_lock:
            history_30min[band][current_slot] += 1

    if band in VHF_BANDS:
        logger.debug(f"VHF Spot recorded for band {band}.")

def analyze_surges():
    global surge_bands
    current_time = time.time()
    active_surges = []

    recent_ms_spots_count = sum(1 for s in spots_buffer
                              if s.get('mode') == 'MSK144' and (current_time - s['timestamp']) < 900)
    is_active, shower_name = is_meteor_shower_active()
    ms_surge_name = f"MSK144: {shower_name}" if is_active else "MSK144: Inactive"

    with surge_lock:
        if is_active and recent_ms_spots_count >= MIN_SPOTS_FOR_SURGE:
            if ms_surge_name not in surge_bands:
                surge_bands.append(ms_surge_name)
            active_surges.append(ms_surge_name)
        elif ms_surge_name in surge_bands:
            surge_bands.remove(ms_surge_name)

        bands_in_surge = [s for s in surge_bands if not s.startswith("MSK144:")]

        for band in HF_BANDS + [b for b in VHF_BANDS if b not in ['2m', 'QO-100']]:
            timestamps = band_history.get(band, deque())

            while timestamps and timestamps[0] < current_time - SURGE_WINDOW:
                timestamps.popleft()

            count_total = len(timestamps)
            if count_total < MIN_SPOTS_FOR_SURGE:
                continue

            avg_rate = count_total / (SURGE_WINDOW / 60.0)
            recent_count = sum(1 for t in timestamps if t > current_time - 60)

            is_surging = (recent_count > (avg_rate * SURGE_THRESHOLD)) and (recent_count >= MIN_SPOTS_FOR_SURGE)

            if is_surging:
                if band not in bands_in_surge:
                    logger.info(f"ALERTE SURGE {band}: Détectée ({recent_count} spots / min)")
                    surge_bands.append(band)
                if band not in active_surges:
                    active_surges.append(band)
            elif band in bands_in_surge:
                surge_bands.remove(band)
                logger.info(f"FIN ALERTE SURGE {band}: L'activité a diminué.")
    return active_surges

# --- MOTEUR DRSE ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_spd_score(call, band, mode, comment, country, dist_km):
    score = 10
    call = call.upper()
    comment = (comment or "").upper()
    for p in RARE_PREFIXES:
        if call.startswith(p):
            score += 65
            break

    if 'UP' in comment or 'SPLIT' in comment:
        score += 15
    if 'DX' in comment:
        score += 5
    if 'QRZ' in comment:
        score -= 10
    if 'PIRATE' in comment:
        score = 0
    if mode == 'CW':
        score += 10

    if dist_km and dist_km > 1000:
        distance_bonus = min(20, 20 * math.log10(dist_km / 1000))
        score += distance_bonus

    if band == 'QO-100':
        score += 40
    elif band in VHF_BANDS:
        score += 30

    if band in ['10m', '12m', '15m']:
        score += 15

    return min(int(score), 100)

def is_rare_prefix(call: str) -> bool:
    """True si l'indicatif commence par un préfixe explicitement déclaré rare."""
    c = (call or "").upper().strip()
    for p in RARE_PREFIXES:
        if c.startswith(p):
            return True
    return False


def get_band_and_mode_smart(freq_float, comment):
    comment = (comment or "").upper()
    f = float(freq_float)
    if f < 1000:
        f = f * 1000.0
    elif f > 20000000:
        f = f / 1000.0
    freq_khz = f

    def find_band(freq_khz):
        if 1800 <= freq_khz <= 2000:
            return "160m"
        if 3500 <= freq_khz <= 3800:
            return "80m"
        if 5300 <= freq_khz <= 5450:
            return "60m"
        if 7000 <= freq_khz <= 7300:
            return "40m"
        if 10100 <= freq_khz <= 10150:
            return "30m"
        if 14000 <= freq_khz <= 14350:
            return "20m"
        if 18068 <= freq_khz <= 18168:
            return "17m"
        if 21000 <= freq_khz <= 21450:
            return "15m"
        if 24890 <= freq_khz <= 24990:
            return "12m"
        if 28000 <= freq_khz <= 29700:
            return "10m"
        if 50000 <= freq_khz <= 54000:
            return "6m"
        if 70000 <= freq_khz <= 70500:
            return "4m"
        if 144000 <= freq_khz <= 146000:
            return "2m"
        if 430000 <= freq_khz <= 440000:
            return "70cm"
        if 1240000 <= freq_khz <= 1300000:
            return "23cm"
        if 10489000 <= freq_khz <= 10499000:
            return "QO-100"
        return "Unknown"

    band = find_band(freq_khz)
    f_mhz = freq_khz / 1000.0
    mode = "SSB"
    TOLERANCE_KHZ = 1
    FT4_HF_FREQS_KHZ = [7047, 10140, 14080, 18104, 21180, 24919, 28180]
    is_ft4_hf = any(abs(freq_khz - ft4_f) <= TOLERANCE_KHZ for ft4_f in FT4_HF_FREQS_KHZ)
    FT4_VHF_FREQ_KHZ = 144170
    is_ft4_vhf = band == "2m" and abs(freq_khz - FT4_VHF_FREQ_KHZ) <= TOLERANCE_KHZ
    ft8_vhf_min, ft8_vhf_max = FT8_VHF_FREQ_RANGE_KHZ
    is_ft8_vhf = band == "2m" and ft8_vhf_min <= freq_khz <= ft8_vhf_max

    if is_ft4_hf or is_ft4_vhf:
        mode = "FT4"
    elif is_ft8_vhf:
        mode = "FT8"

    if mode == "SSB":
        for cw_band, min_mhz, max_mhz in CW_RANGES:
            if cw_band == band and min_mhz <= f_mhz <= max_mhz:
                mode = "CW"
                break

    if band == "2m" and abs(f_mhz - MSK144_FREQ) <= MSK144_TOLERANCE_KHZ:
        mode = "MSK144"

    if "FT8" in comment and mode != "FT4":
        mode = "FT8"
    elif "FT4" in comment and mode != "FT8":
        mode = "FT4"
    elif "CW" in comment and mode == "SSB":
        mode = "CW"
    elif "FM" in comment:
        mode = "FM"
    elif "RTTY" in comment:
        mode = "RTTY"
    elif "SSTV" in comment or abs(freq_khz - 14230) <= 2:
        mode = "SSTV"

    return band, mode

def load_cty_dat(force_download: bool = False):
    """Charge cty.dat (DXCC/prefixes). Télécharge si absent (ou si force_download=True).
    NOTE: certains miroirs renvoient 406 sans header Accept -> on force Accept: */*.
    """
    global prefix_db

    def download_cty() -> bool:
        try:
            logger.info("Tentative de téléchargement de cty.dat...")
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                "Accept": "*/*",
            }
            req = urllib.request.Request(CTY_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r, open(CTY_FILE, "wb") as f:
                f.write(r.read())
            # petit garde-fou: fichier trop petit = téléchargement foireux
            if os.path.exists(CTY_FILE) and os.path.getsize(CTY_FILE) < 50_000:
                logger.warning("cty.dat téléchargé mais taille suspecte (<50KB).")
            logger.info("Téléchargement de cty.dat réussi.")
            return True
        except Exception as e:
            logger.error(f"Échec du téléchargement de cty.dat. Vérifie l'URL ou la connexion: {e}")
            return False

    # Télécharger si absent, si demandé, ou si fichier vide/suspect
    if force_download or (not os.path.exists(CTY_FILE)) or (os.path.exists(CTY_FILE) and os.path.getsize(CTY_FILE) < 50_000):
        if not download_cty():
            return

    try:
        logger.info("Chargement de la base de données DXCC (cty.dat).")
        prefix_db.clear()
        with open(CTY_FILE, "rb") as f:
            raw = f.read().decode("latin-1", errors="ignore")

        for rec in raw.replace("\r", "").replace("\n", " ").split(";"):
            if ":" in rec:
                p = rec.split(":")
                country = p[0].strip()
                try:
                    lat, lon = float(p[4]), float(p[5]) * -1
                except Exception:
                    lat, lon = 0.0, 0.0

                prefixes = p[7].strip().split(",")
                if len(p) > 8:
                    prefixes += p[8].strip().split(",")

                for px in prefixes:
                    clean = px.split("(")[0].split("[")[0].strip().lstrip("=")
                    if clean:
                        prefix_db[clean] = {"c": country, "lat": lat, "lon": lon}

        if not prefix_db:
            # si parsing vide, on retente un download "propre"
            logger.warning("prefix_db vide après parsing cty.dat -> re-téléchargement et retry.")
            if download_cty():
                return load_cty_dat(force_download=False)

        logger.info(f"Base de données DXCC chargée: {len(prefix_db)} préfixes.")
    except Exception as e:
        logger.error(f"Erreur lors du parsing de cty.dat: {e}")


def get_country_info(call):
    call = call.upper()
    best = {'c': 'Unknown', 'lat': 0.0, 'lon': 0.0}
    longest = 0
    candidates = [call]
    if '/' in call:
        candidates.append(call.split('/')[-1])
    for c in candidates:
        for i in range(len(c), 0, -1):
            sub = c[:i]
            if sub in prefix_db and len(sub) > longest:
                longest = len(sub)
                best = prefix_db[sub]
    return best

# --- WORKERS ---
def history_maintenance_worker():
    """Tâche de maintenance pour décaler l'historique 30min/12h à chaque période."""
    threading.current_thread().name = 'HistoryWorker'
    logger.info("HistoryWorker démarré (30min/12h).")
    while True:
        now_utc = time.gmtime(time.time())
        current_minute = now_utc.tm_min
        current_hour = now_utc.tm_hour
        minutes_until_next_slot = (30 - (current_minute % 30)) % 30
        seconds_until_next_slot = minutes_until_next_slot * 60 - now_utc.tm_sec

        # Correction : on s'assure que le temps est toujours positif
        if seconds_until_next_slot < 0:
            seconds_until_next_slot = 0

        logger.debug(f"Prochaine rotation dans {seconds_until_next_slot} secondes.")
        time.sleep(seconds_until_next_slot + 5)

        with history_lock:
            for band in HISTORY_BANDS:
                history_30min[band].pop(0)
                history_30min[band].append(0)
            logger.info(f"HISTORY 30min: Rotation des slots (nouveau slot pour {current_hour:02d}:{current_minute:02d} UTC).")

def ticker_worker():
    """Tâche pour mettre à jour le message défilant avec les infos solaires et RSS."""
    threading.current_thread().name = 'TickerWorker'
    logger.info("TickerWorker démarré.")
    while True:
        msgs = [f"SYSTEM ONLINE - {MY_CALL} ({APP_VERSION})"]

        try:
            req = urllib.request.Request(SOLAR_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                l = [x for x in r.read().decode('utf-8').split('\n') if x and not x.startswith((':','#'))]
                if l:
                    solar_data = l[-1].split()
                    try:
                        a_index = solar_data.index('A-Index:') + 1
                        k_index = solar_data.index('K-Index:') + 1
                        A = solar_data[a_index] if a_index < len(solar_data) else 'N/A'
                        K = solar_data[k_index] if k_index < len(solar_data) else 'N/A'
                        msgs.append(f"SOLAR: A-Index: {A} | K-Index: {K}")
                    except ValueError:
                        msgs.append(f"SOLAR: {l[-1]}")
                else:
                    msgs.append("SOLAR: Data empty.")
        except Exception as e:
            logger.error(f"Erreur de récupération des données solaires: {e}")
            msgs.append("SOLAR: Data retrieval failed.")

        try:
            feed = feedparser.parse(RSS_URLS[0])
            if feed.entries:
                news = [entry.title for entry in feed.entries[:5]]
                msgs.append("NEWS: " + " | ".join(news))
            else:
                msgs.append("NEWS: RSS feed empty.")
        except Exception as e:
            logger.error(f"Erreur de récupération du flux RSS: {e}")
            msgs.append("NEWS: RSS retrieval failed.")

        ticker_info["text"] = "   +++   ".join(msgs)
        logger.info(f"Ticker mis à jour.")
        time.sleep(1800)

def telnet_worker():
    """Tâche pour se connecter et écouter le DX Cluster."""
    threading.current_thread().name = 'TelnetWorker'
    logger.info("TelnetWorker démarré.")
    idx = 0
    while True:
        host, port = CLUSTERS[idx]
        logger.info(f"Tentative de connexion au Cluster: {host}:{port} ({idx + 1}/{len(CLUSTERS)})")
        try:
            tn = telnetlib.Telnet(host, port, timeout=10)
            # Expose current connection for TX (spotting)
            global tn_current
            with tn_lock:
                tn_current = tn
            try:
                tn.read_until(b"login: ", timeout=3)
            except:
                pass

            tn.write(MY_CALL.encode('latin-1') + b"\n")
            time.sleep(1)
            tn.write(b"set/dx/filter\n")
            tn.write(b"show/dx 50\n")
            logger.info(f"Connexion établie sur {host}:{port}. Écoute des spots en cours.")
            last_ping = time.time()

            while True:
                try:
                    line = tn.read_until(b"\n", timeout=2).decode('ascii', errors='ignore').strip()
                except EOFError:
                    logger.warning(f"Cluster {host} a fermé la connexion (EOFError).")
                    break
                except Exception as e:
                    logger.warning(f"Erreur de lecture Telnet: {e}")
                    line = ""

                if not line:
                    if time.time() - last_ping > KEEP_ALIVE:
                        tn.write(b"\n")
                        last_ping = time.time()
                    analyze_surges()
                    continue

                if line.startswith("DX de"):
                    try:
                        content = line[line.find("DX de")+5:].strip()
                        parts = content.split()
                        if len(parts) < 3:
                            continue
                        freq_str = parts[1]
                        dx_call = parts[2].upper()
                        comment = " ".join(parts[3:]).upper()

                        try:
                            freq_raw = float(freq_str)
                        except:
                            continue
                        band, mode = get_band_and_mode_smart(freq_raw, comment)
                        info = get_country_info(dx_call)

                        lat, lon = info['lat'], info['lon']
                        dist_km = 0.0
                        if lat != 0.0 and lon != 0.0:
                            dist_km = calculate_distance(user_lat, user_lon, lat, lon)

                        spd_score = calculate_spd_score(dx_call, band, mode, comment, info['c'], dist_km)
                        color = BAND_COLORS.get(band, '#00f3ff')
                        
                        # Générer un spot_id unique pour le Path Optimizer
                        spot_id = f"{dx_call}-{int(time.time())}"

                        record_surge_data(band)

                        spot_obj = {
                            "timestamp": time.time(), "time": time.strftime("%H:%M"),
                            "freq": freq_str, "dx_call": dx_call, "band": band, "mode": mode,
                            "country": info['c'], "lat": lat, "lon": lon,
                            "score": spd_score,
                            "is_wanted": spd_score >= SPD_THRESHOLD,
                            "is_rare": is_rare_prefix(dx_call),
                            "via_eme": ("EME" in comment),
                            "color": color,
                            "type": "VHF" if band in VHF_BANDS else "HF",
                            "distance_km": dist_km,
                            "spot_id": spot_id # Ajout de l'ID
                        }
                        spots_buffer.append(spot_obj)
                        # Tracking Watchlist: petit historique RAM (léger, filtrable)
                        try:
                            with spot_history_lock:
                                spot_history.append({
                                    "ts": spot_obj.get("timestamp", time.time()),
                                    "dx": spot_obj.get("dx_call"),
                                    "de": None,
                                    "band": spot_obj.get("band"),
                                    "mode": spot_obj.get("mode"),
                                    # freq_khz best-effort (float) si possible
                                    "freq_khz": (float(str(spot_obj.get("freq")).replace(",", ".")) if spot_obj.get("freq") is not None else None),
                                })
                        except Exception:
                            pass
                        logger.info(f"SPOT: {dx_call} ({band}, {mode}) -> SPD: {spd_score} pts (Dist: {dist_km:.0f}km)")
                    except Exception as e:
                        logger.error(f"Erreur de traitement du spot '{line[:50]}...': {e}")

        except Exception as e:
            logger.error(f"ERREUR CRITIQUE Cluster {host}:{port}: {e}. Basculement vers un autre cluster.")
            time.sleep(10)

        idx = (idx + 1) % len(CLUSTERS)

# --- ROUTES ---
@app.route("/api/world/events")
def api_map_events():
    band = request.args.get("band")
    window_min = int(request.args.get("window", 60))

    now = time.time()
    recent = [
        s for s in spots_buffer
        if now - s["timestamp"] <= window_min * 60
        and s.get("lat") and s.get("lon")
        and (not band or s["band"] == band)
    ]

    clusters = cluster_spots(recent)

    events = []
    for c in clusters:
        spots = c["spots"]
        if len(spots) < 3:
            continue

        dxcc = set(s["country"] for s in spots if s.get("country"))
        distances = [s.get("distance_km", 0) for s in spots]

        event = {
            "band": spots[0]["band"],
            "center": c["center"],
            "spot_count": len(spots),
            "dxcc_count": len(dxcc),
            "max_distance_km": int(max(distances)),
            "calls": list({s["dx_call"] for s in spots})[:10],
            "score": int(
                len(spots) * 5
                + len(dxcc) * 15
                + max(distances) / 200
            )
        }

        events.append(event)

    events.sort(key=lambda e: e["score"], reverse=True)

    return jsonify({
        "ok": True,
        "count": len(events),
        "events": events[:10]
    })
@app.get("/api/meta/summary")
def api_meta_summary():
    if not META_SUMMARY.exists():
        return jsonify({"status": "no_summary"}), 404
    try:
        return jsonify(json.loads(META_SUMMARY.read_text(encoding="utf-8")))
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION, my_call=MY_CALL,
                           hf_bands=HF_BANDS, vhf_bands=VHF_BANDS, band_colors=BAND_COLORS,
                           spd_threshold=SPD_THRESHOLD, user_qra=user_qra)

@app.route("/ai.html")
def ai_page():
    return render_template("ai.html")

@app.route("/map")
def map_page():
    return render_template("map.html", version=APP_VERSION, my_call=MY_CALL, user_qra=user_qra)

@app.route("/map.html")
def map_html_compat():
    return redirect(url_for("map_page"))

@app.route("/world")
def world_page():
    return render_template("world.html")

@app.route('/update_qra', methods=['POST'])
def update_qra():
    global user_qra, user_lat, user_lon
    new_qra = request.form.get('qra_locator', '').upper().strip()
    if not new_qra:
        return redirect(url_for('index'))
    new_lat, new_lon = qra_to_lat_lon(new_qra)
    valid = new_lat is not None and new_lon is not None
    if valid:
        user_qra = new_qra
        user_lat = new_lat
        user_lon = new_lon
        logger.info(f"QTH mis à jour: {user_qra}")
    else:
        logger.warning(f"Tentative de mise à jour QTH invalide: {new_qra}")
    return redirect(url_for('index'))


def cluster_send_line(line: str) -> bool:
    """Send a raw line to the connected DX cluster. Returns True if sent."""
    global tn_current
    if not line:
        return False
    with tn_lock:
        tn = tn_current
    if tn is None:
        return False
    try:
        # Cluster expects latin-1 compatible bytes in most cases
        tn.write(line.encode('latin-1', errors='ignore') + b"\n")
        return True
    except Exception:
        return False

@app.route('/spot', methods=['POST'])
@app.route('/api/spot', methods=['POST'])
def api_spot():
    """Spot a callsign to the DX cluster: expects JSON {freq, call, comment}."""
    data = request.get_json(silent=True) or {}
    call = (data.get('call') or '').strip().upper()
    freq = (data.get('freq') or '').strip()
    comment = (data.get('comment') or '').strip()
    if not call or not re.match(r"^[A-Z0-9/]{3,}$", call):
        return jsonify({'ok': False, 'error': 'CALL invalid'}), 400
    # freq: allow "14074.0" or "14.074" etc. We send what user provided if numeric
    try:
        f = float(freq.replace(',', '.'))
    except Exception:
        return jsonify({'ok': False, 'error': 'FREQ invalid'}), 400
    if f <= 0:
        return jsonify({'ok': False, 'error': 'FREQ invalid'}), 400
    # Keep formatting close to what clusters commonly show
    # If user entered MHz (< 1000), convert to kHz-ish? Here we assume: < 1000 => MHz*1000 (14.074 -> 14074.0)
    if f < 1000:
        f_out = f * 1000.0
    else:
        f_out = f
    freq_out = f"{f_out:.1f}"
    # Build cluster command
    cmd = f"DX {freq_out} {call} {comment}".strip()
    sent = cluster_send_line(cmd)
    if not sent:
        return jsonify({'ok': False, 'error': 'Cluster not connected'}), 503
    logger.info(f"Spot TX: {cmd}")
    return jsonify({'ok': True, 'sent': cmd})

@app.route('/user_location.json')
def get_user_location():
    return jsonify({'qra': user_qra, 'lat': user_lat, 'lon': user_lon})

@app.route('/spots.json')
def get_spots():
    now = time.time()
    filter_band = request.args.get('band')
    filter_mode = request.args.get('mode')
    all_spots = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    if filter_band and filter_band != "All":
        all_spots = [s for s in all_spots if s['band'] == filter_band]
    if filter_mode and filter_mode != "All":
        all_spots = [s for s in all_spots if s['mode'] == filter_mode]
    return jsonify(list(reversed(all_spots)))

@app.route('/surge.json')
def get_surge_status():
    active_surges = analyze_surges()
    return jsonify({"surges": active_surges, "timestamp": time.time()})

@app.route('/analysis.html')
def analysis_page():
    """Route pour rendre la page d'analyse/AI Insight."""
    return render_template('analysis.html', my_call=MY_CALL)

@app.route('/analysis')
def analysis_page_alias():
    return redirect(url_for('analysis_page'))

# --- NOUVELLE ROUTE STATISTIQUES DXCC 24H ---

@app.route('/dxcc_stats_24h.json')
def dxcc_stats_24h():
    """
    Calcule et retourne les statistiques DXCC sur 24 heures.
    Inclut les listes dynamiques pour les calls longue distance et les entités rares.
    """
    now = time.time()
    # Spots dans les dernières 24 heures (86400 secondes)
    all_spots_history = spots_buffer # Utiliser le buffer comme historique
    historical_spots = [s for s in all_spots_history if (now - s['timestamp']) < 86400] 

    # Initialisation des compteurs et listes
    dxcc_by_mode = Counter()
    dxcc_by_band = Counter()
    unique_dxcc_set = set()
    high_spd_spots_count = 0
    
    # Nouvelles listes demandées pour le front-end
    rare_dxcc_entities = set()
    long_distance_calls = set()
    
    # Itération sur les spots historiques
    for spot in historical_spots:
        dxcc = spot.get('country') 
        mode = spot.get('mode')
        band = spot.get('band')
        spd = spot.get('score')
        distance_km = spot.get('distance_km')
        call = spot.get('dx_call') 
        
        if dxcc:
            unique_dxcc_set.add(dxcc)
            if mode:
                dxcc_by_mode[mode] += 1
            if band:
                dxcc_by_band[band] += 1

        # 1. Spots rares (SPD>=seuil) + entités rares (préfixes explicitement rares)
        if spd is not None and spd >= SPD_THRESHOLD and dxcc:
            high_spd_spots_count += 1
        if spot.get('is_rare') and dxcc:
            rare_dxcc_entities.add(dxcc)

        # 2. Calcul des calls Longue Distance (> 10000 km)
        # On ne compte que les indicatifs uniques pour la liste
        if distance_km is not None and distance_km >= 10000 and call:
            long_distance_calls.add(call)

    total_spots_24h = len(historical_spots)
    rarity_rate_percent = f"{(high_spd_spots_count / total_spots_24h * 100):.2f}%" if total_spots_24h > 0 else "0.00%"
    last_updated_time = time.strftime("%H:%M:%S", time.gmtime(now))

    # --- Fenêtre courte pour anomalies (2 heures) ---
    recent_spots = [s for s in all_spots_history if (now - s['timestamp']) < 7200]
    recent_by_band = Counter(s.get('band') for s in recent_spots if s.get('band'))

    # Fréquence la plus vue sur 6m (pour affichage anomalies)
    freq6 = [s.get('freq') for s in recent_spots if s.get('band') == '6m' and s.get('freq')]
    top6 = Counter(freq6).most_common(1)
    top_freq_6m = top6[0][0] if top6 else None
    # Dernier spot 6m sur la fenêtre courte (2h) : permet une expiration fiable après 2h sans activité
    last6 = None
    for sp in recent_spots:
        if sp.get('band') == '6m':
            if (last6 is None) or (sp.get('timestamp', 0) > last6.get('timestamp', 0)):
                last6 = sp
    last6_age_sec = int(now - last6['timestamp']) if last6 and last6.get('timestamp') else None
    last6_time = last6.get('time') if last6 else None
    last6_call = last6.get('dx_call') if last6 else None
    last6_freq = last6.get('freq') if last6 else None

    # Activités rares : liste "call + heure + fréquence" avec raz naturelle via fenêtre glissante
    RARE_WINDOW_SEC = 3 * 3600  # 3 heures
    rare_recent = [sp for sp in all_spots_history if (now - sp.get('timestamp', 0)) < RARE_WINDOW_SEC and sp.get('is_rare')]
    last_by_call = {}
    for sp in rare_recent:
        c = sp.get('dx_call')
        if not c:
            continue
        prev = last_by_call.get(c)
        if (prev is None) or (sp.get('timestamp', 0) > prev.get('timestamp', 0)):
            last_by_call[c] = sp
    rare_spots_list = sorted(last_by_call.values(), key=lambda x: x.get('timestamp', 0), reverse=True)[:20]
    recent_rare_spots = [
        {
            'call': sp.get('dx_call'),
            'time': sp.get('time'),
            'freq': sp.get('freq'),
            'band': sp.get('band'),
            'mode': sp.get('mode'),
            'country': sp.get('country'),
            'timestamp': sp.get('timestamp')
        }
        for sp in rare_spots_list
    ]



    return jsonify({
        "unique_dxcc_count": len(unique_dxcc_set),
        "total_spots_24h": total_spots_24h,
        "rarity_rate_percent": rarity_rate_percent,
        "high_spd_spots": high_spd_spots_count,
        "dxcc_by_mode": dict(dxcc_by_mode),
        "dxcc_by_band": dict(dxcc_by_band),
        "last_updated": last_updated_time,

        # Fenêtre courte (2h) pour anomalies
        "recent_by_band": dict(recent_by_band),
        "recent_top_freq": {"6m": top_freq_6m},
        "last_6m": {"age_sec": last6_age_sec, "time": last6_time, "call": last6_call, "freq": last6_freq},
        "recent_rare_spots": recent_rare_spots,
        
        # Clés pour les listes dynamiques
        "rare_dxcc_entities": sorted(list(rare_dxcc_entities)), 
        "long_distance_calls_count": len(long_distance_calls), 
        "long_distance_calls": sorted(list(long_distance_calls))
    })

@app.post("/api/meta/run")
def run_meta():
    """
    Relance la méta-analyse (génère data/meta/summary.json etc.)
    Sécurité:
      - Si META_RUN_TOKEN est défini => header X-META-TOKEN requis.
      - Sinon => autorisé uniquement depuis le LAN (192.168.x.x / 10.x.x.x / 127.0.0.1).
    """
    try:
        ip = request.remote_addr or ""
        token = request.headers.get("X-META-TOKEN", "")

        # Si token configuré -> token obligatoire
        if META_RUN_TOKEN:
            if token != META_RUN_TOKEN:
                return jsonify({"status": "forbidden"}), 403
        else:
            # Sinon: on limite au LAN (évite exposition accidentelle)
            if not (ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("127.")):
                return jsonify({"status": "forbidden"}), 403

        META_DIR.mkdir(parents=True, exist_ok=True)

        log_path = request.args.get("log", str(LOG_PATH_DEFAULT))
        cmd = ["python3", str(ANALYZER), "--log", log_path, "--outdir", str(META_DIR)]

        subprocess.run(cmd, timeout=120, check=True)

        return jsonify({"status": "ok"})
    except subprocess.TimeoutExpired:
        return jsonify({"status": "timeout"}), 504
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "failed", "code": e.returncode}), 500
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500
@app.route('/wanted.json')
def get_ranking():
    now = time.time()
    active = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    def get_top_for_list(spot_list):
        ranked = sorted(spot_list, key=lambda x: x['score'], reverse=True)
        seen, top = set(), []
        for s in ranked:
            if s['dx_call'] not in seen:
                top.append(s)
                seen.add(s['dx_call'])
            if len(top) >= TOP_RANKING_LIMIT:
                break
        return top
    hf_spots = [s for s in active if s['type'] == 'HF']
    vhf_spots = [s for s in active if s['type'] == 'VHF']
    return jsonify({"hf": get_top_for_list(hf_spots), "vhf": get_top_for_list(vhf_spots)})

@app.route('/watchlist.json', methods=['GET', 'POST', 'DELETE'])
def manage_watchlist():
    if request.method == 'GET':
        return jsonify(sorted(list(watchlist)))
    data = request.get_json(force=True, silent=True)
    if not data or 'call' not in data:
        return abort(400)
    call = data['call'].upper().strip()
    if request.method == 'POST':
        watchlist.add(call)
        logger.info(f"Ajout à la watchlist: {call}")
    if request.method == 'DELETE' and call in watchlist:
        watchlist.remove(call)
        logger.info(f"Retrait de la watchlist: {call}")
    save_watchlist()
    return jsonify({"status": "ok"})
@app.get("/api/watchlist/tracking.json")
def api_watchlist_tracking():
    """Tracking watchlist: derniers spots par call (alimente le pavé Index)."""
    try:
        limit = int(request.args.get("limit", 10))
    except Exception:
        limit = 10
    limit = max(1, min(limit, 50))

    q = (request.args.get("q") or "").strip().upper()
    dx_only = (request.args.get("dx_only", "1").strip() not in ("0", "false", "False"))

    calls = sorted(list(watchlist))
    if q:
        calls = [c for c in calls if q in c]

    wanted = set(calls)
    out = {c: [] for c in calls}
    now = time.time()

    with spot_history_lock:
        hist = list(spot_history)

    for s in reversed(hist):
        try:
            dx = (s.get("dx") or "").strip().upper()
            de = (s.get("de") or "").strip().upper()

            hit = None
            if dx in wanted:
                hit = dx
            elif (not dx_only) and de in wanted:
                hit = de

            if not hit:
                continue
            if len(out[hit]) >= limit:
                continue

            ts = float(s.get("ts", now))
            out[hit].append({
                "utc": time.strftime("%H:%M", time.gmtime(ts)),
                "age_min": int((now - ts) / 60),
                "band": s.get("band"),
                "mode": s.get("mode"),
                "freq_khz": s.get("freq_khz"),
                "de": s.get("de"),
                "dx": s.get("dx"),
            })
        except Exception:
            continue

        if calls and all(len(out[c]) >= limit for c in calls):
            break

    return jsonify({
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "limit": limit,
        "dx_only": dx_only,
        "q": q,
        "calls": out
    })

@app.route('/rss.json')
def get_rss():
    return jsonify({"ticker": ticker_info["text"]})

def _get_recent_spots_fallback(minutes: int = 15, limit: int = 300):
    """
    Récupère les spots récents depuis les structures globales probables.
    Ne crashe jamais : retourne une liste (éventuellement vide).
    """
    import time

    now = time.time()
    min_ts = now - (minutes * 60)

    # Liste de noms globaux courants dans ce type d'app
    candidates = [
        "spots_history",
        "recent_spots",
        "spots_buffer",
        "spots",
        "SPOTS",
        "telnet_spots",
        "cluster_spots",
    ]

    container = None
    for name in candidates:
        if name in globals():
            container = globals()[name]
            break

    if container is None:
        return []

    # Convertit en liste
    try:
        items = list(container)
    except Exception:
        return []

    # Filtre temporel (essaie plusieurs clés possibles)
    def ts_of(s):
        if not isinstance(s, dict):
            return None
        for k in ("t", "ts", "time_ts", "timestamp", "epoch", "created_ts"):
            v = s.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return None

    filtered = []
    for s in reversed(items):  # souvent plus récent à la fin
        if isinstance(s, dict):
            ts = ts_of(s)
            if ts is None or ts >= min_ts:
                filtered.append(s)
        if len(filtered) >= limit:
            break

    # on remet dans l'ordre chrono
    return list(reversed(filtered))


@app.route("/api/map/spots")
def api_map_spots():
    minutes = int(request.args.get("minutes", 15))
    limit = int(request.args.get("limit", 300))
    band = (request.args.get("band") or "").strip()
    mode = (request.args.get("mode") or "").strip()

    # 1) Récupère les spots récents depuis TON buffer/stock (ex: deque spots_history)
    spots = _get_recent_spots_fallback(minutes=minutes, limit=limit)

    # 2) Filtre simple
    if band:
        spots = [s for s in spots if (s.get("band") == band)]
    if mode:
        spots = [s for s in spots if (s.get("mode") == mode)]

    # 3) Ajoute lat/lon (si déjà présents, garde; sinon enrichis via cty.dat)
    #    Ici: on suppose que ton pipeline met déjà lat/lon dans chaque spot.
    qth = {"lat": user_lat, "lon": user_lon, "qra": user_qra}

    return jsonify({
        "ok": True,
        "minutes": minutes,
        "count": len(spots),
        "qth": qth,
        "spots": spots
    })

# =========================================================
# FORECAST / WORLD MAP — V1 (proxy local, non prédictif)
# =========================================================

def classify_cluster(cluster_spots):
    """Classifie un cluster avec règles simples et explicables."""
    if not cluster_spots:
        return "suspect", "low", {"spot_count": 0, "unique_calls": 0, "duration_min": 0}

    spot_count = len(cluster_spots)
    calls = set()
    timestamps = []

    for s in cluster_spots:
        dx = s.get("dx_call") or s.get("dx")
        if dx:
            calls.add(dx)
        ts = s.get("timestamp")
        if isinstance(ts, (int, float)):
            timestamps.append(ts)

    unique_calls = len(calls)
    duration_min = int((max(timestamps) - min(timestamps)) / 60) if timestamps else 0

    if spot_count >= 6 and unique_calls >= 3 and duration_min >= 10:
        status, confidence = "confirmed", "high"
    elif spot_count >= 3:
        status, confidence = "suspect", "medium"
    else:
        status, confidence = "suspect", "low"

    return status, confidence, {
        "spot_count": spot_count,
        "unique_calls": unique_calls,
        "duration_min": duration_min
    }

@app.route("/api/forecast/anomalies")
def api_forecast_anomalies():
    try:
        band = request.args.get("band", "all")
        window_min = int(request.args.get("window", 180))

        now = time.time()
        since_ts = now - window_min * 60

        spots = [
            s for s in spots_buffer
            if s.get("timestamp", 0) >= since_ts
            and (band == "all" or s.get("band") == band)
            and s.get("lat") is not None
            and s.get("lon") is not None
        ]

        if not spots:
            return jsonify({
                "ok": True,
                "mode": "calibration",
                "clusters": [],
                "count": 0,
                "spot_count": 0
            })

        # ---------- distance km ----------
        def distance_km(a, b):
            R = 6371.0
            lat1 = math.radians(a["lat"])
            lon1 = math.radians(a["lon"])
            lat2 = math.radians(b["lat"])
            lon2 = math.radians(b["lon"])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            h = math.sin(dlat / 2)**2 + \
                math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
            return 2 * R * math.asin(math.sqrt(h))

        # ---------- clustering ----------
        MAX_DIST_KM = 250
        clusters = []

        for spot in spots:
            added = False
            for cluster in clusters:
                if distance_km(spot, cluster["center"]) <= MAX_DIST_KM:
                    cluster["spots"].append(spot)
                    added = True
                    break
            if not added:
                clusters.append({
                    "center": {"lat": spot["lat"], "lon": spot["lon"]},
                    "spots": [spot]
                })

        results = []

        for c in clusters:
            spots_c = c["spots"]
            timestamps = [s["timestamp"] for s in spots_c]
            calls = {s.get("dx") for s in spots_c if s.get("dx")}

            duration_min = int((max(timestamps) - min(timestamps)) / 60)
            spot_count = len(spots_c)
            unique_calls = len(calls)

            if spot_count < 3:
                status = "calibration"
                confidence = "low"
            elif spot_count < 6 or duration_min < 20:
                status = "suspect"
                confidence = "medium"
            else:
                status = "confirmed"
                confidence = "high"

            results.append({
                "band": band,
                "center": c["center"],
                "status": status,
                "confidence": confidence,
                "metrics": {
                    "spot_count": spot_count,
                    "unique_calls": unique_calls,
                    "duration_min": duration_min
                },
                "examples": [
                    {
                        "dx": s.get("dx"),
                        "freq_khz": s.get("freq"),
                        "mode": s.get("mode"),
                        "utc": datetime.utcfromtimestamp(
                            s["timestamp"]
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    }
                    for s in spots_c[:3]
                ]
            })

        if any(r["status"] == "confirmed" for r in results):
            mode = "active"
        elif any(r["status"] == "suspect" for r in results):
            mode = "suspect"
        else:
            mode = "calibration"

        return jsonify({
            "ok": True,
            "mode": mode,
            "clusters": results,
            "count": len(results),
            "spot_count": len(spots)
        })

    except Exception as e:
        logger.exception("api_forecast_anomalies failed")
        return jsonify({
            "ok": False,
            "error": str(e),
            "mode": "error",
            "clusters": []
        }), 500


def distance_km(a, b):
    """Distance Haversine en km entre deux points dict {'lat','lon'}"""
    R = 6371.0

    lat1 = math.radians(a["lat"])
    lon1 = math.radians(a["lon"])
    lat2 = math.radians(b["lat"])
    lon2 = math.radians(b["lon"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = math.sin(dlat / 2)**2 + \
        math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2

    return 2 * R * math.asin(math.sqrt(h)) 

@app.route("/api/forecast/heatmap.png")
def api_forecast_heatmap():
    from PIL import Image
    import io

    w = int(request.args.get("w", 720))
    h = int(request.args.get("h", 360))

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(buf.getvalue(), mimetype="image/png")

# --- SOLAR ROUTES (XML + JSON) ---
@app.route('/solar.xml')
@app.route('/api/solar.xml')
def get_solar_xml():
    with solar_lock:
        xml = solar_xml_cache
    return Response(xml, mimetype='application/xml; charset=utf-8')

@app.route('/solar.json')
@app.route('/api/solar.json')
def get_solar_json():
    with solar_lock:
        data = dict(solar_cache)
    return jsonify(data)
# --- END SOLAR ROUTES ---


# --- DX BRIEFING (Data-to-Text, deterministic, cached) ---
dx_briefing_lock = threading.Lock()
dx_briefing_cache = {
    "ts": 0.0,
    "fr": None,
    "en": None,
}

def _to_int(x):
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x)
        m = re.search(r"(-?\d+)", s)
        return int(m.group(1)) if m else None
    except Exception:
        return None

def _to_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x)
        m = re.search(r"(-?\d+(?:\.\d+)?)", s)
        return float(m.group(1)) if m else None
    except Exception:
        return None

def _sfi_status(sfi):
    if sfi is None:
        return ("UNKNOWN", "N/A")
    if sfi < 90:
        return ("POOR", "SFI<90")
    if sfi < 120:
        return ("FAIR", "90≤SFI<120")
    if sfi < 160:
        return ("GOOD", "120≤SFI<160")
    return ("EXCELLENT", "SFI≥160")

def _geomag_status(a_idx, k_idx):
    # Simple, readable status
    if a_idx is None and k_idx is None:
        return ("UNKNOWN", "A/K=N/A")
    # Prefer K when available (more direct short-term indicator)
    if k_idx is not None:
        if k_idx <= 2:
            return ("QUIET", "K≤2")
        if k_idx <= 4:
            return ("UNSETTLED", "2<K≤4")
        if k_idx <= 6:
            return ("ACTIVE", "4<K≤6")
        return ("STORM", "K>6")
    # Fallback to A
    if a_idx is not None:
        if a_idx <= 10:
            return ("QUIET", "A≤10")
        if a_idx <= 20:
            return ("UNSETTLED", "10<A≤20")
        if a_idx <= 50:
            return ("ACTIVE", "20<A≤50")
        return ("STORM", "A>50")
    return ("UNKNOWN", "A/K=N/A")

def _hf_outlook_text(sfi, k_idx, lang="fr"):
    # Keep it practical and short. K makes things unstable.
    k_penalty = (k_idx is not None and k_idx >= 4)
    if lang == "en":
        if sfi is None:
            base = "HF outlook uncertain (missing SFI)."
        elif sfi < 90:
            base = "HF likely poor: focus on 40/80m at night; 10/12m mostly closed."
        elif sfi < 120:
            base = "HF fair: 15–20m often workable; 10–12m unstable."
        elif sfi < 160:
            base = "HF good: 10–12–15m may open daytime; 20m strong."
        else:
            base = "HF excellent: 10–12m wide open potential; strong 15–20m."
        if k_penalty:
            base += " Geomagnetic conditions are unsettled: expect fades/auroral skew."
        return base

    # FR
    if sfi is None:
        base = "Prévision HF incertaine (SFI manquant)."
    elif sfi < 90:
        base = "HF faible : privilégie 40/80m la nuit ; 10/12m souvent fermés."
    elif sfi < 120:
        base = "HF correcte : 15–20m souvent praticables ; 10–12m instables."
    elif sfi < 160:
        base = "HF bonne : 10–12–15m possibles en journée ; 20m solide."
    else:
        base = "HF excellente : gros potentiel 10–12m ; 15–20m très forts."
    if k_penalty:
        base += " Géomagnétique agité : fades possibles, trajets polaires perturbés."
    return base

def build_dx_briefing(lang="fr"):
    lang = (lang or "fr").lower()
    lang = "en" if lang.startswith("en") else "fr"

    now = time.time()
    # Snapshot data (avoid holding locks too long)
    with solar_lock:
        sc = dict(solar_cache)

    sfi = _to_int(sc.get("sfi"))
    a_idx = _to_int(sc.get("a"))
    k_idx = _to_float(sc.get("k"))
    ts_utc = sc.get("ts_utc") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Analyze recent spots (lightweight)
    recent_window = 2 * 3600  # 2h for briefing
    active_window = 30 * 60   # 30m for "what's hot"
    now_ts = time.time()

    recent = [s for s in spots_buffer if (now_ts - s.get("timestamp", 0)) < recent_window]
    active = [s for s in recent if (now_ts - s.get("timestamp", 0)) < active_window]

    # Band activity (active 30m)
    band_counts = Counter(s.get("band") for s in active if s.get("band"))
    top_bands = [b for b, _ in band_counts.most_common(5)]

    # Mode activity (active 30m)
    mode_counts = Counter(s.get("mode") for s in active if s.get("mode"))
    top_modes = [m for m, _ in mode_counts.most_common(4)]

    # DXCC / Countries in 2h
    dxcc_counts = Counter(s.get("country") for s in recent if s.get("country") and s.get("country") != "Unknown")
    top_dxcc = [c for c, _ in dxcc_counts.most_common(5)]

    # Long distance calls (2h)
    long_calls = {s.get("dx_call") for s in recent if (s.get("distance_km") or 0) >= 10000 and s.get("dx_call")}
    long_calls_count = len(long_calls)

    # High SPD (rare)
    high_spd = [s for s in recent if (s.get("score") or 0) >= SPD_THRESHOLD]
    high_spd_count = len(high_spd)

    # Surges
    try:
        surges = analyze_surges()
    except Exception:
        surges = []

    sfi_stat, sfi_rule = _sfi_status(sfi)
    geo_stat, geo_rule = _geomag_status(a_idx, k_idx)

    if lang == "en":
        title = "DX Briefing"
        bullets = []

        bullets.append(f"Solar: SFI={sfi if sfi is not None else 'N/A'} ({sfi_stat}), A={a_idx if a_idx is not None else 'N/A'}, K={k_idx if k_idx is not None else 'N/A'} ({geo_stat}).")
        bullets.append(_hf_outlook_text(sfi, k_idx, lang="en"))

        if top_bands:
            bullets.append("Hot bands (30m): " + ", ".join(top_bands))
        if top_modes:
            bullets.append("Hot modes (30m): " + ", ".join(top_modes))
        if surges:
            bullets.append("Surge alerts: " + ", ".join(surges))
        if top_dxcc:
            bullets.append("Top DXCC (2h): " + ", ".join(top_dxcc))
        bullets.append(f"Long-distance calls (≥10,000 km / 2h): {long_calls_count}. High-SPD spots (2h): {high_spd_count}.")

        text = " ".join(bullets)

    else:
        title = "DX Briefing"
        bullets = []

        bullets.append(f"Solaire : SFI={sfi if sfi is not None else 'N/A'} ({sfi_stat}), A={a_idx if a_idx is not None else 'N/A'}, K={k_idx if k_idx is not None else 'N/A'} ({geo_stat}).")
        bullets.append(_hf_outlook_text(sfi, k_idx, lang="fr"))

        if top_bands:
            bullets.append("Bandes chaudes (30 min) : " + ", ".join(top_bands))
        if top_modes:
            bullets.append("Modes chauds (30 min) : " + ", ".join(top_modes))
        if surges:
            bullets.append("Alertes surge : " + ", ".join(surges))
        if top_dxcc:
            bullets.append("Top DXCC (2h) : " + ", ".join(top_dxcc))
        bullets.append(f"Longue distance (≥10 000 km / 2h) : {long_calls_count}. Spots rares (SPD≥{SPD_THRESHOLD}) sur 2h : {high_spd_count}.")

        text = " ".join(bullets)

    payload = {
        "ok": True,
        "version": APP_VERSION,
        "title": title,
        "lang": lang,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "solar_ts_utc": ts_utc,
        "briefing": text,
        "bullets": bullets,
        "metrics": {
            "sfi": sfi if sfi is not None else "N/A",
            "a": a_idx if a_idx is not None else "N/A",
            "k": k_idx if k_idx is not None else "N/A",
            "sfi_status": sfi_stat,
            "geomag_status": geo_stat,
            "top_bands_30m": top_bands,
            "top_modes_30m": top_modes,
            "surges": surges,
            "top_dxcc_2h": top_dxcc,
            "long_distance_calls_2h": long_calls_count,
            "high_spd_spots_2h": high_spd_count,
        }
    }
    return payload

@app.route('/api/dx_briefing.json')
@app.route('/dx_briefing.json')
def api_dx_briefing():
    """
    Deterministic DX briefing (cached, lightweight for Raspberry Pi).
    Query params:
      - lang=fr|en
      - force=1 to bypass cache
    """
    lang = (request.args.get('lang') or 'fr').lower()
    force = request.args.get('force') in ('1', 'true', 'yes')
    now = time.time()

    with dx_briefing_lock:
        cache_age = now - (dx_briefing_cache.get('ts') or 0.0)
        cached = dx_briefing_cache.get('en' if lang.startswith('en') else 'fr')
        if (not force) and cached is not None and cache_age < 600:  # 10 minutes
            return jsonify(cached)

    payload = build_dx_briefing(lang=lang)
    with dx_briefing_lock:
        dx_briefing_cache['ts'] = now
        dx_briefing_cache[payload['lang']] = payload
    return jsonify(payload)
# --- END DX BRIEFING ---


def _strip_html(value: str) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()

def _entry_timestamp(entry) -> float:
    for key in ("published_parsed", "updated_parsed"):
        ts = entry.get(key)
        if ts:
            return float(calendar.timegm(ts))
    return time.time()

def _entry_summary(entry, limit: int = 220) -> str:
    summary = entry.get("summary") or entry.get("description") or ""
    summary = _strip_html(summary)
    if len(summary) > limit:
        return summary[: limit - 1].rstrip() + "…"
    return summary

def _load_briefing_sources():
    if BRIEFING_SOURCES_FILE.exists():
        try:
            data = json.loads(BRIEFING_SOURCES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [
                    src for src in data
                    if isinstance(src, dict) and src.get("url") and src.get("name")
                ]
        except Exception:
            pass
    return BRIEFING_DEFAULT_SOURCES

def _fetch_feed(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": BRIEFING_USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=BRIEFING_FEED_TIMEOUT) as r:
        data = r.read()
    return feedparser.parse(data)

def _fetch_html(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": BRIEFING_USER_AGENT, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=BRIEFING_FEED_TIMEOUT) as r:
        return r.read().decode("utf-8", errors="ignore")

def fetch_qo100_news(timeout: int = 10):
    """
    Récupère les titres, dates et liens des articles QO-100 DX.
    """
    try:
        response = requests.get(QO100_NEWS_URL, headers=QO100_HEADERS, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("article")
    results = []

    for article in articles:
        h2 = article.find("h2")
        if not h2:
            continue

        link_tag = h2.find("a")
        if not link_tag or not link_tag.get("href"):
            continue

        title = link_tag.get_text(strip=True)
        link = link_tag["href"]
        if link.startswith("/"):
            link = "https://qo100dx.club" + link

        date_obj = None
        date_str = ""

        time_tag = article.find("time")
        if time_tag:
            date_str = time_tag.get_text(strip=True)
            try:
                date_obj = datetime.fromisoformat(time_tag.get("datetime"))
            except Exception:
                date_obj = None

        results.append({
            "title": title,
            "date": date_obj,
            "date_str": date_str,
            "link": link,
        })

    results.sort(
        key=lambda x: x["date"] if x["date"] else datetime.min,
        reverse=True
    )

    return results

def _extract_html_items(source_id: str, html_text: str, limit: int):
    soup = BeautifulSoup(html_text, "html.parser")
    items = []

    if source_id == "dxnews":
        for article in soup.select("article"):
            title_link = article.select_one("h1 a, h2 a, h3 a")
            if not title_link:
                continue
            title = _strip_html(title_link.get_text(strip=True))
            link = title_link.get("href")
            summary_parts = []
            for para in article.select("p")[:2]:
                text = _strip_html(para.get_text(strip=True))
                if text:
                    summary_parts.append(text)
            summary = "\n".join(summary_parts)
            time_tag = article.select_one("time")
            published = time_tag.get("datetime") if time_tag else None
            items.append({
                "title": title or "Sans titre",
                "link": link,
                "published_utc": published,
                "summary": summary,
            })
            if len(items) >= limit:
                break

    elif source_id == "ng3k":
        for row in soup.select("table tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue
            title = _strip_html(cols[0].get_text(" ", strip=True))
            detail = _strip_html(cols[1].get_text(" ", strip=True))
            link_tag = cols[0].find("a") or cols[1].find("a")
            href = link_tag.get("href") if link_tag else None
            if not title:
                continue
            items.append({
                "title": title,
                "link": href,
                "published_utc": None,
                "summary": detail,
            })
            if len(items) >= limit:
                break

    elif source_id == "dxmaps":
        for row in soup.select("table tr"):
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            title = _strip_html(cols[0].get_text(" ", strip=True))
            detail = _strip_html(cols[1].get_text(" ", strip=True))
            link_tag = cols[0].find("a") or cols[1].find("a")
            href = link_tag.get("href") if link_tag else None
            if not title:
                continue
            items.append({
                "title": title,
                "link": href,
                "published_utc": None,
                "summary": detail,
            })
            if len(items) >= limit:
                break

    elif source_id == "qo100dx":
        for entry in fetch_qo100_news(timeout=BRIEFING_FEED_TIMEOUT):
            items.append({
                "title": entry.get("title") or "Sans titre",
                "link": entry.get("link"),
                "published_utc": entry.get("date_str") or None,
                "summary": "",
            })
            if len(items) >= limit:
                break

    return items

def _build_briefing_payload(limit: int = BRIEFING_ITEM_LIMIT):
    sources = _load_briefing_sources()
    source_payloads = []
    combined_items = []
    now = time.time()

    for src in sources:
        fetched_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        items = []
        status = "ok"
        error = None

        try:
            source_type = src.get("type", "rss")
            if source_type == "html":
                source_id = src.get("id", "")
                html_text = ""
                if source_id != "qo100dx":
                    html_text = _fetch_html(src["url"])
                extracted = _extract_html_items(source_id, html_text, limit)
                for entry in extracted:
                    items.append({
                        "title": entry.get("title") or "Sans titre",
                        "link": entry.get("link"),
                        "published_utc": entry.get("published_utc"),
                        "summary": entry.get("summary") or "",
                        "source_id": src.get("id"),
                        "timestamp": now,
                    })
            else:
                parsed = _fetch_feed(src["url"])
                entries = parsed.entries or []
                for entry in entries[: limit * 2]:
                    ts = _entry_timestamp(entry)
                    item = {
                        "title": _strip_html(entry.get("title", "Sans titre")) or "Sans titre",
                        "link": entry.get("link"),
                        "published_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
                        "summary": _entry_summary(entry),
                        "source_id": src.get("id"),
                        "timestamp": ts,
                    }
                    items.append(item)
            items.sort(key=lambda it: it["timestamp"], reverse=True)
            items = items[:limit]
            combined_items.extend(items)
        except Exception as exc:
            status = "error"
            error = str(exc)

        source_payloads.append({
            "id": src.get("id"),
            "name": src.get("name"),
            "url": src.get("url"),
            "site": src.get("site"),
            "status": status,
            "error": error,
            "fetched_utc": fetched_utc,
            "items": items,
        })

    combined_items.sort(key=lambda it: it["timestamp"], reverse=True)
    combined_items = combined_items[: limit * 2]

    for item in combined_items:
        item.pop("timestamp", None)

    payload = {
        "ok": True,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "cache": {
            "ttl_seconds": BRIEFING_CACHE_TTL,
            "generated_epoch": now,
        },
        "sources": source_payloads,
        "items": combined_items,
        "total_sources": len(source_payloads),
    }
    return payload

briefing_lock = threading.Lock()
briefing_cache = {
    "ts": 0.0,
    "payload": None,
}

def briefing_refresh_worker():
    logger = logging.getLogger(__name__)
    while True:
        now = time.time()
        try:
            payload = _build_briefing_payload(limit=BRIEFING_ITEM_LIMIT)
            payload["cache"]["age_seconds"] = 0
            payload["cache"]["next_refresh_utc"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + BRIEFING_CACHE_TTL)
            )
            with briefing_lock:
                briefing_cache["ts"] = now
                briefing_cache["payload"] = payload
            logger.info("Briefing cache refreshed.")
        except Exception as exc:
            logger.warning(f"Briefing refresh failed: {exc}")
        time.sleep(BRIEFING_CACHE_TTL)

@app.route("/briefing")
@app.route("/briefing.html")
def briefing_page():
    return render_template("briefing.html")

@app.route("/api/briefing.json")
def api_briefing():
    limit = int(request.args.get("limit", BRIEFING_ITEM_LIMIT))
    force = request.args.get("force") in ("1", "true", "yes")
    now = time.time()

    with briefing_lock:
        cache_age = now - (briefing_cache.get("ts") or 0.0)
        cached = briefing_cache.get("payload")
        if (not force) and cached is not None and cache_age < BRIEFING_CACHE_TTL:
            cached["cache"]["age_seconds"] = int(cache_age)
            cached["cache"]["next_refresh_utc"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(briefing_cache["ts"] + BRIEFING_CACHE_TTL)
            )
            return jsonify(cached)

    payload = _build_briefing_payload(limit=limit)
    payload["cache"]["age_seconds"] = 0
    payload["cache"]["next_refresh_utc"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + BRIEFING_CACHE_TTL)
    )
    with briefing_lock:
        briefing_cache["ts"] = now
        briefing_cache["payload"] = payload
    return jsonify(payload)



@app.route('/history.json')
def get_history():
    now_utc = time.gmtime(time.time())
    current_hour = now_utc.tm_hour
    current_minute = now_utc.tm_min
    current_slot = ((current_hour * 2) + (current_minute // 30)) % HISTORY_SLOTS

    # Génère les labels pour les 12 dernières heures (24 slots de 30 min)
    labels = []
    for i in range(HISTORY_SLOTS):
        slot = (current_slot - i + HISTORY_SLOTS) % HISTORY_SLOTS
        hours_ago = (HISTORY_SLOTS - 1 - i) * HISTORY_PERIOD_MINUTES // 60
        minutes_ago = (HISTORY_SLOTS - 1 - i) * HISTORY_PERIOD_MINUTES % 60
        target_hour = (current_hour - hours_ago) % 24
        target_minute = (current_minute - minutes_ago) % 60
        labels.append(f"H-{hours_ago:02d}:{minutes_ago:02d}")

    with history_lock:
        data = {band: list(hist) for band, hist in history_30min.items()}

    # Rotate data to show most recent first (H-00:30, H-01:00, etc.)
    current_data = {}
    for band in HISTORY_BANDS:
        rotated = data[band][current_slot:] + data[band][:current_slot]
        current_data[band] = rotated

    return jsonify({"labels": labels, "data": current_data})

@app.route('/live_bands.json')
def get_live_bands_data():
    now = time.time()
    active_spots = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    hf_spots = [s for s in active_spots if s['type'] == 'HF']
    vhf_spots = [s for s in active_spots if s['type'] == 'VHF']
    hf_counts = Counter(s['band'] for s in hf_spots if s['band'] in HF_BANDS)
    vhf_counts = Counter(s['band'] for s in vhf_spots if s['band'] in VHF_BANDS)

    hf_data = {
        "labels": [b for b in HF_BANDS if hf_counts[b] > 0],
        "data": [hf_counts[b] for b in HF_BANDS if hf_counts[b] > 0],
        "colors": [BAND_COLORS[b] for b in HF_BANDS if hf_counts[b] > 0]
    }
    vhf_data = {
        "labels": [b for b in VHF_BANDS if vhf_counts[b] > 0],
        "data": [vhf_counts[b] for b in VHF_BANDS if vhf_counts[b] > 0],
        "colors": [BAND_COLORS[b] for b in VHF_BANDS if vhf_counts[b] > 0]
    }
    return jsonify({"hf": hf_data, "vhf": vhf_data})




if __name__ == "__main__":
    load_cty_dat()
    load_watchlist()

    logger.info(f"\n--- {APP_VERSION} ---")
    logger.info(f"QTH de départ: {user_qra} ({user_lat:.2f}, {user_lon:.2f})")

    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    threading.Thread(target=solar_worker, daemon=True).start()
    threading.Thread(target=history_maintenance_worker, daemon=True).start()
    threading.Thread(target=briefing_refresh_worker, daemon=True).start()

    logger.info("Tous les Workers ont été démarrés. Lancement du serveur Flask...")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False)
