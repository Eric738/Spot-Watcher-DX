import time
import telnetlib
import threading
import json
import os
import urllib.request
import feedparser
import ssl
import math 
from collections import deque
from flask import Flask, render_template, jsonify, request, abort

# --- CONFIGURATION GENERALE ---
APP_VERSION = "NEURAL AI v3.4 - DRSE" # Mise à jour
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 1800 
SPD_THRESHOLD = 70 # NOUVEAU: Score de Priorité de DX (SPD) Seuil
TOP_RANKING_LIMIT = 10 

# --- CONFIGURATION SURGE ---
SURGE_WINDOW = 900
SURGE_THRESHOLD = 3.0
MIN_SPOTS_FOR_SURGE = 3

# --- DEFINITIONS BANDES ---
HF_BANDS = ['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
VHF_BANDS = ['4m', '2m', '70cm', '23cm', '13cm', 'QO-100']
HISTORY_BANDS = ['12m', '10m', '6m'] 

# Palette officielle
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

history_24h = {band: [0] * 24 for band in HISTORY_BANDS}
history_lock = threading.Lock()

# --- PLAGES DE FREQUENCES CW MISES A JOUR ---
CW_RANGES = [
    ('160m', 1.810, 1.838),
    ('80m', 3.500, 3.560),
    ('40m', 7.000, 7.035),
    ('30m', 10.100, 10.134),
    ('20m', 14.000, 14.069),
    ('17m', 18.068, 18.095),
    ('15m', 21.000, 21.070),
    ('12m', 24.890, 24.913),
    ('10m', 28.000, 28.070),
]


# --- SSL BYPASS ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError: pass
else: ssl._create_default_https_context = _create_unverified_https_context

# --- Watchlist (fonctions inchangées) ---
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

# --- SURGE (fonctions inchangées) ---
def record_surge_data(band):
    if band not in band_history: band_history[band] = deque()
    band_history[band].append(time.time())

    if band in HISTORY_BANDS:
        with history_lock:
            current_hour = time.gmtime(time.time()).tm_hour
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

# --- MOTEUR DRSE (Score de Priorité de DX) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance en km entre deux points GPS (formule Haversine)."""
    R = 6371 
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# Coordonnées du QTH de l'opérateur (F1SMV) - Simulé
QTH_LAT = 43.10 
QTH_LON = 5.88

def calculate_spd_score(call, band, mode, comment, country, lat, lon):
    """
    Calcule le Score de Priorité de DX (SPD) en utilisant le Moteur DRSE.
    """
    score = 10 
    call = call.upper(); comment = (comment or "").upper()
    
    # 1. RARETÉ DXCC (Base)
    RARE_PREFIXES = [
        'DP0', 'DP1', 'RI1', '8J1', 'VP8', 'KC4', 
        '3Y', 'P5', 'BS7', 'CE0', 'CY9', 'EZ', 'FT5', 'FT8', 'VK0', 
        'HV', '1A', '4U1UN', 'E4', 'SV/A', 'T88', '9J', 'XU', '3D2', 'S21', 
        'KH0', 'KH1', 'KH3', 'KH4', 'KH7', 'KH9', 'KP1', 'KP5', 'ZK', 'ZL7', 'ZL9'
    ]
    
    is_rare = False
    for p in RARE_PREFIXES:
        if call.startswith(p): 
            score += 65 
            is_rare = True
            break 
    
    # 2. QUALITÉ DU SPOT
    if 'UP' in comment or 'SPLIT' in comment: score += 15 
    if 'DX' in comment: score += 5
    if 'QRZ' in comment: score -= 10 
    if mode == 'CW': score += 10
    if 'PIRATE' in comment: score = 0
    
    # 3. GÉOMÉTRIE DE PROPAGATION (Distance)
    if lat != 0.0 and lon != 0.0:
        dist_km = calculate_distance(QTH_LAT, QTH_LON, lat, lon)
        if dist_km > 1000:
            distance_bonus = min(20, 20 * math.log10(dist_km / 1000))
            score += distance_bonus
    
    # 4. BOOSTS SPÉCIFIQUES (Band)
    if band == 'QO-100': score += 40
    elif band in VHF_BANDS: score += 30 
    
    if band in ['10m', '12m', '15m']: score += 15 
    
    return min(int(score), 100)

def get_band_and_mode_smart(freq_float, comment):
    comment = (comment or "").upper()
    f = float(freq_float)
    
    if f < 1000: 
        f = f * 1000.0
    elif f > 20000000: 
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
        if 10489000 <= freq_khz <= 10499000: return "QO-100"
        return "Unknown"

    band = find_band(f)
    f_mhz = f / 1000.0 
    mode = "SSB"
    
    for cw_band, min_mhz, max_mhz in CW_RANGES:
        if cw_band == band and min_mhz <= f_mhz <= max_mhz:
            mode = "CW"
            break
        
    if band == "2m" and 144.340 <= f_mhz <= 144.380:
        mode = "MSK144"
        return band, mode 
        
    if (3.557 <= f_mhz <= 3.587 or 7.069 <= f_mhz <= 7.079 or 10.130 <= f_mhz <= 10.140 or 
        14.071 <= f_mhz <= 14.077 or 18.097 <= f_mhz <= 18.103 or 21.071 <= f_mhz <= 21.077 or 
        24.913 <= f_mhz <= 24.919 or 28.069 <= f_mhz <= 28.079):   
        mode = "FT8"
        return band, mode 

    if mode != "CW":
        mode = "SSB" 
        if "FT8" in comment: mode = "FT8" 
        elif "FT4" in comment: mode = "FT4"
        elif "CW" in comment: mode = "CW"
        elif "FM" in comment: mode = "FM"
        elif "SSTV" in comment: mode = "SSTV"
        elif "PSK31" in comment: mode = "PSK31"
        elif "RTTY" in comment: mode = "RTTY"
        
    return band, mode

def load_cty_dat():
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

# --- WORKERS (inchangés) ---
def history_maintenance_worker():
    global history_24h
    while True:
        now_utc = time.gmtime(time.time())
        next_hour = (now_utc.tm_hour + 1) % 24
        sleep_seconds = (3600 - (now_utc.tm_min * 60 + now_utc.tm_sec)) + 5 
        time.sleep(sleep_seconds) 
        with history_lock:
            for band in HISTORY_BANDS:
                history_24h[band] = history_24h[band][1:] + [0]
            print(f"HISTORY 24H: Shifted and reset hour {next_hour}")

def ticker_worker():
    while True:
        msgs = [f"SYSTEM ONLINE - {MY_CALL}"]
        try:
            req = urllib.request.Request(SOLAR_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                l = [x for x in r.read().decode('utf-8').split('\n') if x and not x.startswith((':','#'))]
                if l: msgs.append(f"SOLAR: {l[-1]}")
        except: pass
        try:
            feed = feedparser.parse(RSS_URLS[0])
            if feed.entries:
                news = [entry.title for entry in feed.entries[:5]]
                msgs.append("NEWS: " + " | ".join(news))
        except Exception as e: 
            print(f"RSS Error: {e}")
        ticker_info["text"] = "   +++   ".join(msgs)
        time.sleep(1800) 

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
                        
                        # Utilisation du nouveau moteur DRSE
                        spd_score = calculate_spd_score(dx_call, band, mode, comment, info['c'], info['lat'], info['lon'])
                        color = BAND_COLORS.get(band, '#00f3ff')
                        
                        record_surge_data(band)
                        
                        spot_obj = {
                            "timestamp": time.time(), "time": time.strftime("%H:%M"),
                            "freq": freq_str, "dx_call": dx_call, "band": band, "mode": mode,
                            "country": info['c'], "lat": info['lat'], "lon": info['lon'],
                            "score": spd_score, 
                            # is_wanted: vrai si le score SPD dépasse le seuil (Tâche 2 et 4)
                            "is_wanted": spd_score >= SPD_THRESHOLD,
                            "via_eme": ("EME" in comment),
                            "color": color,
                            "type": "VHF" if band in VHF_BANDS else "HF"
                        }
                        spots_buffer.append(spot_obj)
                        print(f"SPOT: {dx_call} ({band}) -> SPD: {spd_score} pts (Wanted: {spot_obj['is_wanted']})")
                    except Exception as e: 
                        # print(f"Parse Error: {e}") # Debug seulement
                        pass
        except: pass
        time.sleep(5)
        idx = (idx + 1) % len(CLUSTERS)

# --- ROUTES ---
@app.route('/')
def index():
    # Passage du nouveau seuil au frontend (SPD_THRESHOLD)
    return render_template('index.html', version=APP_VERSION, my_call=MY_CALL, 
                           hf_bands=HF_BANDS, vhf_bands=VHF_BANDS, band_colors=BAND_COLORS,
                           spd_threshold=SPD_THRESHOLD) 

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
        # Tri basé sur le nouveau SPD_SCORE
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

@app.route('/history.json')
def get_history():
    now_hour = time.gmtime(time.time()).tm_hour
    
    labels = []
    for i in range(24):
        h = (now_hour - (23 - i)) % 24
        labels.append(f"H-{23-i} ({h:02}h)") 
        
    with history_lock:
        data = {band: list(hist) for band, hist in history_24h.items()} 

    current_data = {}
    for band in HISTORY_BANDS:
        hist_list = data[band]
        rotated = hist_list[now_hour+1:] + hist_list[:now_hour+1]
        current_data[band] = rotated
        
    return jsonify({"labels": labels, "data": current_data})


if __name__ == "__main__":
    load_cty_dat()
    load_watchlist()
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    threading.Thread(target=history_maintenance_worker, daemon=True).start() 
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)