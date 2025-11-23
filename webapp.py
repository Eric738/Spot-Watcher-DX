import time
import telnetlib
import threading
import json
import os
import urllib.request
import feedparser
from collections import deque, Counter
from flask import Flask, render_template, jsonify

# --- CONFIGURATION ---
APP_VERSION = "v7.2-Watchlist"
BUILD_DATE = "23/11/2025"

# LISTE DES CLUSTERS (Failover)
CLUSTERS = [
    ("dxfun.com", 8000),      # Primaire
    ("dx.f5len.org", 7300),   # Secours (F5LEN)
    ("gb7mbc.spud.club", 8000)# Secours 2
]

RSS_URLS = [
    "https://feeds.feedburner.com/dxzone/dx",
    "https://feeds.feedburner.com/dxzone/hamradio"
]

# --- TA WATCHLIST (Mets ici les indicatifs que tu veux voir en JAUNE) ---
WATCHLIST = ["VP6A", "FT4YM", "3B8M", "TX5S"] 

MY_CALL = "F1SMV"             
KEEP_ALIVE = 60    
SPOT_LIFETIME_DISPLAY = 900   
SPOT_LIFETIME_STATS = 86400   

CTY_URL = "https://www.country-files.com/cty/cty.dat"
CTY_FILE = "cty.dat"

app = Flask(__name__)

spots_buffer = deque(maxlen=20000)
prefix_db = {} 
ticker_info = {"text": f"DX Watcher {APP_VERSION} - Initialisation...", "updated": 0}

# --- 1. GESTION CTY.DAT ---
def download_cty():
    print(f"--- Téléchargement de {CTY_FILE} ...")
    try:
        req = urllib.request.Request(CTY_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            with open(CTY_FILE, "wb") as f: f.write(response.read())
        print("--- CTY Download OK")
        return True
    except Exception as e: 
        print(f"--- Erreur CTY Download: {e}")
        return False

def load_cty_dat():
    global prefix_db
    if not os.path.exists(CTY_FILE): 
        if not download_cty(): return

    print("--- Chargement CTY (Mode: Flatten & Split)...")
    try:
        with open(CTY_FILE, "rb") as f: 
            raw_content = f.read().decode('latin-1')
        
        new_db = {}
        content = raw_content.replace('\r', '').replace('\n', ' ')
        records = content.split(';')
        
        count = 0
        for record in records:
            record = record.strip()
            if not record or ':' not in record: continue

            parts = record.split(':')
            if len(parts) < 8: continue

            country_name = parts[0].strip()
            try:
                lat = float(parts[4])
                lon = float(parts[5]) * -1
            except: lat, lon = 0.0, 0.0

            primary_prefix = parts[7].strip()
            aliases_str = ":".join(parts[8:])
            aliases = aliases_str.split(',')
            all_prefixes = [primary_prefix] + aliases

            for p in all_prefixes:
                p = p.upper().strip()
                if '(' in p: p = p.split('(')[0]
                if '[' in p: p = p.split('[')[0]
                if '{' in p: p = p.split('{')[0]
                if '<' in p: p = p.split('<')[0]
                
                is_exact = False
                if p.startswith('='):
                    is_exact = True
                    p = p[1:]

                p = p.strip()
                if p:
                    new_db[p] = {'country': country_name, 'lat': lat, 'lon': lon, 'exact': is_exact}
                    count += 1

        prefix_db = new_db
        print(f"--- SUCCÈS : {len(prefix_db)} préfixes chargés.")
        
    except Exception as e: 
        print(f"--- Erreur CRITIQUE parsing CTY: {e}")

def cty_worker():
    while True:
        time.sleep(86400)
        download_cty()
        load_cty_dat()

# --- 2. MATCHING ---
def lookup_country(callsign):
    call = callsign.upper().strip()
    if not prefix_db: return 0, 0, "Loading..."

    candidates = [call]
    if '/' in call:
        parts = call.split('/')
        candidates = parts + [call]

    best_match = None
    best_len = 0

    for c in candidates:
        for i in range(len(c), 0, -1):
            sub = c[:i]
            if sub in prefix_db:
                data = prefix_db[sub]
                if data['exact']:
                    if sub == c: return data['lat'], data['lon'], data['country']
                    else: continue
                if len(sub) > best_len:
                    best_len = len(sub)
                    best_match = data

    if best_match: return best_match['lat'], best_match['lon'], best_match['country']
    return 0, 0, "Unknown"

# --- 3. WORKERS ---
def info_worker():
    while True:
        messages = []
        try:
            req = urllib.request.Request("https://services.swpc.noaa.gov/text/wwv.txt", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read().decode('utf-8')
                lines = [l for l in data.split('\n') if l.strip() and not l.startswith(':') and not l.startswith('#')]
                if lines: messages.append(f"SOLAR: {lines[-1]}")
        except Exception as e:
            print(f"Erreur NOAA: {e}")
            messages.append("SOLAR: N/A")
        
        print("--- Mise à jour des flux RSS ---")
        for url in RSS_URLS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    messages.append(f"NEWS: {entry.title}")
            except Exception as e:
                print(f"Erreur RSS ({url}): {e}")

        messages.append(f"DX WATCHER {APP_VERSION} ONLINE")
        ticker_info["text"] = "   +++   ".join(messages)
        time.sleep(900)

def telnet_worker():
    cluster_index = 0
    
    while True:
        host, port = CLUSTERS[cluster_index]
        print(f"--- Tentative connexion Cluster: {host}:{port} ---")
        
        try:
            tn = telnetlib.Telnet(host, port, timeout=15)
            try:
                tn.read_until(b"login: ", timeout=5)
            except: pass
            
            tn.write(MY_CALL.encode('ascii') + b"\n")
            print(f"--- CONNECTÉ À {host} ---")
            
            last_ping = time.time()

            while True:
                try:
                    line = tn.read_until(b"\n", timeout=2).decode('ascii', errors='ignore').strip()
                    if not line:
                        if time.time() - last_ping > KEEP_ALIVE + 10:
                            tn.write(b"\n")
                            last_ping = time.time()
                        continue

                    if line.startswith("DX de"):
                        parts = line.split()
                        if len(parts) > 4:
                            freq_str = parts[3]
                            dx_call = parts[4]
                            
                            lat, lon, country = lookup_country(dx_call)
                            
                            try: f_raw = float(freq_str)
                            except: f_raw = 0.0
                            f_mhz = f_raw / 1000.0 

                            band = "Other"
                            if 1.8 <= f_mhz <= 2.0: band = "160m"
                            elif 3.5 <= f_mhz <= 4.0: band = "80m"
                            elif 7.0 <= f_mhz <= 7.3: band = "40m"
                            elif 10.1 <= f_mhz <= 10.15: band = "30m"
                            elif 14.0 <= f_mhz <= 14.35: band = "20m"
                            elif 18.068 <= f_mhz <= 18.168: band = "17m"
                            elif 21.0 <= f_mhz <= 21.45: band = "15m"
                            elif 24.89 <= f_mhz <= 24.99: band = "12m"
                            elif 28.0 <= f_mhz <= 29.7: band = "10m"
                            elif 50.0 <= f_mhz <= 54.0: band = "6m"
                            elif 144.0 <= f_mhz <= 148.0: band = "2m"  
                            elif 430.0 <= f_mhz <= 440.0: band = "70cm"
                            elif f_mhz > 2300.0: band = "QO-100"

                            comment = " ".join(parts[5:]).upper()
                            mode = "SSB"
                            if "FT8" in comment or "FT4" in comment: mode = "FT8"
                            elif "CW" in comment: mode = "CW"
                            elif "RTTY" in comment or "PSK" in comment: mode = "DIGI"
                            
                            # --- LOGIQUE WATCHLIST ---
                            is_wanted = dx_call in WATCHLIST

                            spot = {
                                "time": time.strftime("%H:%M", time.gmtime()),
                                "timestamp": time.time(),
                                "freq": freq_str, 
                                "dx_call": dx_call,
                                "band": band, 
                                "mode": mode,
                                "country": country, 
                                "lat": lat, 
                                "lon": lon,
                                "is_wanted": is_wanted # On envoie l'info au HTML
                            }
                            spots_buffer.append(spot)

                    if time.time() - last_ping > KEEP_ALIVE:
                        tn.write(b"\n")
                        last_ping = time.time()

                except Exception as e:
                    print(f"Erreur lecture boucle: {e}")
                    break 

        except Exception as e:
            print(f"--- Échec connexion {host}: {e}")
        
        time.sleep(5)
        cluster_index = (cluster_index + 1) % len(CLUSTERS)

# --- 4. ROUTES FLASK ---
@app.route('/')
def index():
    return render_template('index.html', my_call=MY_CALL, version=APP_VERSION, date=BUILD_DATE)

@app.route('/spots.json')
def get_spots():
    now = time.time()
    active = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME_DISPLAY]
    return jsonify(list(reversed(active)))

@app.route('/wanted.json')
def get_wanted():
    now = time.time()
    stats_pool = [s for s in spots_buffer if (now - s['timestamp']) < SPOT_LIFETIME_STATS]
    c_list = [s['country'] for s in stats_pool if s['country'] != "Unknown"]
    return jsonify(Counter(c_list).most_common(10))

@app.route('/rss.json')
def get_rss():
    return jsonify({"ticker": ticker_info["text"]})

if __name__ == "__main__":
    load_cty_dat()
    threading.Thread(target=telnet_worker, daemon=True).start()
    threading.Thread(target=info_worker, daemon=True).start()
    threading.Thread(target=cty_worker, daemon=True).start()
    
    print(f"--- DX Watcher {APP_VERSION} Started ---")
    app.run(host='0.0.0.0', port=8000, debug=False)
