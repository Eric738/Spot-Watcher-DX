import time
import telnetlib
import threading
import json
import os
import urllib.request
import feedparser
import ssl
from collections import deque
from flask import Flask, render_template, jsonify, request, abort

# --- CONFIGURATION GENERALE ---
APP_VERSION = "NEURAL AI v3.2 - " # CHANGEMENT DE VERSION
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 1800 
AI_SCORE_THRESHOLD = 50 
TOP_RANKING_LIMIT = 10 

# --- CONFIGURATION SURGE ---
SURGE_WINDOW = 900
SURGE_THRESHOLD = 3.0
MIN_SPOTS_FOR_SURGE = 3

# --- DEFINITIONS BANDES ---
HF_BANDS = ['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
VHF_BANDS = ['4m', '2m', '70cm', '23cm', '13cm', 'QO-100']
HISTORY_BANDS = ['12m', '10m', '6m'] # NOUVELLE LISTE POUR L'HISTOGRAMME

# Palette officielle
BAND_COLORS = {
    '160m': '#5c4b51', '80m': '#8e44ad', '60m': '#2c3e50',
    '40m': '#2980b9', '30m': '#16a085', '20m': '#27ae60',
    '17m': '#f1c40f', '15m': '#e67e22', '12m': '#d35400', # Orange pour 12m
    '10m': '#c0392b', # Rouge pour 10m
    '6m': '#e84393', # Rose pour 6m
    '4m': '#ff9ff3', '2m': '#f1c40f', 
    '70cm': '#c0392b', '23cm': '#8e44ad', '13cm': '#bdc3c7',
    'QO-100': '#00a8ff' # Bleu Satellite
}

# Flux RSS
RSS_URLS = ["https://www.dx-world.net/feed/"]

CLUSTERS = [
    ("dxfun.com", 8000),
    ("dx.f5len.org", 7300),
    ("gb7mbc.spud.club", 8000)
]

CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"
SOLAR_URL = "https://services.swpc.noaa.gov/text/wwv.txt"
WATCHLIST_FILE = "watchlist.json"

app = Flask(__name__)

spots_buffer = deque(maxlen=6000)
band_history = {}
prefix_db = {}
ticker_info = {"text": "SYSTEM INITIALIZATION..."}
watchlist = set()

# NOUVEAU: Historique des spots par heure (24 heures)
history_24h = {band: [0] * 24 for band in HISTORY_BANDS}
history_lock = threading.Lock()

# --- SSL BYPASS ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError: pass
else: ssl._create_default_https_context = _create_unverified_https_context

# --- Watchlist ---
def load_watchlist():
    global watchlist
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                watchlist = set([c.upper() for c in data if isinstance(c, str)])
        except: watchlist = set()

def save_watchlist():
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(sorted(list(watchlist)), f, indent=2)
    except: pass

# --- SURGE ---
def record_surge_data(band):
    if band not in band_history: band_history[band] = deque()
    band_history[band].append(time.time())

    # Mise à jour de l'historique 24h
    if band in HISTORY_BANDS:
        with history_lock:
            # L'indice est l'heure UTC actuelle (0 à 23)
            current_hour = time.gmtime(time.time()).tm_hour
            # Incrémente le compteur pour l'heure actuelle
            history_24h[band][current_hour] += 1

def analyze_surges():
    current_time = time.time()
    active_surges = []
    for band, timestamps in list(band_history.items()):
        while timestamps and timestamps[0] < current_time - SURGE_WINDOW:
            timestamps.popleft()
        count_total = len(timestamps)
        if count_total < 5: continue 
        avg_rate = count_total / (SURGE_WINDOW / 60.0)
        recent_count = sum(1 for t in timestamps if t > current_time - 60)
        if recent_count > (avg_rate * SURGE_THRESHOLD) and recent_count >= MIN_SPOTS_FOR_SURGE:
            active_surges.append(band)
    return active_surges

# --- IA & LOGIC (Pas de changement) ---
def calculate_ai_score(call, band, mode, comment, country):
    score = 10 
    call = call.upper(); comment = (comment or "").upper()
    
    # LISTE DES PREFIXES RARES ET ANTARCTIQUES MISE A JOUR
    RARE_PREFIXES = [
        'DP0', 'DP1', 'RI1', '8J1', 'VP8', 'KC4', # Antarctique
        '3Y', 'P5', 'BS7', 'CE0', 'CY9', 'EZ', 'FT5', 'FT8', 'VK0', 
        'HV', '1A', '4U1UN', 'E4', 'SV/A', 'T88', '9J', 'XU', '3D2', 'S21', 
        'KH0', 'KH1', 'KH3', 'KH4', 'KH7', 'KH9', 'KP1', 'KP5', 'ZK', 'ZL7', 'ZL9'
    ]
    
    for p in RARE_PREFIXES:
        if call.startswith(p): 
            score += 60 # Boost énorme pour les rares
            break 
    
    if 'UP' in comment or 'SPLIT' in comment: score += 15
    if 'DX' in comment: score += 5
    
    # Boost spécifique QO-100
    if band == 'QO-100': score += 40
    elif band in VHF_BANDS: score += 30 
    
    if band == '10m' or band == '6m': score += 20
    if mode == 'CW': score += 10
    if 'PIRATE' in comment: score = 0
    
    return min(score, 100)

def get_band_and_mode_smart(freq_float, comment):
    comment = (comment or "").upper()
    f = float(freq_float)
    
    # --- LOGIQUE DE NORMALISATION FREQUENCE ---
    # Les clusters envoient QO-100 en kHz (10489xxx)
    # Si f < 1000, c'est du MHz -> on multiplie par 1000
    # Si f > 20000000 (20 GHz), c'est du Hz -> on divise par 1000
    # On NE TOUCHE PAS aux fréquences entre 1M et 11M (QO-100 en kHz)
    
    if f < 1000: 
        f = f * 1000.0
    elif f > 20000000: # Correction: seuil monté à 20M pour ne pas casser le 10GHz (10M kHz)
        f = f / 1000.0

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
        # QO-100 Downlink: 10489.500 MHz -> 10489500 kHz
        if 10489000 <= freq_khz <= 10499000: return "QO-100"
        return "Unknown"

    band = find_band(f)
    
    # --- AUTO-DETECTION PAR FREQUENCE (Priorité maximale) ---
    
    # 1. MSK144 (2m: 144.360 MHz +/- 20 kHz)
    if band == "2m" and 144340.0 <= f <= 144380.0:
        mode = "MSK144"
        return band, mode # Priorité absolue
        
    # 2. FT8 (HF/VHF)
    if (3557.0 <= f <= 3587.0 or    # 80m FT8 (3572 +/- 15 kHz)
        7069.0 <= f <= 7079.0 or    # 40m FT8 (7074 +/- 5 kHz)
        10130.0 <= f <= 10140.0 or  # 30m FT8 (10135 +/- 5 kHz)
        14071.0 <= f <= 14077.0 or  # 20m FT8 (14074 +/- 3 kHz)
        18097.0 <= f <= 18103.0 or  # 17m FT8 (18100 +/- 3 kHz)
        21071.0 <= f <= 21077.0 or  # 15m FT8 (21074 +/- 3 kHz)
        24913.0 <= f <= 24919.0 or  # 12m FT8 (24916 +/- 3 kHz)
        28069.0 <= f <= 28079.0):   # 10m FT8 (28074 +/- 5 kHz)
        mode = "FT8"
        return band, mode # Priorité absolue

    # --- 3. DETECTION PAR COMMENTAIRE (Si non FT8/MSK144 par fréquence) ---
    
    mode = "SSB"
    if "FT8" in comment: mode = "FT8" # Détection FT8 hors segment par commentaire
    elif "FT4" in comment: mode = "FT4"
    elif "CW" in comment: mode = "CW"
    elif "FM" in comment: mode = "FM"
    elif "SSTV" in comment: mode = "SSTV"
    elif "PSK31" in comment: mode = "PSK31"
    elif "RTTY" in comment: mode = "RTTY"
        
    # --- 4. CORRECTION FINALE CW ---
    if band in ["30m", "20m"] and f < 14100 and mode=="SSB": 
        mode = "CW"
    
    return band, mode

def load_cty_dat():
# ... (reste de la fonction load_cty_dat inchangé)
    global prefix_db
    if not os.path.exists(CTY_FILE):
        try: urllib.request.urlretrieve(CTY_URL, CTY_FILE)
        except: return
    try:
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
    except: pass

def get_country_info(call):
# ... (reste de la fonction get_country_info inchangé)
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
    global history_24h
    while True:
        # Maintenance: Décalage de l'historique toutes les heures pile (UTC)
        now_utc = time.gmtime(time.time())
        next_hour = (now_utc.tm_hour + 1) % 24
        
        # Temps restant jusqu'au début de la prochaine heure UTC
        sleep_seconds = (3600 - (now_utc.tm_min * 60 + now_utc.tm_sec)) + 5 

        time.sleep(sleep_seconds) 
        
        with history_lock:
            for band in HISTORY_BANDS:
                # Décalage des données (l'heure actuelle va à la fin)
                history_24h[band] = history_24h[band][1:] + [0]
            print(f"HISTORY 24H: Shifted and reset hour {next_hour}")

def ticker_worker():
    while True:
        msgs = [f"SYSTEM ONLINE - {MY_CALL}"]
        
        # 1. Solar Data
        try:
            req = urllib.request.Request(SOLAR_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                l = [x for x in r.read().decode('utf-8').split('\n') if x and not x.startswith((':','#'))]
                if l: msgs.append(f"SOLAR: {l[-1]}")
        except: pass
        
        # 2. RSS Data
        try:
            feed = feedparser.parse(RSS_URLS[0])
            if feed.entries:
                # On prend les 5 derniers titres
                news = [entry.title for entry in feed.entries[:5]]
                msgs.append("NEWS: " + " | ".join(news))
        except Exception as e: 
            print(f"RSS Error: {e}")

        ticker_info["text"] = "   +++   ".join(msgs)
        time.sleep(1800) # Refresh RSS toutes les 30 min

def telnet_worker():
    idx = 0
    while True:
        host, port = CLUSTERS[idx]
        print(f"Connexion Cluster: {host}:{port}")
        try:
            tn = telnetlib.Telnet(host, port, timeout=15)
            try: tn.read_until(b"login: ", timeout=5)
            except: pass
            tn.write(MY_CALL.encode('ascii') + b"\n")
            time.sleep(1)
            tn.write(b"show/dx 50\n")
            
            last_ping = time.time()
            while True:
                try: line = tn.read_until(b"\n", timeout=2).decode('ascii', errors='ignore').strip()
                except: line = ""
                if not line:
                    if time.time() - last_ping > KEEP_ALIVE: 
                        tn.write(b"\n"); last_ping = time.time()
                    continue
                
                if "DX de" in line:
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
                        score = calculate_ai_score(dx_call, band, mode, comment, info['c'])
                        color = BAND_COLORS.get(band, '#00f3ff')
                        
                        # Enregistrement pour le Surge et l'Historique 24h
                        record_surge_data(band)
                        
                        spot_obj = {
                            "timestamp": time.time(), "time": time.strftime("%H:%M"),
                            "freq": freq_str, "dx_call": dx_call, "band": band, "mode": mode,
                            "country": info['c'], "lat": info['lat'], "lon": info['lon'],
                            "score": score, "is_wanted": score >= AI_SCORE_THRESHOLD,
                            "via_eme": ("EME" in comment),
                            "color": color,
                            "type": "VHF" if band in VHF_BANDS else "HF"
                        }
                        spots_buffer.append(spot_obj)
                        print(f"SPOT: {dx_call} ({band}) -> {score} pts")
                    except Exception as e: 
                        # print(f"Parse Error: {e}") # Debug seulement
                        pass
        except: pass
        time.sleep(5)
        idx = (idx + 1) % len(CLUSTERS)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION, my_call=MY_CALL, 
                           hf_bands=HF_BANDS, vhf_bands=VHF_BANDS, band_colors=BAND_COLORS)

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
    return jsonify({"surges": analyze_surges(), "timestamp": time.time()})

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
    if not data or 'call' not in data: return abort(400)
    call = data['call'].upper().strip()
    if request.method == 'POST': watchlist.add(call)
    if request.method == 'DELETE' and call in watchlist: watchlist.remove(call)
    save_watchlist()
    return jsonify({"status": "ok"})

@app.route('/rss.json')
def get_rss(): return jsonify({"ticker": ticker_info["text"]})

# NOUVELLE ROUTE POUR L'HISTORIQUE 24H
@app.route('/history.json')
def get_history():
    # Retourne les données historiques des 24 dernières heures UTC
    # La liste est ordonnée: l'élément à l'index 0 est l'heure la plus ancienne
    # Le dernier élément est l'heure en cours
    
    # On crée une liste de labels (H-23, H-22, ..., H-0) basée sur l'heure UTC actuelle
    now_hour = time.gmtime(time.time()).tm_hour
    
    labels = []
    for i in range(24):
        # L'heure à l'index 'i' est l'heure actuelle - (23-i)
        # Ex: si now_hour=10, l'index 0 est (10 - 23) % 24 = -13 % 24 = 11.
        # En fait, c'est l'heure qui s'est terminée à cet index.
        h = (now_hour - (23 - i)) % 24
        labels.append(f"H-{23-i} ({h:02}h)") # Exemple: H-23 (11h)
        
    # La liste history_24h contient l'historique dans l'ordre chronologique
    # history_24h[band][now_hour] est la valeur courante (H-0)
    
    # Pour obtenir le bon ordre H-23 à H-0:
    # On coupe la liste à l'heure actuelle et on la recolle (rotation)
    
    # history_24h[band] contient: [Heure 0, Heure 1, ..., Heure 'now_hour']
    # On veut: [Heure 'now_hour+1', ..., Heure 23, Heure 0, ..., Heure 'now_hour']
    
    with history_lock:
        data = {band: list(hist) for band, hist in history_24h.items()} # Copie

    current_data = {}
    for band in HISTORY_BANDS:
        hist_list = data[band]
        # On fait une rotation pour que l'index 0 soit l'heure la plus ancienne (H-23)
        rotated = hist_list[now_hour+1:] + hist_list[:now_hour+1]
        current_data[band] = rotated
        
    return jsonify({"labels": labels, "data": current_data})


if __name__ == "__main__":
    load_cty_dat()
    load_watchlist()
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    threading.Thread(target=history_maintenance_worker, daemon=True).start() # NOUVEAU THREAD
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)