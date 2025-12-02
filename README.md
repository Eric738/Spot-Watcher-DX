# 🛰️ NEURAL DX v3.4 - **DRSE (DX Risk Scoring Engine)**

## 💡 Résumé du projet

**NEURAL DX v3.4** est une station de surveillance radioamateur en temps réel, basée sur Python/Flask pour le backend et une interface web dynamique (HTML/CSS/JavaScript). Le projet agrège et analyse les données de spots DX, les visualise sur des cartes en direct, calcule la distance des contacts par rapport à la position de l'opérateur (QRA Locator), et génère des alertes de propagation ciblées. La version intègre un système d'alerte visuelle agressive pour les cibles prioritaires.

---

## ✨ Fonctionnalités clés

* **DRSE (DX Risk Scoring Engine) & Alerte Priorité (Nouveau v3.4) :** Intégration du score de priorité de DX (SPD). Les spots avec un score élevé (SPD >= 70) sont immédiatement signalés par un **clignotement agressif** et une **bordure rouge vif épaisse** sur le Live Stream et le Top DX Wanted, garantissant une visibilité maximale.
* **SPD dans le Live Stream (Nouveau v3.4) :** Le **Score de Priorité de DX (SPD)** est affiché dans une colonne dédiée du tableau Live Stream, avec un fond rouge pour les cibles prioritaires.
* **Calcul de distance personnalisé :** Affiche la distance en **kilomètres** entre le QRA de l'opérateur et chaque spot/entité, y compris dans les tableaux *Top DX Wanted*.
* **Temporisation QRA :** Le message de validation/erreur du QRA Locator saisi (`Valid / Valide`) s'efface automatiquement après **40 secondes**.
* **Cartographie dynamique (HF & VHF/UHF) :** Visualisation des spots en temps réel via des cartes Leaflet distinctes.
* **Live Streams & Top DX Wanted :** Tableaux d'activité.
* **Watchlist & Alertes Vocales :** Surveillance d'indicatifs spécifiques avec notification audio et mise en surbrillance.
* **Alertes de Propagation (Surge) :** Détection et signalisation des pics d'activité sur les bandes.
* **Historique 24H :** Graphique dédié à l'activité sur les bandes magiques (**12m, 10m, 6m**) avec alerte visuelle d'ouverture.
* **Filtres dynamiques :** Filtrage des spots par **bande** et **mode** (CW, SSB, FT8, MSK144, SSTV, etc.).
* **Correction mineure tri mode ft8**
* **application plan de bande cw strict**

---
![Apercu du Dashboard](apercu.png)

## 🏗️ Architecture technique

Le projet utilise une architecture client-serveur simple :

| Composant | Technologie | Rôle |
| :--- | :--- | :--- |
| **Backend** | Python (Flask) | Gestion des données, connexion au DX Cluster (Telnet), calculs de score (AI Score), mise en cache, et service des endpoints JSON. |
| **Frontend** | HTML/CSS/JS | Interface utilisateur. Leaflet pour la cartographie, Chart.js pour les graphiques, Vanilla JS pour la mise à jour dynamique et les interactions (QRA, filtres). |
| **Data Flow** | JSON, Telnet | Flask récupère les spots du Cluster et les formate en JSON. Le JavaScript interroge les endpoints Flask (`/spots.json`, `/wanted.json`, etc.) toutes les 3 secondes pour mettre à jour l'interface. |

---

## 🛠️ Installation et configuration

### Dépendances

Ce projet nécessite les bibliothèques Python suivantes :

* `flask`
* `requests`
* `telnetlib`
* `json`
* `os`
* `threading`
* `feedparser` (pour les RSS)
* `geopy` (ou une librairie de géocoding/distance si la fonction n'est pas codée manuellement)

### Commandes utiles

| Commande | Description |
| :--- | :--- |
| `pip install -r requirements.txt` | Installe toutes les dépendances Python nécessaires. |
| `python webapp.py` | Démarre le serveur Flask sur `http://localhost:8000`. |

### Configuration initiale

Avant l'exécution, vous devez modifier la section de configuration de base dans `webapp.py` :

1.  **Ouvrez `webapp.py`**
2.  **Mettez à jour les constantes suivantes :**

    ```python
    # webapp.py
    MY_CALL = "VOTRE_INDICATIF"  # <-- Indispensable
    WEB_PORT = 8000
    QRA_DEFAULT = "JN33"  # <-- Votre QRA par défaut (pour les calculs de distance)

    # Configuration Telnet DX Cluster
    TELNET_HOST = "cluster.example.com"
    TELNET_PORT = 73
    ```

### Lancement

1.  Assurez-vous que toutes les dépendances sont installées.
2.  Lancez le serveur :
    ```bash
    python webapp.py
    ```
3.  Ouvrez votre navigateur à l'adresse fournie par l'application (par défaut : `http://127.0.0.1:8000`).

---
![Apercu du Dashboard](apercu.png)

## 🚀 Utilisation de l'interface

### 1. Saisie du QRA Locator

Dans la section **COMMAND DECK** :

1.  Entrez votre QRA Locator (ex: `JN33`, `JN33BB`).
2.  Cliquez sur **GO**.
3.  Le système :
    * Centre la carte sur votre position.
    * Met à jour tous les tableaux en calculant la distance.
    * Affiche **"Valid / Valide"** pendant 40 secondes.

### 2. Gestion des filtres

* Utilisez les listes déroulantes **FILTERS** pour affiner l'affichage des spots dans les sections *LIVE STREAM* et sur les cartes (ex: sélectionner `20m` ou `FT8`).

### 3. Watchlist

* Entrez un indicatif (ex: `K1TTT`) dans le champ **WATCHLIST** et cliquez sur **ADD**.
* Les spots pour cet indicatif seront mis en évidence en jaune et déclencheront une alerte vocale (si **VOICE: ON**).

### 4. Systèmes d'alerte (DRSE)

* **Cible Prioritaire (SPD >= 70) :** Les spots critiques déclenchent un **clignotement rouge agressif** et une bordure épaisse dans le Live Stream et le Top DX Wanted pour une identification immédiate.
* **SURGE :** Une bannière rouge apparaît si le nombre de spots sur une bande dépasse le seuil défini dans `webapp.py`.
* **OUVERTURE DETECTEE :** Le panneau *PROPAGATION HISTORY* alerte si l'activité sur les bandes 12m, 10m ou 6m dépasse un seuil récent.

### 5. Demarrage

lancez l'application ./start.sh dans le repertoire radio-spo-watcher-dx
le systeme va automatiquement chargerla base cty.dat et mettre a jour la carte dès reception des spots

enjoy DX !

### Licence MIT

feel free to modify and share . Created for the Amateur Radio Communauty by Eric F1SMV à l'aide de GIMINI3 #codevibing vous pouvez me joindre via mon fil X