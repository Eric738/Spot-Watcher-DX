NEURAL DX WATCHER V4.3
🛰️ Introduction

**NEURAL DX WATCHER V4.3** est une application web de nouvelle génération conçue spécifiquement pour les radioamateurs (DXers). Elle offre un tableau de bord en temps réel pour suivre les spots DX (stations lointaines) sur les bandes HF et VHF/UHF, complété par un module d'analyse cognitive avancé. L'objectif est de centraliser les données de propagation, les alertes, l'historique d'activité et la cartographie pour ne manquer aucune opportunité DX.

Cette version 4.3 incorpore la granularité de prévision à très court terme (30 min / 1h) dans son modèle IA et assure une navigation portable et robuste entre ses modules.

✨ Fonctionnalités Générales

* **Temps Réel :** Affichage instantané des spots DX.
* **Panneaux Personnalisables :** Fonctionnalité **Drag & Drop** pour organiser les panneaux sur les deux pages (Dashboard et Analyse). L'ordre est sauvegardé localement.
* **Thèmes :** Bascule simple entre les modes SoftTech, Matrix et Dark (synchronisé entre les pages).
* **Portabilité :** Navigation fluide entre le Dashboard et l'Analyse, quel que soit l'environnement serveur.

---

### 1. DASHBOARD (`index.html`) - Le Centre de Contrôle Temps Réel

Le Dashboard est la page principale de l'application, conçue pour fournir une vue immédiate et interactive de l'activité DX mondiale.

| Module | Description Détaillée |
| :--- | :--- |
| **Spots DX en Temps Réel** | Liste dynamique et filtrable de tous les spots reçus. Les spots critiques (Score de Priorité DX > 70) sont mis en évidence pour alerter l'opérateur. |
| **Synthèse Vocale Avancée** | Annonce sonore des nouveaux spots. Un bouton **🔊 VOICE ON/OFF** permet d'activer ou de désactiver la voix. |
| **Filtre Vocal de Distance** | Un sélecteur permet de filtrer les annonces vocales en fonction de la distance (par rapport à votre QRA). Les options incluent : `ALL`, `< 5000 km`, `5000 - 10000 km`, et `> 10000 km` (pour le DX "Long Haul"). |
| **Cartographie Intégrée** | Deux cartes Leaflet distinctes : **HF** et **VHF/UHF**. Elles affichent la localisation de votre QTH et des spots DX actifs en temps réel. |
| **Historique d'Activité** | Un graphique de l'activité des bandes sur une fenêtre de **12 heures**, avec une granularité de **30 minutes**, essentiel pour identifier les fenêtres d'ouverture régulières. |
| **Watchlist** | Permet d'ajouter et de supprimer des indicatifs d'appel (Callsigns) prioritaires. Les spots correspondant à votre Watchlist sont mis en évidence. |
| **Gestion QRA** | Un formulaire permet de définir rapidement votre localisateur QRA. La mise à jour est immédiate et le QRA s'affiche en haut de la page. |
| **Surge Alerts** | Détection et affichage des pics d'activité inhabituels (alerts en rouge) sur une bande donnée, signalant une ouverture soudaine. |

---

### 2. AI INSIGHT (`analysis.html`) - Module d'Analyse 24H

Accessible via le bouton **📊 AI INSIGHT**, cette page utilise le modèle IA pour digérer les données DXCC des dernières 24 heures et fournir des projections et des statistiques de rareté.

| Module | Description Détaillée |
| :--- | :--- |
| **COGNITIVE DX FORECAST (NEXT 48H)** | Prédiction de la propagation globale basée sur le modèle NEURAL v4.3. Ce graphique de ligne est vital pour la planification d'activité. |
| **Nouveaux Horizons de Prévision** | L'Axe X (Temps) inclut maintenant des horizons très courts pour la prise de décision immédiate : **H+0.5** (30 min), **H+1** (1 heure), H+6, H+24 et H+48. |
| **Métriques DXCC Avancées** | Affiche trois métriques clés basées sur l'activité des dernières 24 heures : **Calls Spottés > 10 000 km**, **Taux de Rareté (SPD > 70)** et **Spots Rares Absolus (SPD > 70)** (liste des DXCC rares spottés). |
| **DXCC Uniques par Mode** | Diagramme à barres montrant la concentration des DXCC uniques travaillés par mode (FT8, CW, SSB...). Utile pour la **priorisation de l'activité**. |
| **DXCC Uniques par Bande** | Diagramme à barres montrant la concentration des DXCC uniques travaillés par bande (20m, 15m, 40m...). Utile pour l'**optimisation de la propagation**. |

---

### 📸 Aperçu de l'Interface

![Apercu du Dashboard](apercu.png)

---

### ⚙️ Installation & Démarrage

Ce projet est basé sur Python (Flask) pour le backend et HTML/CSS/JavaScript (Leaflet, Chart.js) pour l'interface client.

#### Prérequis

* Python 3.x
* Accès Internet
* Bibliothèques Python listées dans `requirements.txt` (ou installez manuellement `flask`, `telnetlib`, `requests`, `feedparser`, etc.)

#### Étapes de Démarrage

1.  **Clonez le dépôt :**
    ```bash
    git clone gh repo clone Eric738/Spot-Watcher-DX
    cd neural-dx-watcher-v4
    ```
2.  **Installez les dépendances Python :**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configurez votre QRA :** Ouvrez `webapp.py` et modifiez les variables de configuration au début du fichier, notamment `MY_CALL` et `DEFAULT_QRA`.
4.  **Lancez l'application :**
    ```bash
    python webapp.py
    ```
    L'application sera accessible via votre navigateur à l'adresse par défaut : `http://127.0.0.1:8000` (ou le port configuré).

---

### 🛠️ Configuration (webapp.py)

Les principaux paramètres de l'application se trouvent au début du fichier `webapp.py` :

| Variable | Description | Valeur par Défaut |
| :--- | :--- | :--- |
| `MY_CALL` | Votre indicatif d'appel. | F1SMV |
| `DEFAULT_QRA` | Votre localisateur QRA (ex: JN23). | JN23 |
| `SPD_THRESHOLD` | Seuil du Score de Priorité DX pour les alertes (spots en rouge). | 70 |
| `SPOT_LIFETIME` | Durée pendant laquelle un spot reste actif (en secondes). | 1800 (30 minutes) |

---
*Feel free to modify and share. Created by F1SMV Eric for Ham Radio Communauty with #GIMINI3.*
