# 🛰️ NEURAL DX v4.0 - Mobile Ready & Personnalisable 🚀

## 💡 Résumé du projet

**NEURAL DX v4.0** est une station de surveillance radioamateur en temps réel. Basée sur Python/Flask (backend) et une interface web dynamique (HTML/CSS/JavaScript), cette version combine les performances des précédentes versions avec une flexibilité d'affichage et une meilleure ergonomie. Elle agrège et analyse les données de spots DX, les visualise sur des cartes en direct, calcule la distance des contacts et génère des alertes de propagation ciblées.

---

## 🆕 Nouveautés de la Version 4.0

Cette version majeure apporte des améliorations significatives de l'interface utilisateur :

* **Design Responsive (Mobile Ready) :** L'interface s'adapte désormais automatiquement aux écrans de petite et moyenne taille (smartphones, tablettes) en empilant les panneaux verticalement.
* **Ordonnancement par Glisser-Déposer (Drag & Drop) :** Les panneaux d'information des colonnes latérales peuvent être réorganisés par l'utilisateur avec la souris. Cet ordre est sauvegardé dans le navigateur (`localStorage`).
* **Thèmes Dynamiques :** Le bouton `THEME` affiche désormais le nom du thème actif et bascule entre les 4 styles disponibles : `SOFTTECH`, `MATRIX`, `AMBER`, `NEON`.
* **Amélioration de la Cartographie :** L'indicatif DX (Callsign) est maintenant affiché directement dans l'infobulle (tooltip) de chaque marqueur sur les cartes HF et VHF.

---

## ✨ Fonctionnalités Clés

* **Calcul de distance personnalisé :** Affiche la distance en **kilomètres** entre le QRA de l'opérateur et chaque spot/entité.
* **Cartographie dynamique (HF & VHF/UHF) :** Visualisation des spots en temps réel via des cartes Leaflet distinctes.
* **Watchlist & Alertes Vocales :** Surveillance d'indicatifs spécifiques avec notification audio et mise en surbrillance.
* **Alertes de Propagation (Surge) :** Détection et signalisation des pics d'activité sur les bandes.
* **Historique 24H :** Graphique dédié à l'activité sur les bandes magiques (**12m, 10m, 6m**) avec alerte visuelle d'ouverture.
* **Filtres dynamiques :** Filtrage des spots par bande et par mode (CW, SSB, FT8, MSK144, etc.).

---

## 🛠️ Architecture Technique

Le projet utilise une architecture simple client-serveur :

| Composant | Technologie | Rôle |
| :--- | :--- | :--- |
| **Backend** | Python / Flask | Agrégation des données DX Cluster (Telnet), calculs de distance/score, gestion de la Watchlist et des alertes. |
| **Frontend** | HTML5 / CSS3 / JavaScript | Interface utilisateur dynamique, graphiques (Chart.js), cartographie (Leaflet) et gestion de l'état (Drag & Drop via Sortable.js). |

---

## 🚀 Installation

1.  **Cloner le dépôt :**
    ```bash
    git clone [# 🛰️ NEURAL DX v4.0 - Mobile Ready & Personnalisable 🚀

## 💡 Résumé du projet

**NEURAL DX v4.0** est une station de surveillance radioamateur en temps réel. Basée sur Python/Flask (backend) et une interface web dynamique (HTML/CSS/JavaScript), cette version combine les performances des précédentes versions avec une flexibilité d'affichage et une meilleure ergonomie. Elle agrège et analyse les données de spots DX, les visualise sur des cartes en direct, calcule la distance des contacts et génère des alertes de propagation ciblées.

---

## 🆕 Nouveautés de la Version 4.0

Cette version majeure apporte des améliorations significatives de l'interface utilisateur :

* **Design Responsive (Mobile Ready) :** L'interface s'adapte désormais automatiquement aux écrans de petite et moyenne taille (smartphones, tablettes) en empilant les panneaux verticalement.
* **Ordonnancement par Glisser-Déposer (Drag & Drop) :** Les panneaux d'information des colonnes latérales peuvent être réorganisés par l'utilisateur avec la souris. Cet ordre est sauvegardé dans le navigateur (`localStorage`).
* **Thèmes Dynamiques :** Le bouton `THEME` affiche désormais le nom du thème actif et bascule entre les 4 styles disponibles : `SOFTTECH`, `MATRIX`, `AMBER`, `NEON`.
* **Amélioration de la Cartographie :** L'indicatif DX (Callsign) est maintenant affiché directement dans l'infobulle (tooltip) de chaque marqueur sur les cartes HF et VHF.

---

## ✨ Fonctionnalités Clés

* **Calcul de distance personnalisé :** Affiche la distance en **kilomètres** entre le QRA de l'opérateur et chaque spot/entité.
* **Cartographie dynamique (HF & VHF/UHF) :** Visualisation des spots en temps réel via des cartes Leaflet distinctes.
* **Watchlist & Alertes Vocales :** Surveillance d'indicatifs spécifiques avec notification audio et mise en surbrillance.
* **Alertes de Propagation (Surge) :** Détection et signalisation des pics d'activité sur les bandes.
* **Historique 24H :** Graphique dédié à l'activité sur les bandes magiques (**12m, 10m, 6m**) avec alerte visuelle d'ouverture.
* **Filtres dynamiques :** Filtrage des spots par bande et par mode (CW, SSB, FT8, MSK144, etc.).

---

## 🛠️ Architecture Technique

Le projet utilise une architecture simple client-serveur :

| Composant | Technologie | Rôle |
| :--- | :--- | :--- |
| **Backend** | Python / Flask | Agrégation des données DX Cluster (Telnet), calculs de distance/score, gestion de la Watchlist et des alertes. |
| **Frontend** | HTML5 / CSS3 / JavaScript | Interface utilisateur dynamique, graphiques (Chart.js), cartographie (Leaflet) et gestion de l'état (Drag & Drop via Sortable.js). |

---

## 🚀 Installation

1.  **Cloner le dépôt :**
    ```bash
    git clone [https://github.com/Eric738/Spot-Watcher-DX.git]
    cd neural-dx
    ```

2.  **Installer les dépendances Python :**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration initiale**

    Avant l'exécution, vous devez modifier la section de configuration de base dans `webapp.py` :

    ```python
    # webapp.py
    MY_CALL = "YOUR_CALLSIGN"  # <-- Votre indicatif (essentiel)
    QRA_DEFAULT = "JN33"       # <-- Votre QRA par défaut
    # ... et configurer l'hôte/port du DX Cluster Telnet
    ```

4.  **Lancement**

    Lancez l'application en utilisant le script de démarrage (ou directement `python webapp.py`) :

    ```bash
    ./start.sh
    ```
    Accédez à l'interface via votre navigateur à l'adresse `http://127.0.0.1:8000` (ou le port configuré).

---

## 💻 Aperçu de l'Interface

![Aperçu du Dashboard](apercu.png)

---

## 🖱️ Utilisation de l'interface

### 1. Personnalisation de l'Affichage

* **Thèmes :** Cliquez sur le bouton `THEME: [Nom du Thème]` dans l'en-tête pour changer l'apparence.
* **Glisser-Déposer :** Cliquez et maintenez le clic sur l'en-tête d'un panneau (ex: `LIVE BANDS`, `WATCHLIST`) dans les colonnes gauche ou droite pour le déplacer et changer son ordre d'affichage. L'ordre est conservé au rechargement.

### 2. Saisie du QRA Locator

Dans la section **COMMAND DECK** :

1.  Entrez votre QRA Locator (ex: `JN33`, `JN33BB`).
2.  Cliquez sur **GO**.
3.  Le système centre les cartes sur votre position et met à jour tous les calculs de distance.

### 3. Watchlist

* Entrez un indicatif (ex: `K1TTT`) dans le champ **WATCHLIST** et cliquez sur **ADD**.
* Les spots pour cet indicatif seront mis en évidence et déclencheront une alerte vocale (si `VOICE: ON`).

### 4. Systèmes d'alerte

* **SURGE :** Une bannière apparaît si le nombre de spots sur une bande dépasse le seuil défini dans `webapp.py`.
* **OUVERTURE DETECTEE :** Le panneau *PROPAGATION HISTORY* alerte si l'activité sur les bandes magiques (12m, 10m, 6m) dépasse un seuil récent.]
    cd neural-dx
    ```

2.  **Installer les dépendances Python :**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration initiale**

    Avant l'exécution, vous devez modifier la section de configuration de base dans `webapp.py` :

    ```python
    # webapp.py
    MY_CALL = "YOUR_CALLSIGN"  # <-- Votre indicatif (essentiel)
    QRA_DEFAULT = "JN33"       # <-- Votre QRA par défaut
    # ... et configurer l'hôte/port du DX Cluster Telnet
    ```

4.  **Lancement**

    Lancez l'application en utilisant le script de démarrage (ou directement `python webapp.py`) :

    ```bash
    ./start.sh
    ```
    Accédez à l'interface via votre navigateur à l'adresse `http://127.0.0.1:8000` (ou le port configuré).

---

## 💻 Aperçu de l'Interface

![Aperçu du Dashboard](apercu.png)

---

## 🖱️ Utilisation de l'interface

### 1. Personnalisation de l'Affichage

* **Thèmes :** Cliquez sur le bouton `THEME: [Nom du Thème]` dans l'en-tête pour changer l'apparence.
* **Glisser-Déposer :** Cliquez et maintenez le clic sur l'en-tête d'un panneau (ex: `LIVE BANDS`, `WATCHLIST`) dans les colonnes gauche ou droite pour le déplacer et changer son ordre d'affichage. L'ordre est conservé au rechargement.

### 2. Saisie du QRA Locator

Dans la section **COMMAND DECK** :

1.  Entrez votre QRA Locator (ex: `JN33`, `JN33BB`).
2.  Cliquez sur **GO**.
3.  Le système centre les cartes sur votre position et met à jour tous les calculs de distance.

### 3. Watchlist

* Entrez un indicatif (ex: `K1TTT`) dans le champ **WATCHLIST** et cliquez sur **ADD**.
* Les spots pour cet indicatif seront mis en évidence et déclencheront une alerte vocale (si `VOICE: ON`).

### 4. Systèmes d'alerte

* **SURGE :** Une bannière apparaît si le nombre de spots sur une bande dépasse le seuil défini dans `webapp.py`.
* **OUVERTURE DETECTEE :** Le panneau *PROPAGATION HISTORY* alerte si l'activité sur les bandes magiques (12m, 10m, 6m) dépasse un seuil récent.

enjoy DX !

### Licence MIT

feel free to modify and share . Created for the Amateur Radio Communauty by Eric F1SMV à l'aide de GIMINI3 #codevibing vous pouvez me joindre via mon fil X
