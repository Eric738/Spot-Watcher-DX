import time
import telnetlib
import threading
import json
import os
import urllib.request
from collections import deque, Counter
from flask import Flask, render_template, jsonify, request

# --- CONFIGURATION ---
APP_VERSION = "NEURAL AI v1.2 (FT4/VHF/UHF)" 
MY_CALL = "F1SMV"
WEB_PORT = 8000
KEEP_ALIVE = 60
SPOT_LIFETIME = 1800  # 30 minutes
AI_SCORE_THRESHOLD = 50
TOP_RANKING_LIMIT = 7 # Réduit à 7 pour éviter l'ascenseur (scrollbar)

CLUSTERS = [
    ("dxfun.com", 8000),
    ("dx.f5len.org", 7300),
    ("gb7mbc.spud.club", 8000)
]

CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"
SOLAR_URL = "https://services.swpc.noaa.gov/text/wwv.txt"

RARE_PREFIXES = [
    '3Y', 'BS7', 'CE0X', 'CY9', 'CY0', 'FT5', 'FT8', 'HK0', 'KH1', 'KH3', 
    'KH5', 'KH7K', 'KH9', 'KP1', 'KP5', 'P5', 'T3', 'VP8', 'VQ9', 'ZK', 
    'ZL9', 'ZS8', 'BV9', 'EZ', 'FR/G', 'VK0', 'TR8', 'DP0', 'TY', 'HV', 
    '1A', '4U1UN', 'E4', 'SV/A', 'CE0'
]

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
        if call.startswith(p): score += 50; break 
    
    # Mots clés
    if 'UP' in comment or 'SPLIT' in comment: score += 15
    if 'DX' in comment: score += 5
    
    # Bandes & Modes (Bonus VHF/UHF)
    if band in ['6m', '2m', '70cm']: score += 30
    if band in ['10m', '12m', '160m']: score += 20
    if mode == 'CW': score += 10
    
    # Pénalités
    if 'PIRATE' in comment: score = 0
    
    return min(score, 100)

# --- FILTRES BANDES & MODES INTELLIGENTS ---
def get_band_and_mode_smart(freq_float, comment):
    """
    Détermine la bande et le mode précis.
    Gère HF, VHF (2m), UHF (70cm) et distingue FT4/FT8.
    """
    # 1. Nettoyage
    comment = comment.upper()
    
    # 2. Conversion MHz -> kHz si nécessaire
    f = freq_float
    if f < 1000: f = f * 1000 
    
    # 3. Détection Bande
    band = "Unknown"
    if 1800 <= f <= 2000: band = "160m"
    elif 3500 <= f <= 3800: band = "80m"
    elif 7000 <= f <= 7200: band = "40m"
    elif 10100 <= f <= 10150: band = "30m"
    elif 14000 <= f <= 14350: band = "20m"
    elif 18068 <= f <= 18168: band = "17m"
    elif 21000 <= f <= 21450: band = "15m"
    elif 24890 <= f <= 24990: band = "12m"
    elif 28000 <= f <= 29700: band = "10m"
    elif 50000 <= f <= 54000: band = "6m"
    elif 144000 <= f <= 146000: band = "2m"    
    elif 430000 <= f <= 440000: band = "70cm"  
    elif f > 10000000: band = "QO-100"

    # 4. Détection Mode (Priorité au commentaire pour FT4/FT8)
    # On retourne le mode précis si trouvé
    if "FT4" in comment: return band, "FT4"
    if "FT8" in comment: return band, "FT8"
    if "CW" in comment: return band, "CW"
    if "SSB" in comment or "USB" in comment or "LSB" in comment: return band, "SSB"
    if "RTTY" in comment: return band, "RTTY"
    if "FM" in comment: return band, "FM"

    # Sinon, on devine via la fréquence (Logique IARU)
    mode = "DATA" # Par défaut

    if band == "40m":
        if f < 7040: mode = "CW"
        elif f < 7050: mode = "DATA" # Souvent FT8/FT4 ici
        else: mode = "SSB"
    elif band == "20m":
        if f < 14070: mode = "CW"
        elif f < 14100: mode = "DATA"
        else: mode = "SSB"
    elif band == "15m":
        if f < 21070: mode = "CW"
        elif f < 21150: mode = "DATA"
        else: mode = "SSB"
    elif band == "10m":
        if f < 28070: mode = "CW"
        elif f < 28300: mode = "DATA"
        else: mode = "SSB"
    elif band == "6m":
        if f < 50100: mode = "CW"
        elif f < 50300: mode = "SSB"
        elif f < 50320: mode = "DATA"
        else: mode = "SSB/FM"
    elif band == "2m":
        if f < 144150: mode = "CW"
        elif f < 144180: mode = "DATA"
        elif f < 144400: mode = "SSB"
        else: mode = "FM"
    elif band == "70cm":
        if f < 432150: mode = "CW"
        elif f < 432200: mode = "DATA"
        else: mode = "SSB/FM"
    elif band in ["30m", "17m", "12m", "80m"]:
        if (f - int(f/1000)*1000) < 50: mode = "CW"
        else: mode = "DATA/SSB"

    return band, mode

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
                        
                        # --- FILTRE INTELLIGENT ---
                        freq_raw = float(parts[1])
                        dx_call = parts[2]
                        comment = " ".join(parts[3:-1]).upper()
                        
                        band, mode = get_band_and_mode_smart(freq_raw, comment)
                        # --------------------------
                        
                        info = get_country_info(dx_call)
                        score = calculate_ai_score(dx_call, band, mode, comment, info['c'])
                        
                        spots_buffer.append({
                            "timestamp": time.time(), "time": time.strftime("%H:%M"),
                            "freq": parts[1], "dx_call": dx_call, "band": band, "mode": mode,
                            "country": info['c'], "lat": info['lat'], "lon": info['lon'],
                            "score": score, "is_wanted": score >= AI_SCORE_THRESHOLD
                        })
                        print(f"AI SCAN: {dx_call} ({band}/{mode}) -> Score {score}")
                    except: pass
        except: pass
        time.sleep(5); idx = (idx + 1) % len(CLUSTERS)

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html', version=APP_VERSION, my_call=MY_CALL, date=time.strftime("%d/%m/%Y"))

@app.route('/spots.json')
def get_spots():
    now = time.time()
    # Support optionnel de filtres via URL ?band=20m&mode=FT8
    filter_band = request.args.get('band')
    filter_mode = request.args.get('mode')
    
    all_spots = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    
    # Application des filtres si demandés
    if filter_band:
        all_spots = [s for s in all_spots if s['band'] == filter_band]
    if filter_mode:
        all_spots = [s for s in all_spots if s['mode'] == filter_mode]
        
    return jsonify(list(reversed(all_spots)))

@app.route('/wanted.json')
def get_ranking():
    now = time.time()
    active = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME]
    
    # Tri par score décroissant
    ranked = sorted(active, key=lambda x: x['score'], reverse=True)
    
    # Dédoublonnage
    seen, top = set(), []
    for s in ranked:
        if s['dx_call'] not in seen:
            top.append({'call': s['dx_call'], 'score': s['score'], 'c': s['country']})
            seen.add(s['dx_call'])
        # LIMITE À 7 POUR ÉVITER L'ASCENSEUR DANS L'INTERFACE
        if len(top) >= TOP_RANKING_LIMIT: break
            
    return jsonify(top)

@app.route('/rss.json')
def get_rss(): return jsonify({"ticker": ticker_info["text"]})

if __name__ == "__main__":
    if not os.path.exists('templates'): os.makedirs('templates')
    load_cty_dat()
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
