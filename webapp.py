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
from logging.handlers import TimedRotatingFileHandler
from collections import deque, Counter
from flask import Flask, render_template, jsonify, request, abort, redirect, url_for, Response


# --- CLUSTER TX (Spot) ---
tn_lock = threading.Lock()
tn_current = None  # telnetlib.Telnet when connected
# --- FIN CLUSTER TX ---
# --- CONFIGURATION GENERALE ---
APP_VERSION = "NEURAL AI v4.7 - corrections mineures + DXCC update"
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
    'YK', 'VK0', 'VK9', 'VP0' , 'V21', 'XF4', 'XZ', 'ZK', 'ZL8', 'ZL7', 'ZL9',
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

# --- SOLAR (XML) FETCHER ---
def fetch_solar_from_wwv_txt():
    """
    Fetch solar indices from NOAA SWPC wwv.txt and update solar_cache + solar_xml_cache.
    Runs hourly in solar_worker().
    """
    global solar_cache, solar_xml_cache
    try:
        req = urllib.request.Request(SOLAR_URL, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode('utf-8', errors='ignore')

        # Robust parsing (wwv.txt format varies)
        sfi = a_idx = k_idx = "N/A"

        # Common patterns
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

        with solar_lock:
            solar_cache = {"sfi": sfi, "a": a_idx, "k": k_idx, "ts_utc": ts}
            solar_xml_cache = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<solar>'
                f'<sfi>{sfi}</sfi>'
                f'<a>{a_idx}</a>'
                f'<k>{k_idx}</k>'
                f'<updated_utc>{ts}</updated_utc>'
                '</solar>'
            )
        logger.info(f"SOLAR updated (xml): SFI={sfi} A={a_idx} K={k_idx}")

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
# --- END SOLAR (XML) FETCHER ---


# --- CACHES GLOBAUX et INITIALISATION QTH ---
spots_buffer = deque(maxlen=6000)
band_history = {}
prefix_db = {}
ticker_info = {"text": "SYSTEM INITIALIZATION... (Waiting for RSS/Solar data)"}

# --- SOLAR CACHE (XML/JSON) ---
solar_lock = threading.Lock()
solar_cache = {"sfi": "N/A", "a": "N/A", "k": "N/A", "ts_utc": None}
solar_xml_cache = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><solar><sfi>N/A</sfi><a>N/A</a><k>N/A</k><updated_utc></updated_utc></solar>"
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
app = Flask(__name__)

# --- PLAGES DE FREQUENCES CW ---
CW_RANGES = [
    ('160m', 1.810, 1.838), ('80m', 3.500, 3.560), ('40m', 7.000, 7.035),
    ('30m', 10.100, 10.134), ('20m', 14.000, 14.069), ('17m', 18.068, 18.095),
    ('15m', 21.000, 21.070), ('12m', 24.890, 24.913), ('10m', 28.000, 28.070),
]

# --- FRÉQUENCES FT4/FT8 (en kHz) ---
FT8_VHF_FREQ_RANGE_KHZ = (144171, 144177)

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
                        logger.info(f"SPOT: {dx_call} ({band}, {mode}) -> SPD: {spd_score} pts (Dist: {dist_km:.0f}km)")
                    except Exception as e:
                        logger.error(f"Erreur de traitement du spot '{line[:50]}...': {e}")

        except Exception as e:
            logger.error(f"ERREUR CRITIQUE Cluster {host}:{port}: {e}. Basculement vers un autre cluster.")
            time.sleep(10)

        idx = (idx + 1) % len(CLUSTERS)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION, my_call=MY_CALL,
                           hf_bands=HF_BANDS, vhf_bands=VHF_BANDS, band_colors=BAND_COLORS,
                           spd_threshold=SPD_THRESHOLD, user_qra=user_qra)

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
        
        # Clés pour les listes dynamiques
        "rare_dxcc_entities": sorted(list(rare_dxcc_entities)), 
        "long_distance_calls_count": len(long_distance_calls), 
        "long_distance_calls": sorted(list(long_distance_calls))
    })

# --- NOUVELLES ROUTES AI INSIGHT (SIMULÉES) ---

@app.route('/ai_pattern_data.json')
def ai_pattern_data():
    """Simule les données du Moteur de Corrélation Cognitive DX."""
    data = {
        "status": "PATTERN MATCH 90%",
        "active": True,
        "prediction": "Probabilité de DX : 85% (Bande 10m, Région Afrique de l'Ouest, Fenêtre : 19:15-20:00 UTC).",
        "justification": "Le décalage de la Grayline combiné à la remontée de l'indice Kp suggère une ouverture F2 oblique de courte durée. Recommandation : Surveiller le 10m.",
        "triggers": [
            {"band": "15m", "mode": "FT8", "region": "EU-JA", "value": "+2.5 σ", "color": "var(--alert)"},
            {"band": "20m", "mode": "CW", "region": "NA-AUS", "value": "+1.8 σ", "color": "var(--accent)"}
        ]
    }
    return jsonify(data)

@app.route('/ai_solar_data.json')
def ai_solar_data():
    """Simule les données du Propagateur Solaire-Terrestre."""
    data = {
        "global_score": "B+",
        "alert_message": "Le SFI a augmenté de 5 points (SFI 145). L'IA anticipe une amélioration dans 3 heures. Poids 10m/12m augmenté de 10 SPD.",
        "band_impact": [
            {"band": "20m / 40m", "recommendation": "A+ (Stable)", "color": "var(--success)"},
            {"band": "10m / 12m", "recommendation": "B (Fluctuant)", "color": "var(--open-color)"},
            {"band": "160m", "recommendation": "C- (Absorption)", "color": "var(--alert)"}
        ]
    }
    return jsonify(data)

@app.route('/ai_path_data.json')
def ai_path_data():
    """Simule les données du Path Optimizer pour un spot donné."""
    # Coordonnées du QTH (F1SMV, JN23)
    user_lat, user_lon = 43.10, 5.88 
    
    # Spot d'exemple (ZL1ABC, RF79)
    dx_call = "ZL1ABC"
    dx_lat, dx_lon = -36.84, 174.74 
    
    # Chemin Optimal (simulant la Grayline ou un rebond)
    optimal_path_coords = [
        [user_lat, user_lon],
        [30, 25],  # Point intermédiaire simulé
        [dx_lat, dx_lon]
    ]
    
    # Chemin Non Optimal (simulant le trajet long avec mauvaise propagation)
    long_path_coords = [
        [user_lat, user_lon],
        [-10, 100], 
        [dx_lat, dx_lon]
    ]

    data = {
        "dx_call": dx_call,
        "dx_lat": dx_lat,
        "dx_lon": dx_lon,
        "optimal_path_coords": optimal_path_coords,
        "long_path_coords": long_path_coords,
        "conclusion": "Le trajet optimal (vert) passe par la Grayline du Pacifique Nord, évitant l'absorption par l'ionosphère nocturne. Recommandé : 20m SSB."
    }
    return jsonify(data)

# --- FIN DES NOUVELLES ROUTES AI INSIGHT ---

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

@app.route('/rss.json')
def get_rss():
    return jsonify({"ticker": ticker_info["text"]})


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

    logger.info("Tous les Workers ont été démarrés. Lancement du serveur Flask...")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False)