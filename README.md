# 📡 NEURAL DX CLUSTER (v2.0)

> **L'intelligence artificielle au service du DXing.**
> Un agrégateur de spots radioamateurs nouvelle génération, doté d'analyse comportementale temps réel, de détection d'ouvertures de propagation (Surge) et d'une interface visuelle immersive.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-yellow.svg)
![Status](https://img.shields.io/badge/status-OPERATIONAL-green.svg)

## 📋 Présentation

Le **Neural DX Cluster** n'est pas un simple afficheur de spots Telnet. C'est un moteur d'analyse (écrit en Python) qui se connecte au réseau mondial, ingère les données brutes, et les traite via un algorithme de scoring pour identifier **ce qui est intéressant maintenant**.

Il remplace les listes textuelles interminables par un tableau de bord visuel (Cartes, Graphiques, Alertes) inspiré des interfaces Cyberpunk/Sci-Fi.

---
![Apercu du Dashboard] (capture.png)
## 🌟 Fonctionnalités Clés

### 🧠 1. Neural Scoring (Le "Cerveau")
Chaque spot reçu se voit attribuer une note de **0 à 100** en temps réel selon plusieurs critères :
*   **Rareté du DXCC :** Un pays rare booste le score (ex: P5, 3Y...).
*   **Bande/Fréquence :** Pondération intelligente.
*   **Mode :** CW/SSB/FT8.
*   **Distance & Géolocalisation :** Calcul via Maidenhead Locator et base de données CTY.

### ⚡ 2. Système SURGE (Détection d'Ouverture)
L'innovation majeure de la v2. Le système surveille le **débit de spots** par bande.
*   Si une bande calme (ex: 10m) reçoit soudainement une rafale de spots, le système déclenche une alerte **SURGE**.
*   **Visuel :** Bannière d'alerte clignotante, barres du graphique devenant blanches, marqueurs pulsants sur la carte.
*   **Audio :** Annonce vocale immédiate.

### 👁️ 3. Interface Immersive
*   **Carte Mondiale Live :** Visualisation géographique des spots (Leaflet).
*   **Graphique d'Activité :** Histogramme temps réel de l'activité par bande.
*   **Thèmes Dynamiques :** Changez l'ambiance en un clic (Matrix, Cyber, Amber, Neon, Light).
*   **News Ticker :** Flux RSS (Solar data, DX News) défilant type "Bourse".

---

## ⚙️ Architecture & Logique Système

### Structure des fichiers
*   `webapp.py` : **Le Cœur du système.** Gère la connexion Telnet, l'analyse IA, la détection Surge et le serveur Web Flask.
*   `templates/index.html` : L'interface utilisateur (Frontend).
*   `cty.dat` : Base de données des pays (téléchargée automatiquement).
*   `watchlist.json` : Sauvegarde de vos indicatifs surveillés.

### Comment fonctionne la détection SURGE ?
Le système Surge repose sur une analyse différentielle de l'historique des spots (Sliding Window Algorithm) implémentée dans `webapp.py`.

1.  **Collecte :** Le backend enregistre le timestamp de chaque spot par bande.
2.  **Analyse :** 
    *   Il calcule la moyenne d'activité sur 15 minutes (`SURGE_WINDOW`).
    *   Il compare l'activité de la **dernière minute** à cette moyenne.
3.  **Déclenchement :**
    *   Si `Activité > Moyenne * 3` (Seuil définissable) : **SURGE DETECTED**.
    *   Le serveur envoie l'alerte au navigateur via `/surge.json`.

---

## 🚀 Installation et Démarrage

### Prérequis
*   Python 3.8 ou supérieur.
*   Une connexion internet stable.

### 1. Installation des dépendances
Installez les librairies nécessaires via pip :
```bash
pip install flask feedparser
# Note : telnetlib est inclus par défaut dans Python < 3.13. 
# Si vous utilisez Python 3.13+, vous devrez peut-être installer 'telnetlib3' ou une alternative.

 Configuration
Ouvrez le fichier webapp.py et modifiez la section CONFIG au début du fichier :

MY_CALL = "F1SMV"        # Votre indicatif
WEB_PORT = 8000          # Port du serveur web
SURGE_THRESHOLD = 3.0    # Sensibilité de la détection d'ouverture
3. Lancement
Exécutez simplement le script principal :

python webapp.py
Le terminal affichera :

[SYSTEM] Connexion au cluster...
[RSS] RSS OK: 20 news chargees.
[FLASK] Running on http://0.0.0.0:8000
4. Accès
Ouvrez votre navigateur et allez sur : http://localhost:8000

📖 Guide de l'Interface
Le Tableau de Bord
Top Left (Carte) :
🔵 Couleurs : Synchronisées avec le backend (10m = Rouge, 20m = Vert, etc.).
⚪ Blanc Pulsant : Bande en SURGE.
Top Right (Wanted IA) : Liste prioritaire triée par l'IA.
Bottom Left (Live Flux) : La liste brute défilante.
Bottom Right (Watchlist & Chart) :
Entrez un indicatif pour le surveiller (alerte vocale immédiate).
Le graphique montre quelle bande est ouverte actuellement.
Contrôles
VOICE : Active/Désactive la synthèse vocale.
THEME : Change la palette de couleurs.
FILTRES : Filtrez par Bande ou Mode pour nettoyer l'affichage.
🤝 Crédits
Développé par F1SMV pour la communauté Radioamateurgrace à GIMINI3 #codevibing
Propulsé par Python, Flask et LeafletJS.

Happy DXing & 73!
