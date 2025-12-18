# 📡 DX Cluster Dashboard – v4.4

Dashboard web temps réel pour radioamateurs, connecté à un DX Cluster via Telnet.  
Conçu pour la **veille DX**, la **visualisation géographique**, l’**analyse d’activité**, et l’**interaction directe** avec le cluster (spot manuel, synthèse vocale, etc.).

---

## 🚀 Fonctionnalités principales

### 🔗 Connexion DX Cluster
- Connexion Telnet persistante à un DX Cluster (ex : dxfun.com)
- Récupération continue des spots
- Gestion automatique de la reconnexion

### 🗺️ Carte DX mondiale
- Affichage en temps réel des stations spotées
- Géolocalisation basée sur **DXCC / cty.dat**
- Mise à jour automatique du fichier `cty.dat` au démarrage (download + parsing)
- Clustering visuel des spots pour lisibilité

### 📊 Statistiques & graphiques
- Histogramme d’activité sur **12 heures**
- Bandes actives en temps réel
- Détection de surges / pics d’activité
- Historique exploitable côté front

### 🧲 Panneaux (pavés) dynamiques
- **Layout multi-colonnes**
- Tous les pavés sont **drag & drop**
- Position mémorisée (localStorage)
- Architecture modulaire (ajout de panneaux facile)

### ☀️ Indices solaires
- Pavé dédié (SFI, A, K, etc.)
- Rafraîchissement automatique (toutes les heures)
- Données XML parsées côté backend

### 🗣️ Synthèse vocale (TTS)
- Annonce vocale des nouveaux spots
- Langues supportées :
  - 🇫🇷 Français (fr-FR)
  - 🇬🇧 English (en-US)
  - 🇪🇸 Español (es-ES)
  - 🇮🇱 עברית (he-IL)
- Fonctionne sur desktop et mobile (après interaction utilisateur)

### ✍️ Spot manuel
- Pavé “Spot Manuel”
- Saisie :
  - Indicatif
  - Fréquence (MHz ou kHz)
  - Commentaire
- Envoi direct vers le DX Cluster
- Retour d’état immédiat

### 📡 Watchlist & alertes
- Watchlist de calls
- Alertes visuelles et vocales
- API REST prête pour automatisation

---

## 🧠 Architecture

- **Backend** : Python / Flask
- **Frontend** : HTML + JavaScript (vanilla)
- **Cartographie** : Leaflet
- **Données DXCC** : `cty.dat` (auto-téléchargé)
- **API** :
  - `/spots.json`
  - `/history.json`
  - `/live_bands.json`
  - `/surge.json`
  - `/rss.json`
  - `/spot` (POST)
  - Compatibilité `/api/*`

---

## 📸 Aperçu

![Apercu du Dashboard](apercu.png)

---

## 🛠️ Installation rapide

```bash
git clone https://github.com/Eric738/Spot-Watcher-DX.git
ou gh repo clone Eric738/Spot-Watcher-DX
cd dx-cluster-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python webapp.py

Puis ouvrir :
👉 http://127.0.0.1:8000
⚠️ Notes importantes

    Le premier déclenchement de la synthèse vocale nécessite un clic utilisateur (restriction navigateur).

    Sur mobile, vérifier que le moteur TTS est bien installé (Android / iOS).

    Le fichier cty.dat est téléchargé automatiquement s’il est absent ou invalide.

🧩 Évolutions possibles

    Filtrage avancé par mode / bande

    Heatmap DX par zone

    Analyse de propagation anormale

    Export CSV / ADIF

    Intégration SDR / WSJT-X

Feel free to modify and share.
Created by F1SMV Eric for Ham Radio Communauty with #GIMINI3 #chatGPT.
Vous pouvez me joindre via X.


---




ChatGPT can make mistakes. Check important info. See Cookie Preferences.