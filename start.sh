#!/bin/bash

# 1. Définition des couleurs pour les logs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[INIT] Démarrage de Radio Spot Watcher DX v6.2...${NC}"

# 2. Gestion du port 5000 (Flask par défaut) ou 8000
# Note: Flask tourne souvent sur 5000, on nettoie les deux par sécurité
for PORT in 5000 8000; do
    PID=$(lsof -t -i:$PORT)
    if [ -n "$PID" ]; then
        echo -e "${RED}[WARN] Le port $PORT est occupé par le PID $PID.${NC}"
        echo -e "${YELLOW}[ACTION] Arrêt forcé du processus $PID...${NC}"
        kill -9 $PID
        sleep 1
    fi
done
echo -e "${GREEN}[OK] Ports nettoyés.${NC}"

# 3. Vérification de l'environnement Python
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[INSTALL] Création de l'environnement virtuel...${NC}"
    python3 -m venv venv
fi

# On active l'environnement pour les commandes suivantes
source venv/bin/activate

# 4. Installation/Vérification des dépendances
# On le fait à chaque fois, c'est très rapide si c'est déjà là
echo -e "${YELLOW}[CHECK] Vérification des librairies (Flask, Requests, BS4)...${NC}"
pip install flask requests beautifulsoup4 > /dev/null 2>&1

# 5. Lancement de l'application
echo -e "${GREEN}[START] Lancement de l'application Flask...${NC}"
python webapp.py
