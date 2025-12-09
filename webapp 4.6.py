import time
import telnetlib
import threading
import json
import os
import urllib.request
import feedparser
import ssl
import math 
import logging
import re 
from logging.handlers import TimedRotatingFileHandler
from collections import deque, Counter 
from flask import Flask, render_template, jsonify, request, abort, redirect, url_for 
from datetime import datetime, timedelta

# --- CONFIGURATION GENERALE ---
APP_VERSION = "NEURAL AI v4.6 - Ticker/Map/Propag Fix" # Version mise à jour
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 1800 
SPD_THRESHOLD = 70
TOP_RANKING_LIMIT = 10 
DEFAULT_QRA = "JN23"

# --- FICHIER DE LOG ---
LOG_FILE = "radio_spot_watcher.log" 

# --- CONFIGURATION SURGE ---
SURGE_WINDOW = 900
SURGE_THRESHOLD = 3.0
MIN_SPOTS_FOR_SURGE = 3

# --- CONFIGURATION ASTRO/MÉTEOR SCATTER --
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
HISTORY_BANDS = ['12m', '10m', '6m'] 

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
]
CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"
WATCHLIST_FILE = "watchlist.json"
SOLAR_URL = "https://services.swpc.noaa.gov/text/wwv.txt"

# --- CACHES GLOBAUX et INITIALISATION QTH ---
spots_buffer = deque(maxlen=6000)
band_history = {}
prefix_db = {}
# Mise à jour de l'initialisation pour le panneau Propag
ticker_info = {
    "text": "SYSTEM INITIALIZATION... (Waiting for RSS/Solar data)",
    "solar_data": {"sfi": "?", "a": "?", "k": "?", "meteor": "Unknown"},
    "rss_data": "SYSTEM INITIALIZATION..."
} 
watchlist = set()
surge_bands = [] 
latest_alert = None # Variable pour l'alerte vocale TTS

history_24h = {band: [0] * 24 for band in HISTORY_BANDS}
history_lock = threading.Lock()
surge_lock = threading.Lock()

# --- CONFIGURATION DU LOGGER ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(threadName)s: %(message)s'
formatter = logging.Formatter(LOG_FORMAT, datefmt='%Y-%M-%d %H:%M:%S')
file_handler = TimedRotatingFileHandler(
    LOG_FILE, when='midnight', interval=1, backupCount=1, encoding='utf-8'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


# --- FLASK APP INITIALIZATION ---
app = Flask(__name__) 

user_qra = DEFAULT_QRA
user_lat, user_lon = 0.0, 0.0

# --- PLAGES DE FREQUENCES & MODES ---
FREQ_RANGES = [
    ('160m', 1.800, 2.000, 'HF'), ('80m', 3.500, 4.000, 'HF'), ('60m', 5.000, 5.450, 'HF'),
    ('40m', 7.000, 7.300, 'HF'), ('30m', 10.100, 10.150, 'HF'), ('20m', 14.000, 14.350, 'HF'),
    ('17m', 18.068, 18.168, 'HF'), ('15m', 21.000, 21.450, 'HF'), ('12m', 24.890, 24.990, 'HF'),
    ('10m', 28.000, 29.700, 'HF'), ('6m', 50.000, 54.000, 'HF'),
    ('4m', 70.000, 70.500, 'VHF'), ('2m', 144.000, 148.000, 'VHF'),
    ('70cm', 430.000, 440.000, 'VHF'), ('23cm', 1240.000, 1300.000, 'VHF'), ('QO-100', 10489.000, 10490.000, 'VHF'),
]
CW_RANGES = [
    ('160m', 1.810, 1.838), ('80m', 3.500, 3.560), ('40m', 7.000, 7.035),
    ('30m', 10.100, 10.134), ('20m', 14.000, 14.069), ('17m', 18.068, 18.095),
    ('15m', 21.000, 21.070), ('12m', 24.890, 24.913), ('10m', 28.000, 28.070),
]
MODES = ['CW', 'SSB', 'FT8', 'FT4', 'RTTY', 'MSK144', 'FM'] # Liste pour le filtre

# --- SSL BYPASS ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError: pass
else: ssl._create_default_https_context = _create_unverified_https_context


# --- FONCTIONS UTILITAIRES ET DE TRAITEMENT ---

def qra_to_lat_lon(qra):
    """ Convertit un locator QRA (Maidenhead) en coordonnées latitude/longitude. """
    try:
        qra = qra.upper().strip()
        if len(qra) < 4: return 0.0, 0.0
        
        # Champ (4000 km x 2000 km, 20° long x 10° lat)
        lon = -180 + (ord(qra[0]) - ord('A')) * 20 + (int(qra[2]) * 2) + 1
        lat = -90 + (ord(qra[1]) - ord('A')) * 10 + (int(qra[3]) * 1) + 0.5
        
        # Carré (166 km x 83 km, 2° long x 1° lat)
        if len(qra) >= 6:
            lon += (ord(qra[4]) - ord('A')) * (2/24) + (1/24)
            lat += (ord(qra[5]) - ord('A')) * (1/24) + (1/48)
            
        return lat, lon
    except: 
        return 0.0, 0.0

def calculate_distance(lat1, lon1, lat2, lon2):
    """ Calcule la distance en km entre deux points (formule Haversine). """
    R = 6371  # Rayon de la Terre en km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def load_watchlist():
    """ Charge la liste d'indicatifs à surveiller depuis un fichier JSON. """
    global watchlist
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                watchlist = set([c.upper() for c in data if isinstance(c, str)])
            logger.info(f"Watchlist chargée: {len(watchlist)} indicatifs.")
        except: 
            logger.error("Erreur lors du chargement de la Watchlist.")
            pass

def save_watchlist():
    """ Sauvegarde la liste d'indicatifs dans un fichier JSON. """
    try:
        with open(WATCHLIST_FILE, "w") as f: 
            json.dump(sorted(list(watchlist)), f, indent=4)
    except Exception as e: 
        logger.error(f"Erreur lors de la sauvegarde de la Watchlist: {e}")

def load_cty_dat():
    """ Charge la base de données DXCC (prefix_db) à partir de cty.dat. """
    global prefix_db
    prefix_db = {}
    
    if not os.path.exists(CTY_FILE):
        logger.info("Tentative de téléchargement de cty.dat pour la base de données DXCC...")
        try:
            # Utilisez un User-Agent de base pour éviter le blocage par certains serveurs
            req = urllib.request.Request(CTY_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response, open(CTY_FILE, 'wb') as outfile:
                outfile.write(response.read())
            logger.info("cty.dat téléchargé avec succès.")
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de cty.dat: {e}. La localisation sera imprécise ou nulle.")
            return

    try:
        with open(CTY_FILE, 'r', encoding='latin-1') as f:
            lines = f.readlines()
            current_lat = 0.0
            current_lon = 0.0
            current_country = "Unknown"
            country_count = 0
            
            for i, line in enumerate(lines):
                if (i % 2) == 0:
                    parts = line.split(':')
                    if len(parts) < 6: continue
                    current_country = parts[0].strip()
                    try:
                        # DXCC fournit les coordonnées en +/-deg (ex: +48.8, -2.3)
                        current_lat = float(parts[4])
                        current_lon = float(parts[5])
                        country_count += 1
                    except ValueError:
                        continue
                else:
                    prefixes = [p.strip().replace('&', '') for p in line.split(',') if p.strip()]
                    
                    for prefix_raw in prefixes:
                        prefix = prefix_raw.split('(')[0].split('=')[0].split('<')[0].strip()
                        if not prefix: continue
                        
                        prefix_db[prefix] = {
                            'c': current_country, 
                            'lat': current_lat, 
                            'lon': current_lon
                        }
            
        logger.info(f"Base de données DXCC chargée: {len(prefix_db)} préfixes pour {country_count} entités.")
    except Exception as e:
        logger.error(f"Erreur de parsing de cty.dat: {e}. La localisation des spots sera inexacte.")

def get_country_info(call):
    """ Recherche les coordonnées et le pays pour un indicatif donné. """
    call = call.upper()
    
    # La logique de recherche du préfixe le plus long est maintenue
    for i in range(len(call), 0, -1):
        prefix = call[:i]
        if prefix in prefix_db:
            return prefix_db[prefix]
            
    # Cas extrême où l'indicatif n'est pas trouvé
    return {'c': 'Unknown', 'lat': 0.0, 'lon': 0.0}

def get_band_and_mode_from_spot(freq_mhz, comment):
    """ Détection Mode/Bande à partir de la fréquence en MHz et du commentaire. """
    band, b_type = 'Unknown', 'HF'
    
    for b, fmin, fmax, btype in FREQ_RANGES:
        if fmin <= freq_mhz < fmax: band, b_type = b, btype; break
            
    mode = 'SSB' 
    comment = comment.upper()
    
    if 'FT8' in comment: mode = 'FT8'
    elif 'CW' in comment: mode = 'CW'
    elif 'FT4' in comment: mode = 'FT4'
    elif 'RTTY' in comment: mode = 'RTTY'
    elif 'MSK144' in comment: mode = 'MSK144'
    elif 'FM' in comment: mode = 'FM'
    else:
        # Fallback par fréquence si pas de commentaire
        if (14.074 <= freq_mhz <= 14.078) or (7.074 <= freq_mhz <= 7.078) or (21.074 <= freq_mhz <= 21.078): mode = 'FT8'
        for b, fmin, fmax in CW_RANGES:
             if fmin <= freq_mhz <= fmax: mode = 'CW'; break
        if band == '2m' and abs(freq_mhz - MSK144_FREQ) < MSK144_TOLERANCE_KHZ: mode = 'MSK144'
        
    return band, mode, b_type

def calculate_spd(spot):
    """ Calcule le score de priorité de DX (SPD). """
    score = 0
    dist = spot.get('distance_km', 0)
    
    if dist > 3000: score = 20 + int(math.log(dist)*5)
    elif dist > 100: score = 10
    
    band = spot.get('band')
    if band in ['10m', '6m', '2m']: score += 15
    
    mode = spot.get('mode', '')
    if mode in ['CW', 'FT8', 'MSK144']: score += 10
    
    if spot.get('dx_call') in watchlist: score += 40
    with surge_lock:
        if band in surge_bands: score += 20
    
    return min(100, score)

def check_and_set_alert(spot):
    """Génère un message d'alerte TTS si le spot est important."""
    global latest_alert
    
    if spot['dx_call'] == MY_CALL or 'RCH' in spot['dx_call'] or 'DE' in spot['dx_call']:
        return 
        
    alert_message = None
    if spot['dx_call'] in watchlist:
        alert_message = f"ALERTE WATCHLIST. {spot['dx_call']} sur {spot['freq']:.3f} mégahertz, en bande {spot['band']}, mode {spot['mode']}. De {spot['country']}."
    elif spot['score'] >= SPD_THRESHOLD and spot['distance_km'] > 1000:
        alert_message = f"DX RARE. {spot['dx_call']} de {spot['country']} sur {spot['band']}, mode {spot['mode']}. Distance {int(spot['distance_km'])} kilomètres."
    
    if alert_message:
        latest_alert = {"time": time.time(), "message": alert_message}
        logger.warning(f"Alerte TTS générée: {alert_message}")

def process_spot_line(line):
    """ Analyse une ligne brute du cluster pour créer un objet spot. """
    line = line.strip()
    if line.upper().startswith("DX"):
        line = line[2:].strip()
    
    parts = line.split()

    try:
        freq_raw = None
        dx_call = None
        comment_start_index = 0
        
        for i, part in enumerate(parts):
            try:
                val = float(part)
                if val > 0.0 and val < 300000.0:
                    freq_raw = val
                    if i + 1 < len(parts):
                        dx_call = parts[i + 1]
                        if '-' in dx_call or re.match(r'^\d{4}Z?$', dx_call):
                            dx_call = None
                            continue
                            
                        comment_start_index = i + 2
                        break
            except ValueError:
                continue

        if not freq_raw or not dx_call:
            return None 

        comment_parts = parts[comment_start_index:]
        comment_full = " ".join(comment_parts)
        comment = re.sub(r'<[^>]+>', '', comment_full).strip()
        comment = re.sub(r'\s+', ' ', comment).strip()
        
        freq_mhz = freq_raw / 1000.0
        band, mode, btype = get_band_and_mode_from_spot(freq_mhz, comment)
        if band == 'Unknown': 
            return None
        
        # --- LOGIQUE DE LOCALISATION AMÉLIORÉE (QRA > DXCC) ---
        info = get_country_info(dx_call) 
        spot_lat, spot_lon = info['lat'], info['lon']
        country_display = info['c']
        
        # 1. Tenter de trouver le locator QRA dans le commentaire (ex: JN23, FN41fg)
        # Maidenhead regex: 2 lettres (A-R), 2 chiffres (0-9), optionnellement 2 lettres (A-X)
        qra_match = re.search(r'([A-R]{2}\d{2}([A-X]{2})?)', comment_full.upper())
        qra_from_comment = qra_match.group(1) if qra_match else None
        
        if qra_from_comment:
            qra_lat, qra_lon = qra_to_lat_lon(qra_from_comment)
            if qra_lat != 0.0 and qra_lon != 0.0:
                spot_lat, spot_lon = qra_lat, qra_lon
                country_display = f"{info['c']} ({qra_from_comment})" # Ajouter le QRA au nom du pays
                
        # 2. Calculer la distance avec la meilleure position trouvée
        dist = 0
        if spot_lat != 0 and user_lat != 0:
            dist = calculate_distance(user_lat, user_lon, spot_lat, spot_lon)

        spot = {
            'timestamp': time.time(), 'time': time.strftime("%H:%M:%S"),
            'freq': freq_mhz, 'dx_call': dx_call, 'comment': comment,
            'band': band, 'mode': mode, 'type': btype,
            'country': country_display, 
            'lat': spot_lat, 
            'lon': spot_lon,
            'distance_km': dist, 'color': BAND_COLORS.get(band, '#fff')
        }
        spot['score'] = calculate_spd(spot)
        return spot
        
    except Exception as e:
        logger.error(f"Erreur de parsing pour la ligne: {line}. Exception: {e}")
        return None


# --- THREADS DE TRAVAIL (WORKERS) ---

def telnet_worker():
    """ Thread pour la connexion et l'écoute du DX Cluster. """
    threading.current_thread().name = 'TelnetWorker'
    logger.info("TelnetWorker démarré.")
    idx = 0
    while True:
        host, port = CLUSTERS[idx % len(CLUSTERS)] 
        logger.info(f"Tentative de connexion au Cluster: {host}:{port} ({idx % len(CLUSTERS) + 1}/{len(CLUSTERS)})")
        try:
            tn = telnetlib.Telnet(host, port, timeout=10)
            try: tn.read_until(b"login: ", timeout=3) 
            except: pass 
            tn.write(MY_CALL.encode('latin-1') + b"\n")
            time.sleep(1) 
            tn.write(b"set/dx/filter\n") 
            tn.write(b"show/dx 50\n")
            logger.info(f"Connexion établie sur {host}:{port}. Écoute des spots en cours.")
            last_ping = time.time()
            while True:
                line = tn.read_until(b"\n", timeout=2) 
                if line:
                    spot = process_spot_line(line.decode('latin-1', errors='ignore'))
                    if spot:
                        spots_buffer.append(spot)
                        check_and_set_alert(spot)
                        with history_lock:
                            if spot['band'] in history_24h:
                                history_24h[spot['band']][datetime.utcnow().hour] += 1
                        logger.info(f"SPOT REÇU: {spot['dx_call']} sur {spot['band']} ({spot['mode']}) - Freq: {spot['freq']:.3f} MHz - Dist: {int(spot['distance_km'])} km - Comment: {spot.get('comment', '')[:20]}")
                        
                if time.time() - last_ping > KEEP_ALIVE:
                    tn.write(b"\r\n") 
                    last_ping = time.time()

        except EOFError: logger.warning(f"Connexion fermée par {host} (EOF). Passage au cluster suivant.")
        except Exception as e: logger.error(f"Erreur Telnet sur {host}: {type(e).__name__} - {e}")
        finally:
            idx = (idx + 1) % len(CLUSTERS)
            time.sleep(15)

def background_worker():
    """ Thread de maintenance (Ticker, Surge, Logique de fond). """
    threading.current_thread().name = 'BackgroundWorker'
    while True:
        try:
            now = time.time()
            active = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
            
            # 1. Mise à jour du Ticker (seulement le nombre de spots ici, le reste vient de rss_worker)
            ticker_info["text"] = ticker_info.get("rss_data", "SYSTEM INITIALIZATION...") + f" | {len(active)} SPOTS ACTIFS"
            
            # 2. Logique de détection de SURGE
            recent = [s for s in active if (now - s['timestamp']) < SURGE_WINDOW]
            counts = Counter(s['band'] for s in recent)
            with surge_lock:
                surge_bands.clear()
                surge_bands.extend([b for b, c in counts.items() if c >= MIN_SPOTS_FOR_SURGE and b in HISTORY_BANDS])
            
            time.sleep(60)
        except Exception as e:
            logger.error(f"Erreur dans BackgroundWorker: {e}")
            time.sleep(60)

def rss_worker():
    """ Thread pour la récupération des informations de propagation (Solar/RSS). """
    threading.current_thread().name = 'RSSWorker'
    while True:
        try:
            # 1. Récupération des données solaires (WWV)
            solar_data = urllib.request.urlopen(SOLAR_URL, timeout=10).read().decode('utf-8')
            
            # Parsing SFI/K/A index
            match_sfi = re.search(r'Solar Flux\s+:\s+(\d+)', solar_data)
            match_k = re.search(r'K-index\s+:\s+(\d+)\s+at\s+([0-9]{4} UT)', solar_data)
            match_a = re.search(r'A-index\s+:\s+(\d+)', solar_data)
            
            sfi_idx = match_sfi.group(1) if match_sfi else '?'
            k_idx = match_k.group(1) if match_k else '?'
            a_idx = match_a.group(1) if match_a else '?'

            # 2. Récupération des données DX World (RSS)
            rss_feed = feedparser.parse(RSS_URLS[0])
            rss_text = rss_feed.entries[0].title if rss_feed.entries else "DX NEWS: No recent news."
            
            # 3. Mise à jour des données structurées pour le panneau Propag
            meteor_shower = get_meteor_shower()
            solar_core_data = f"SFI: {sfi_idx} | A: {a_idx} | K: {k_idx}"
            
            ticker_info["solar_data"] = {
                "sfi": sfi_idx, 
                "a": a_idx, 
                "k": k_idx, 
                "meteor": meteor_shower,
                "solar_core": solar_core_data
            }
            
            # 4. Mise à jour du Ticker principal (texte résumé)
            # FIX Ticker: Raccourcir le texte à 40 caractères pour une meilleure lisibilité
            rss_core_data = f"DX NEWS: {rss_text[:40].strip().replace('|', ' ')}... | {solar_core_data} | MS: {meteor_shower}"
            ticker_info["rss_data"] = rss_core_data
            
        except Exception as e:
            logger.error(f"Erreur dans RSSWorker: {e}")
            ticker_info["rss_data"] = f"RSS/SOLAR DATA ERROR: {type(e).__name__}."
            ticker_info["solar_data"] = {"sfi": "?", "a": "?", "k": "?", "meteor": "ERROR", "solar_core": "SFI: ? | A: ? | K: ?"}
            
        time.sleep(900) # Mise à jour toutes les 15 minutes

def history_maintenance_worker():
    """ Thread de maintenance des données d'historique (rotation à minuit). """
    threading.current_thread().name = 'HistoryWorker'
    while True:
        now = datetime.utcnow()
        next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
        sleep_time = (next_midnight - now).total_seconds()
        
        logger.info(f"Prochaine réinitialisation de l'historique dans {int(sleep_time/3600)}h.")
        time.sleep(sleep_time) 
        
        with history_lock:
            for band in history_24h:
                history_24h[band] = [0] * 24 
            logger.info("Historique des spots 24h réinitialisé à minuit.")

def get_meteor_shower():
    """ Retourne la pluie de météores active si c'est le cas. """
    now = datetime.utcnow()
    for shower in METEOR_SHOWERS:
        start_date = datetime(now.year, shower['start'][0], shower['start'][1])
        end_date = datetime(now.year, shower['end'][0], shower['end'][1])
        
        # Gestion du chevauchement d'années (ex: Géminides Déc-Jan)
        if start_date.month > end_date.month and now.month == 12: 
            end_date = end_date.replace(year=now.year + 1)
        
        if start_date <= now <= end_date:
            return shower['name']
    return 'None'


# --- ROUTES FLASK ---

@app.route('/')
def index():
    return render_template('index.html', app_version=APP_VERSION, my_call=MY_CALL, 
                           default_qra=DEFAULT_QRA, hf_bands=HF_BANDS, vhf_bands=VHF_BANDS, band_colors=BAND_COLORS, modes=MODES)

@app.route('/spots.json')
def get_spots():
    now = time.time()
    all_s = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    return jsonify({'spots': all_s, 'new_spots': []}) 

@app.route('/history.json')
def get_hist():
    with history_lock:
        lbls = [f"{i:02d}h" for i in range(24)]
        data = {b: list(c) for b, c in history_24h.items()}
    return jsonify({'labels': lbls, 'data': data})

@app.route('/live_bands.json')
def get_live():
    now = time.time()
    active_spots = [s for s in spots_buffer if (now - s['timestamp']) < 1800]
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


@app.route('/surge.json')
def get_srg(): return jsonify({'surges': surge_bands})

# Le ticker retourne maintenant le texte complet ET les données structurées de propagation
@app.route('/rss.json')
def get_rss(): 
    return jsonify({
        "ticker": ticker_info["text"],
        "solar": ticker_info.get("solar_data", {"sfi": "?", "a": "?", "k": "?", "meteor": "Unknown", "solar_core": "SFI: ? | A: ? | K: ?"}),
    })

@app.route('/wanted.json')
def get_wanted():
    now = time.time()
    active = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    # Tri par score SPD (nouvelle logique pour le classement)
    ranked = sorted(active, key=lambda s: s['score'], reverse=True)
    
    top, seen = [], set()
    for s in ranked:
        # Filtre sur la distance pour éviter les spots trop locaux dans le top
        if s['distance_km'] > 100: 
            if s['dx_call'] not in seen:
                top.append({
                    'call': s['dx_call'], 
                    'score': s['score'], 
                    'c': s['country'], 
                    'band': s['band'],
                    'freq': s['freq'],
                    'color': s['color']
                })
                seen.add(s['dx_call'])
            if len(top) >= TOP_RANKING_LIMIT: break
    return jsonify(top)

# ROUTE POUR LA SYNTHÈSE VOCALE
@app.route('/speech_alert.json')
def get_speech_alert():
    global latest_alert
    if latest_alert and (time.time() - latest_alert['time']) < 120: 
        alert_to_send = latest_alert
        latest_alert = None 
        return jsonify(alert_to_send)
    return jsonify({'message': None})

@app.route('/watchlist.json', methods=['GET', 'POST', 'DELETE'])
def wl():
    if request.method == 'GET': return jsonify(sorted(list(watchlist)))
    d = request.get_json(silent=True) or {}
    c = d.get('call', '').upper().strip()
    if request.method == 'POST' and c: watchlist.add(c); save_watchlist()
    if request.method == 'DELETE' and c in watchlist: watchlist.remove(c); save_watchlist()
    return jsonify({'status': 'ok'})
    
@app.route('/update_qra', methods=['POST'])
def u_qra():
    global user_qra, user_lat, user_lon
    d = request.get_json(silent=True)
    q = d.get('qra', '').strip().upper()
    lat, lon = qra_to_lat_lon(q)
    if lat != 0: user_qra, user_lat, user_lon = q, lat, lon
    return jsonify({'success': lat!=0, 'qra': user_qra, 'lat': user_lat, 'lon': user_lon})

@app.route('/user_location.json')
def u_loc(): return jsonify({'qra': user_qra, 'lat': user_lat, 'lon': user_lon})

if __name__ == "__main__":
    user_lat, user_lon = qra_to_lat_lon(DEFAULT_QRA)
    if not os.path.exists('templates'): os.makedirs('templates')
    
    load_cty_dat() 
    load_watchlist()
    
    # Démarrage de tous les Workers
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=background_worker, daemon=True).start()
    threading.Thread(target=rss_worker, daemon=True).start()
    threading.Thread(target=history_maintenance_worker, daemon=True).start()
    
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False)