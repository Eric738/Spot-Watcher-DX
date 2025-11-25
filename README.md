# 📡 DX Watcher Ultimate - Neural AI Edition (v1.2)VHF/UHF

**DX Watcher Ultimate** est un agrégateur de DX Cluster local, multicanal et intelligent. Contrairement aux clusters traditionnels qui se contentent d'afficher une liste chronologique brute, ce logiciel intègre un moteur d'analyse algorithmique (**Neural AI Engine**) qui note, classe et priorise les spots radioamateurs en temps réel.

![Version](https://img.shields.io/badge/Version-Neural_AI_v1.0-blue) ![Python](https://img.shields.io/badge/Python-3.x-yellow) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 🌍 The "Neural Ranking" Revolution (English)

For the first time in amateur radio software, DX Watcher implements a **Live Neural Ranking System**. Instead of scrolling through hundreds of irrelevant spots, the software analyzes the metadata of each incoming signal (Callsign rarity, comments like "UP/SPLIT", band propagation, and mode) to assign a **Real-Time Interest Score (0-100)**.

This introduces a paradigm shift: **Don't just watch the spots, watch the Score.** The system automatically highlights "Hot" DX stations that you might have missed in the noise of a standard cluster. It acts as a smart co-pilot, filtering the mundane to reveal the extraordinary.

---
![Aperçu du Dashboard](capture.png)

## 🧠 Le Moteur Neural : Comment ça marche ?

Le cœur du système repose sur la fonction `calculate_ai_score` située dans `webapp.py`. Ce n'est pas une simple liste de filtres, mais un système de **scoring pondéré**.

Chaque spot commence avec un score de base et gagne (ou perd) des points selon des critères précis :

1.  **Analyse du Callsign (Rareté)** : Le moteur compare le préfixe à une base de données de "Most Wanted" (ex: P5, 3Y, FT8...). Si c'est rare, le score explose (+50 points).
2.  **Analyse Sémantique (Commentaires)** : L'IA lit les commentaires laissés par les spotters.
    *   Détection de `UP`, `SPLIT`, `LISTEN` : Indique une station DX très demandée (+15 points).
    *   Détection de `PIRATE` : Le score tombe immédiatement à 0.
3.  **Contexte de Bande et Mode** :
    *   Bonus pour les bandes "magiques" (6m, 10m, 12m, 160m).
    *   Bonus pour le mode CW (selon configuration).

### 🚀 Enrichir l'IA (Personnalisation)

C'est ici que la magie opère. Vous pouvez rendre l'IA plus "intelligente" en modifiant la fonction `calculate_ai_score` dans le fichier Python.

**Exemple 1 : Prioriser le IOTA (Islands On The Air)**
Ajoutez simplement cette condition pour scanner les commentaires :
```python
if 'IOTA' in comment:
    score += 20  # Boost significatif pour les chasseurs d'îles
if 'POTA' in comment or 'SOTA' in comment:
    score += 10
if mode == 'FT8':
    score -= 30  # Pénalise le FT8 pour faire remonter la SSB
L'objectif est de faire évoluer ce moteur pour qu'il "pense" comme l'opérateur qui l'utilise.

✨ Fonctionnalités Clés
Multi-Cluster Aggregation : Connexion simultanée à 3 serveurs Telnet (personnalisables) pour ne rien rater.
Neural Ranking Table : Un Top 10 dynamique des stations les plus intéressantes du moment, triées par score IA.
Cartographie Live : Affichage des spots sur une carte interactive (Leaflet) avec code couleur selon le score (Vert = Standard, Rouge = Hot DX).
Graphique de Propagation : Histogramme temps réel de l'activité par bande avec couleurs fixes standardisées.
Watchlist Intelligente : Ajoutez un indicatif (ex: TR8) et le système le surlignera en Or et déclenchera une alerte.
Synthèse Vocale (TTS) : Annonce vocale automatique des spots "Hot" ou de la Watchlist ("Alerte DX ! T88AR sur 20 mètres").

🛠️ Installation et Démarrage
Prérequis
Python 3.x installé.
Bibliothèques Python : flask (Le reste est standard).
Installation
Clonez ou téléchargez ce dossier.
Installez les dépendances :
pip install flask feedparser
(Note : feedparser est optionnel pour le ticker solaire, le code gère son absence)
Lancement
Lancez le script principal :
python webapp.py
Le moteur va démarrer, charger la base de données pays (cty.dat) et se connecter aux clusters.
Ouvrez votre navigateur à l'adresse : http://localhost:8000

📝 Configuration
Ouvrez webapp.py pour modifier :

MY_CALL : Votre indicatif.
CLUSTERS : La liste des serveurs Telnet.
RARE_PREFIXES : La liste des pays que VOUS considérez comme rares pour le calcul du score.
pense par Eric F1SMV realise par GIMINI 3 
