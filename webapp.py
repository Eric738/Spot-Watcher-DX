import time
import telnetlib
import threading
import json
import os
import urllib.request
from collections import deque, Counter
from flask import Flask, render_template, jsonify

# --- CONFIGURATION ---
APP_VERSION = "NEURAL AI v1.0"  # MODIFIÉ POUR L'AFFICHAGE
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 1800  # 30 minutes
AI_SCORE_THRESHOLD = 50

CLUSTERS = [
    ("dxfun.com", 8000),
    ("dx.f5len.org", 7300),
    ("gb7mbc.spud.club", 8000)
]

CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"
RSS_URLS = ["https://feeds.feedburner.com/dxzone/dx"]
SOLAR_URL = "https://services.swpc.noaa.gov/text/wwv.txt"

RARE_PREFIXES = [
    '3Y', 'BS7', 'CE0X', 'CY9', 'CY0', 'FT5', 'FT8', 'HK0', 'KH1', 'KH3', 
    'KH5', 'KH7K', 'KH9', 'KP1', 'KP5', 'P5', 'T3', 'VP8', 'VQ9', 'ZK', 
    'ZL9', 'ZS8', 'BV9', 'EZ', 'FR/G', 'VK0', 'TR8', 'DP0', 'TY', 'HV', 
    '1A', '4U1UN', 'E4', 'SV/A'
]

try: import feedparser; HAS_FEEDPARSER = True
except: HAS_FEEDPARSER = False

app = Flask(__name__)
spots_buffer = deque(maxlen=5000)
prefix_db = {}
ticker_info = {"text": "Initialisation Neural Engine..."}

# --- IA CORE ---
def calculate_ai_score(call, band, mode, comment, country):
    score = 10
    call = call.upper(); comment = comment.upper()
    
    # Rareté
    for p in RARE_PREFIXES:
        if call.startswith(p): score += 50; break # Boost énorme pour les rares
    
    # Mots clés
    if 'UP' in comment or 'SPLIT' in comment: score += 15
    if 'DX' in comment: score += 5
    
    # Bandes & Modes
    if band in ['6m', '10m', '12m', '160m']: score += 20
    if mode == 'CW': score += 10
    
    # Pénalités
    if 'PIRATE' in comment: score = 0
    
    return min(score, 100)

# --- CTY ---
def load_cty_dat():
    global prefix_db
    if not os.path.exists(CTY_FILE):
        try:
            urllib.request.urlretrieve(CTY_URL, CTY_FILE)
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
        print(f"--- AI ENGINE: {len(prefix_db)} entities loaded ---")
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
        msgs = [f"NEURAL RANKING ACTIVE - {MY_CALL}"]
        try:
            with urllib.request.urlopen(SOLAR_URL, timeout=10) as r:
                l = [x for x in r.read().decode('utf-8').split('\n') if x and not x.startswith((':','#'))]
                if l: msgs.append(f"SOLAR: {l[-1]}")
        except: pass
        ticker_info["text"] = "   +++   ".join(msgs)
        time.sleep(900)

def telnet_worker():
    idx = 0
    while True:
        host, port = CLUSTERS[idx]
        try:
            tn = telnetlib.Telnet(host, port, timeout=15)
            try: tn.read_until(b"login: ", timeout=5)
            except: pass
            tn.write(MY_CALL.encode('ascii') + b"\n")
            time.sleep(1)
            tn.write(b"show/dx 20\n") 
            last_ping = time.time()
            
            while True:
                line = tn.read_until(b"\n", timeout=2).decode('ascii', errors='ignore').strip()
                if not line:
                    if time.time() - last_ping > KEEP_ALIVE: tn.write(b"\n"); last_ping = time.time()
                    continue
                
                if "DX de" in line:
                    try:
                        parts = line[line.find("DX de")+6:].split()
                        if len(parts) < 4: continue
                        freq = float(parts[1])
                        dx_call = parts[2]
                        comment = " ".join(parts[3:-1]).upper()
                        
                        band = "HF"
                        if 1800<=freq<=2000: band="160m"
                        elif 7000<=freq<=7300: band="40m"
                        elif 14000<=freq<=14350: band="20m"
                        elif 21000<=freq<=21450: band="15m"
                        elif 28000<=freq<=29700: band="10m"
                        elif 50000<=freq<=54000: band="6m"
                        elif freq > 10000000: band="QO-100"
                        
                        mode = "DATA"
                        if "CW" in comment: mode="CW"
                        elif "SSB" in comment: mode="SSB"
                        
                        info = get_country_info(dx_call)
                        score = calculate_ai_score(dx_call, band, mode, comment, info['c'])
                        
                        spots_buffer.append({
                            "timestamp": time.time(), "time": time.strftime("%H:%M"),
                            "freq": parts[1], "dx_call": dx_call, "band": band, "mode": mode,
                            "country": info['c'], "lat": info['lat'], "lon": info['lon'],
                            "score": score, "is_wanted": score >= AI_SCORE_THRESHOLD
                        })
                        print(f"AI SCAN: {dx_call} -> Score {score}")
                    except: pass
        except: pass
        time.sleep(5); idx = (idx + 1) % len(CLUSTERS)

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html', version=APP_VERSION, my_call=MY_CALL, date=time.strftime("%d/%m/%Y"))

@app.route('/spots.json')
def get_spots():
    now = time.time()
    return jsonify(list(reversed([s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME])))

@app.route('/wanted.json')
def get_ranking():
    # C'EST ICI LA CORRECTION MAJEURE
    # On renvoie le TOP 10 des scores IA au lieu des pays
    now = time.time()
    active = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    # Tri par score décroissant
    ranked = sorted(active, key=lambda x: x['score'], reverse=True)
    
    # Dédoublonnage pour le top 10
    seen, top = set(), []
    for s in ranked:
        if s['dx_call'] not in seen:
            top.append({'call': s['dx_call'], 'score': s['score'], 'c': s['country']})
            seen.add(s['dx_call'])
        if len(top) >= 10: break
            
    return jsonify(top)

@app.route('/rss.json')
def get_rss(): return jsonify({"ticker": ticker_info["text"]})

if __name__ == "__main__":
    if not os.path.exists('templates'): os.makedirs('templates')
    load_cty_dat()
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
