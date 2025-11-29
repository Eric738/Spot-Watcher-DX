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
APP_VERSION = "NEURAL AI v2.2 (Yellow Ops)" 
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

# --- DEFINITIONS BANDES (6m déplacé en HF) ---
HF_BANDS = ['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
VHF_BANDS = ['4m', '2m', '70cm', '23cm', '13cm', 'QO-100']

# Palette officielle
BAND_COLORS = {
    '160m': '#5c4b51', '80m': '#8e44ad', '60m': '#2c3e50',
    '40m': '#2980b9', '30m': '#16a085', '20m': '#27ae60',
    '17m': '#f1c40f', '15m': '#e67e22', '12m': '#d35400',
    '10m': '#c0392b', 
    '6m': '#e84393', '4m': '#ff9ff3', '2m': '#f1c40f', 
    '70cm': '#c0392b', '23cm': '#8e44ad', '13cm': '#bdc3c7',
    'QO-100': '#00a8ff'
}

# Flux RSS (DX-World ou ARRL par exemple)
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
ticker_info = {"text": "Initialisation..."}
watchlist = set()

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

# --- IA & LOGIC ---
def calculate_ai_score(call, band, mode, comment, country):
    score = 10 
    call = call.upper(); comment = (comment or "").upper()
    
    RARE_PREFIXES = ['3Y', 'BS7', 'CE0', 'CY9', 'P5', 'VP8', 'VQ9', 'ZK', 'ZL9', 'ZS8', 'BV9', 'EZ', 'VK0', 'TR8', 'HV', '1A', '4U', 'E4', 'SV/A', 'T77', 'T88', '9J', 'XU', '3D2', 'S21', 'KH0']
    for p in RARE_PREFIXES:
        if call.startswith(p): score += 50; break 
    
    if 'UP' in comment or 'SPLIT' in comment: score += 15
    if 'DX' in comment: score += 5
    if band in VHF_BANDS: score += 40 
    if band == '10m' or band == '6m': score += 20
    if mode == 'CW': score += 10
    if 'PIRATE' in comment: score = 0
    return min(score, 100)

def get_band_and_mode_smart(freq_float, comment):
    comment = (comment or "").upper()
    f = float(freq_float)
    if f < 1000: f = f * 1000.0
    if f > 1000000: f = f / 1000.0

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
        if freq_khz > 10000000: return "QO-100"
        return "Unknown"

    band = find_band(f)
    mode = "SSB"
    if "FT8" in comment: mode = "FT8"
    elif "FT4" in comment: mode = "FT4"
    elif "CW" in comment: mode = "CW"
    elif "FM" in comment: mode = "FM"
    
    if band in ["30m", "20m"] and f < 14100 and mode=="SSB": mode = "CW"
    
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

# --- WORKERS ---
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
        
        # 2. RSS Data (Correction)
        try:
            feed = feedparser.parse(RSS_URLS[0])
            if feed.entries:
                # On prend les 15 derniers titres
                news = [entry.title for entry in feed.entries[:15]]
                msgs.append("NEWS: " + " | ".join(news))
        except Exception as e: 
            print(f"RSS Error: {e}")

        ticker_info["text"] = "   ++++updated every 30mn   ".join(msgs)
        time.sleep(600) # Update toutes les 30 min

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
                        print(f"SPOT: {dx_call} ({band}) -> {score}")
                    except: pass
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

if __name__ == "__main__":
    load_cty_dat()
    load_watchlist()
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
