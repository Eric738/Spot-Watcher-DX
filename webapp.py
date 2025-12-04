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
from collections import deque, Counter 
from flask import Flask, render_template, jsonify, request, abort, redirect, url_for 

# --- CONFIGURATION GENERALE ---
APP_VERSION = "NEURAL AI v4.0 - Fixes + D&D" # Version mise à jour
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 1800 
SPD_THRESHOLD = 70
TOP_RANKING_LIMIT = 10 
DEFAULT_QRA = "JN23"

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

# --- DX CLUSTER CONFIGURATION (Clusters fiables) ---
RSS_URLS = ["https://www.dx-world.net/feed/"]
CLUSTERS = [
    ("dxfun.com", 8000),
    ("cluster.dx.de", 7300), 
    ("telnet.wxc.kr", 23)    
]
CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"
SOLAR_URL = "https://services.swpc.noaa.gov/text/wwv.txt"
WATCHLIST_FILE = "watchlist.json"

# --- CACHES GLOBAUX et INITIALISATION QTH ---
app = Flask(__name__)
# Configuration du logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

spots_buffer = deque(maxlen=6000)
band_history = {}
prefix_db = {}
ticker_info = {"text": "SYSTEM INITIALIZATION..."}
watchlist = set()
surge_bands = [] 

history_24h = {band: [0] * 24 for band in HISTORY_BANDS}
history_lock = threading.Lock()
surge_lock = threading.Lock()


# --- PLAGES DE FREQUENCES CW ---
CW_RANGES = [
    ('160m', 1.810, 1.838), ('80m', 3.500, 3.560), ('40m', 7.000, 7.035),
    ('30m', 10.100, 10.134), ('20m', 14.000, 14.069), ('17m', 18.068, 18.095),
    ('15m', 21.000, 21.070), ('12m', 24.890, 24.913), ('10m', 28.000, 28.070),
]

# --- FRÉQUENCES FT4/FT8 (en kHz) ---
FT4_HF_FREQS_KHZ = [
    7047, 10140, 14080, 18104, 21180, 24919, 28180
]
FT4_VHF_FREQ_KHZ = 144170
FT8_VHF_FREQ_RANGE_KHZ = (144171, 144177) 


# --- SSL BYPASS ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError: pass
else: ssl._create_default_https_context = _create_unverified_https_context


# --- FONCTIONS UTILITAIRES ET DE TRAITEMENT ---

def qra_to_lat_lon(qra):
    """ Convertit un QRA locator en latitude et longitude. """
    try:
        qra = qra.upper().strip()
        if len(qra) < 4: 
            logger.warning(f"QRA '{qra}' est trop court.")
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
    except Exception as e:
        logger.error(f"Erreur lors de la conversion QRA '{qra}': {e}")
        return None, None

# Initialisation du QTH utilisateur 
initial_lat, initial_lon = qra_to_lat_lon(DEFAULT_QRA)
user_qra = DEFAULT_QRA
user_lat = initial_lat if initial_lat is not None else 43.10
user_lon = initial_lon if initial_lon is not None else 5.88


def is_meteor_shower_active():
    """ Vérifie si la date actuelle est dans une période d'essaim de météores (UTC). """
    now = time.gmtime(time.time())
    current_month = now.tm_mon
    current_day = now.tm_mday

    for shower in METEOR_SHOWERS:
        start_m, start_d = shower["start"]
        end_m, end_d = shower["end"]

        # Cas Déc à Jan
        if start_m > end_m: 
            if (current_month == start_m and current_day >= start_d) or \
               (current_month == end_m and current_day <= end_d):
                return True, shower["name"]
        
        # Cas simple (dans la même année) ou chevauchement de mois
        else: 
            if (current_month == start_m and current_day >= start_d) or \
               (current_month == end_m and current_day <= end_d) or \
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
            logger.error(f"Impossible de charger la Watchlist: {e}")
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
    if band not in band_history: band_history[band] = deque()
    band_history[band].append(time.time())
    
    if band in HISTORY_BANDS:
        now_hour_utc = time.gmtime(time.time()).tm_hour
        with history_lock:
            # L'index est l'heure UTC courante (0-23)
            history_24h[band][now_hour_utc] += 1


def analyze_surges():
    """ Calcule les surges HF/VHF standard ET gère les surges MSK144. """
    
    global surge_bands 
    current_time = time.time()
    active_surges = []
    
    recent_ms_spots_count = sum(1 for s in spots_buffer 
                                if s.get('band') == '2m' and s.get('mode') == 'MSK144' and (current_time - s['timestamp']) < 900)

    # --- 1. LOGIQUE MSK144 / METEOR SCATTER ---
    is_active, shower_name = is_meteor_shower_active()
    ms_surge_name = f"MSK144: {shower_name}" if is_active else "MSK144: Inactive"
    
    with surge_lock:
        
        # A. Détection MSK144
        if is_active and recent_ms_spots_count >= MIN_SPOTS_FOR_SURGE:
            if ms_surge_name not in surge_bands:
                surge_bands.append(ms_surge_name)
                logger.info(f"ALERTE MSK144: Surge MS détectée pendant les {shower_name} ({recent_ms_spots_count} spots)!")
            active_surges.append(ms_surge_name)

        # B. Nettoyage MSK144
        else:
            if ms_surge_name in surge_bands:
                surge_bands.remove(ms_surge_name)
                logger.info(f"FIN ALERTE MSK144: L'activité a diminué ou l'essaim est terminé.")
            
        # --- 2. LOGIQUE HF/VHF STANDARD ---
        
        bands_in_surge = [s for s in surge_bands if not s.startswith("MSK144:")]
        
        for band in HF_BANDS + [b for b in VHF_BANDS if b not in ['2m', 'QO-100']]:
            timestamps = band_history.get(band, deque())
            
            # Nettoyage des timestamps trop vieux
            while timestamps and timestamps[0] < current_time - SURGE_WINDOW:
                timestamps.popleft()
            
            count_total = len(timestamps)
            
            if count_total < MIN_SPOTS_FOR_SURGE: continue
                
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
                # Retirer la surge si l'activité retombe
                surge_bands.remove(band)
                logger.info(f"FIN ALERTE SURGE {band}: L'activité a diminué.")

    return active_surges


# --- MOTEUR DRSE (Score de Priorité de DX) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    """ Calcule la distance de grand cercle entre deux points (en km). """
    R = 6371 
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def calculate_spd_score(call, band, mode, comment, country, dist_km):
    """ Calcule le Score de Priorité de DX (SPD). """
    score = 10 
    call = call.upper(); comment = (comment or "").upper()
    
    RARE_PREFIXES = [
        'DP0', 'DP1', 'RI1', '8J1', 'VP8', 'KC4', 
        '3Y', 'P5', 'BS7', 'CE0', 'CY9', 'EZ', 'FT5', 'FT8', 'VK0', 
        'HV', '1A', '4U1UN', 'E4', 'SV/A', 'T88', '9J', 'XU', '3D2', 'S21', 
        'KH0', 'KH1', 'KH3', 'KH4', 'KH7', 'KH9', 'KP1', 'KP5', 'ZK', 'ZL7', 'ZL9'
    ]
    
    # 1. Rareté du préfixe
    for p in RARE_PREFIXES:
        if call.startswith(p): 
            score += 65 
            break 
    
    # 2. Commentaires/Mode
    if 'UP' in comment or 'SPLIT' in comment: score += 15 
    if 'DX' in comment: score += 5
    if 'QRZ' in comment: score -= 10 
    if mode == 'CW': score += 10
    if 'PIRATE' in comment: score = 0
    
    # 3. Distance (Bonus si > 1000km)
    if dist_km and dist_km > 1000:
        distance_bonus = min(20, 20 * math.log10(dist_km / 1000))
        score += distance_bonus
    
    # 4. Bande (VHF/UHF/QO-100/Bandes Magiques)
    if band == 'QO-100': score += 40
    elif band in VHF_BANDS: score += 30 
    
    if band in ['10m', '12m', '15m']: score += 15 
    
    return min(int(score), 100)

def get_band_and_mode_smart(freq_float, comment):
    """ Détermine la bande et le mode à partir de la fréquence. """
    comment = (comment or "").upper()
    f = float(freq_float)
    
    if f < 1000: 
        f = f * 1000.0
    elif f > 20000000: 
        f = f / 1000.0

    freq_khz = f # Frequency in kHz

    def find_band(freq_khz):
        if 1800 <= freq_khz <= 2000: return "160m"
        if 3500 <= freq_khz <= 3800: return "80m"
        if 5300 <= freq_khz <= 5450: return "60m"
        if 7000 <= freq_khz <= 7300: return "40m"
        if 10100 <= freq_khz <= 10150: return "30m"
        if 14000 <= freq_khz <= 14350: return "20m"
        if 18068 <= freq_khz <= 18168: return "17m"
        if 21000 <= freq_khz <= 21450: return "15m"
        if 24890 <= freq_khz <= 24990: return "12m"
        if 28000 <= freq_khz <= 29700: return "10m"
        if 50000 <= freq_khz <= 54000: return "6m"
        if 70000 <= freq_khz <= 70500: return "4m"
        if 144000 <= freq_khz <= 146000: return "2m"
        if 430000 <= freq_khz <= 440000: return "70cm"
        if 1240000 <= freq_khz <= 1300000: return "23cm"
        if 10489000 <= freq_khz <= 10499000: return "QO-100"
        return "Unknown"

    band = find_band(freq_khz)
    f_mhz = freq_khz / 1000.0 
    mode = "SSB"

    # --- NOUVELLE LOGIQUE DE DÉTECTION FT4/FT8 ---
    TOLERANCE_KHZ = 1 

    # 1. Vérification FT4 HF (Tolérance de +/- 1 kHz)
    FT4_HF_FREQS_KHZ = [7047, 10140, 14080, 18104, 21180, 24919, 28180]
    is_ft4_hf = any(abs(freq_khz - ft4_f) <= TOLERANCE_KHZ for ft4_f in FT4_HF_FREQS_KHZ)

    # 2. Vérification FT4 VHF (2m) (Tolérance de +/- 1 kHz)
    FT4_VHF_FREQ_KHZ = 144170
    is_ft4_vhf = band == "2m" and abs(freq_khz - FT4_VHF_FREQ_KHZ) <= TOLERANCE_KHZ

    # 3. Vérification FT8 VHF (2m) (Plage exacte)
    ft8_vhf_min, ft8_vhf_max = FT8_VHF_FREQ_RANGE_KHZ
    is_ft8_vhf = band == "2m" and ft8_vhf_min <= freq_khz <= ft8_vhf_max
    
    # Application des modes numériques
    if is_ft4_hf or is_ft4_vhf:
        mode = "FT4"
    elif is_ft8_vhf:
        mode = "FT8"
    
    # 4. Détection CW dans les segments CW
    if mode == "SSB": # Ne pas écraser FT4/FT8/MSK144 déjà détectés
        for cw_band, min_mhz, max_mhz in CW_RANGES:
            if cw_band == band and min_mhz <= f_mhz <= max_mhz:
                mode = "CW"
                break
    
    # 5. Détection MSK144 (précise)
    if band == "2m" and abs(f_mhz - MSK144_FREQ) <= MSK144_TOLERANCE_KHZ:
        mode = "MSK144"
        
    # 6. Surcharge par commentaires (comme solution de secours)
    if "FT8" in comment and mode != "FT4": mode = "FT8" 
    elif "FT4" in comment and mode != "FT8": mode = "FT4"
    elif "CW" in comment and mode == "SSB": mode = "CW"
    elif "FM" in comment: mode = "FM"
    elif "SSTV" in comment: mode = "SSTV"
    elif "PSK31" in comment: mode = "PSK31"
    elif "RTTY" in comment: mode = "RTTY"
        
    return band, mode

def load_cty_dat():
    """ Charge la base de données des préfixes DXCC (cty.dat). """
    global prefix_db
    if not os.path.exists(CTY_FILE):
        try: 
            logger.info("Téléchargement de cty.dat...")
            urllib.request.urlretrieve(CTY_URL, CTY_FILE)
        except Exception as e: 
            logger.error(f"Échec du téléchargement de cty.dat: {e}")
            return
    try:
        logger.info("Chargement de la base de données DXCC.")
        with open(CTY_FILE, "rb") as f: raw = f.read().decode('latin-1')
        for rec in raw.replace('\r', '').replace('\n', ' ').split(';'):
            if ':' in rec:
                p = rec.split(':')
                country = p[0].strip()
                try: lat, lon = float(p[4]), float(p[5]) * -1
                except: lat, lon = 0.0, 0.0
                prefixes = p[7].strip().split(',')
                if len(p)>8: prefixes += p[8].strip().split(',')
                for px in prefixes:
                    clean = px.split('(')[0].split('[')[0].strip().lstrip('=')
                    if clean: prefix_db[clean] = {'c': country, 'lat': lat, 'lon': lon}
        logger.info(f"Base de données DXCC chargée: {len(prefix_db)} préfixes.")
    except Exception as e: 
        logger.error(f"Erreur lors du parsing de cty.dat: {e}")

def get_country_info(call):
    """ Recherche les coordonnées et le pays pour un indicatif donné. """
    call = call.upper()
    best = {'c': 'Unknown', 'lat': 0.0, 'lon': 0.0}
    longest = 0
    candidates = [call]
    if '/' in call: candidates.append(call.split('/')[-1])
    for c in candidates:
        for i in range(len(c), 0, -1):
            sub = c[:i]
            if sub in prefix_db and len(sub) > longest:
                longest = len(sub); best = prefix_db[sub]
    return best

# --- WORKERS ---
def history_maintenance_worker():
    """ Tâche de maintenance pour décaler l'historique 24h à chaque heure UTC. """
    threading.current_thread().name = 'HistoryWorker'
    while True:
        now_utc = time.gmtime(time.time())
        # Décalage juste après la fin de la minute 59:59 (plus 5s de garde)
        sleep_seconds = (3600 - (now_utc.tm_min * 60 + now_utc.tm_sec)) + 5 
        time.sleep(sleep_seconds) 
        
        with history_lock:
            # Détermination de l'heure qui vient de commencer (new_now_hour)
            new_now_hour = time.gmtime(time.time()).tm_hour
            
            # L'heure qui vient de se terminer est (new_now_hour - 1) % 24
            hour_to_reset = (new_now_hour - 1 + 24) % 24 
            
            for band in HISTORY_BANDS:
                # Réinitialisation des spots pour l'heure qui vient de se terminer
                history_24h[band][hour_to_reset] = 0
            logger.info(f"HISTORY 24H: Réinitialisation de l'heure {hour_to_reset:02}h (qui vient de se terminer).")


def ticker_worker():
    """ Tâche pour mettre à jour le message défilant avec les infos solaires et RSS. """
    threading.current_thread().name = 'TickerWorker'
    while True:
        msgs = [f"SYSTEM ONLINE - {MY_CALL} ({APP_VERSION})"]
        
        # 1. Infos solaires
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
            
        # 2. Infos RSS
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
        time.sleep(1800) 

def telnet_worker():
    """ Tâche pour se connecter et écouter le DX Cluster. """
    threading.current_thread().name = 'TelnetWorker'
    idx = 0
    while True:
        host, port = CLUSTERS[idx]
        logger.info(f"Tentative de connexion au Cluster: {host}:{port} ({idx + 1}/{len(CLUSTERS)})")
        try:
            tn = telnetlib.Telnet(host, port, timeout=15)
            try: tn.read_until(b"login: ", timeout=5)
            except: pass
            tn.write(MY_CALL.encode('ascii') + b"\n")
            time.sleep(1)
            
            # Correction du bug encoding et commandes initiales
            tn.write(b"set/dx/filter\n") 
            tn.write(b"show/dx 50\n") 
            
            logger.info(f"Connexion établie sur {host}:{port}. Écoute des spots en cours.")
            last_ping = time.time()
            
            while True:
                try: 
                    line = tn.read_until(b"\n", timeout=3).decode('ascii', errors='ignore').strip()
                except: 
                    line = ""
                
                if not line:
                    if time.time() - last_ping > KEEP_ALIVE: 
                        tn.write(b"\n"); last_ping = time.time()
                    
                    analyze_surges() 
                    
                    continue
                
                if line.startswith("DX de"):
                    try:
                        content = line[line.find("DX de")+5:].strip()
                        parts = content.split()
                        if len(parts) < 3: continue
                        freq_str = parts[1]
                        dx_call = parts[2].upper()
                        comment = " ".join(parts[3:]).upper()
                        
                        try: freq_raw = float(freq_str)
                        except: continue

                        band, mode = get_band_and_mode_smart(freq_raw, comment)
                        info = get_country_info(dx_call)
                        
                        lat, lon = info['lat'], info['lon']
                        dist_km = 0.0
                        if lat != 0.0 and lon != 0.0:
                            dist_km = calculate_distance(user_lat, user_lon, lat, lon)
                            
                        spd_score = calculate_spd_score(dx_call, band, mode, comment, info['c'], dist_km)
                        color = BAND_COLORS.get(band, '#00f3ff')
                        
                        record_surge_data(band)
                        
                        spot_obj = {
                            "timestamp": time.time(), "time": time.strftime("%H:%M"),
                            "freq": freq_str, "dx_call": dx_call, "band": band, "mode": mode,
                            "country": info['c'], "lat": lat, "lon": lon,
                            "score": spd_score, 
                            "is_wanted": spd_score >= SPD_THRESHOLD,
                            "via_eme": ("EME" in comment),
                            "color": color,
                            "type": "VHF" if band in VHF_BANDS else "HF",
                            "distance_km": dist_km 
                        }
                        spots_buffer.append(spot_obj)
                        logger.info(f"SPOT: {dx_call} ({band}, {mode}) -> SPD: {spd_score} pts (Dist: {dist_km:.0f}km)")
                    except Exception as e: 
                        logger.error(f"Erreur de traitement du spot '{line}': {e}")
                        
        except Exception as e: 
            logger.error(f"ERREUR CRITIQUE Cluster {host}:{port}: {e}. Basculement.")
            time.sleep(5)
            
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
        logger.info(f"QTH mis à jour: {user_qra} ({user_lat:.2f}, {user_lon:.2f})")
    else:
        logger.warning(f"Tentative de mise à jour QTH invalide: {new_qra}")
    
    return redirect(url_for('index')) 

@app.route('/user_location.json')
def get_user_location():
    return jsonify({
        'qra': user_qra,
        'lat': user_lat,
        'lon': user_lon
    })

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
            if len(top) >= TOP_RANKING_LIMIT: break
        return top

    hf_spots = [s for s in active if s['type'] == 'HF']
    vhf_spots = [s for s in active if s['type'] == 'VHF']

    return jsonify({
        "hf": get_top_for_list(hf_spots),
        "vhf": get_top_for_list(vhf_spots)
    })

@app.route('/watchlist.json', methods=['GET', 'POST', 'DELETE'])
def manage_watchlist():
    if request.method == 'GET': return jsonify(sorted(list(watchlist)))
    data = request.get_json(force=True, silent=True)
    if not data or 'call' not in data: 
        logger.warning("Tentative d'accès watchlist avec données invalides.")
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
def get_rss(): return jsonify({"ticker": ticker_info["text"]})

@app.route('/history.json')
def get_history():
    now_hour = time.gmtime(time.time()).tm_hour
    
    labels = []
    # 1. Générer les étiquettes de H-23 à H-0
    for i in range(24):
        hours_ago = 23 - i 
        # target_hour est l'index UTC qui correspond à H-23 (i=0) jusqu'à H-0 (i=23)
        target_hour = (now_hour - hours_ago + 24) % 24
        labels.append(f"H-{hours_ago} ({target_hour:02}h)") 
        
    with history_lock:
        data = {band: list(hist) for band, hist in history_24h.items()} 

    current_data = {}
    for band in HISTORY_BANDS:
        hist_list = data[band]
        
        # 2. Rotation pour avoir l'ordre H-23, H-22, ..., H-0.
        # L'index qui correspond à H-23 est (now_hour + 1) % 24.
        start_index_for_H_23 = (now_hour + 1) % 24
        
        # Rotation : [Index H-23, ..., Index H-0]
        rotated = hist_list[start_index_for_H_23:] + hist_list[:start_index_for_H_23]
        current_data[band] = rotated
        
    return jsonify({"labels": labels, "data": current_data})

@app.route('/live_bands.json')
def get_live_bands_data():
    now = time.time()
    # Filtrer les spots actifs (moins de SPOT_LIFETIME)
    active_spots = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    
    # Séparation HF et VHF
    hf_spots = [s for s in active_spots if s['type'] == 'HF']
    vhf_spots = [s for s in active_spots if s['type'] == 'VHF']
    
    # Compter les spots par bande
    hf_counts = Counter(s['band'] for s in hf_spots if s['band'] in HF_BANDS)
    vhf_counts = Counter(s['band'] for s in vhf_spots if s['band'] in VHF_BANDS)
    
    # Préparer les données pour Chart.js (HF)
    hf_data = {
        "labels": [b for b in HF_BANDS if hf_counts[b] > 0],
        "data": [hf_counts[b] for b in HF_BANDS if hf_counts[b] > 0],
        "colors": [BAND_COLORS[b] for b in HF_BANDS if hf_counts[b] > 0]
    }
    
    # Préparer les données pour Chart.js (VHF)
    vhf_data = {
        "labels": [b for b in VHF_BANDS if vhf_counts[b] > 0],
        "data": [vhf_counts[b] for b in VHF_BANDS if vhf_counts[b] > 0],
        "colors": [BAND_COLORS[b] for b in VHF_BANDS if vhf_counts[b] > 0]
    }
    
    # Le graphique Live VHF doit inclure "QO-100" même s'il est techniquement SHF
    return jsonify({
        "hf": hf_data,
        "vhf": vhf_data
    })


if __name__ == "__main__":
    load_cty_dat()
    load_watchlist()
    
    logger.info(f"\n--- {APP_VERSION} ---")
    logger.info(f"QTH de départ: {user_qra} ({user_lat:.2f}, {user_lon:.2f})")
    
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    threading.Thread(target=history_maintenance_worker, daemon=True).start() 
    
    logger.info(f"Server starting on http://0.0.0.0:{WEB_PORT}")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False)