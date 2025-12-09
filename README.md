NEURAL DX WATCHER V4.2
🛰️ Introduction

NEURAL DX WATCHER V4.2 est une application web conçue pour les radioamateurs (DXers). Elle offre un tableau de bord en temps réel pour suivre les spots DX (stations lointaines) sur les bandes HF et VHF/UHF, centralisant les alertes, les statistiques, l'historique d'activité et la cartographie.

Cette version 4.2 apporte des améliorations majeures en termes de performances, de graphiques historiques et intègre des contrôles avancés de la synthèse vocale pour ne manquer aucune opportunité DX.
✨ Fonctionnalités Principales

    Temps Réel: Affichage des spots DX en temps réel sur les bandes HF et VHF/UHF.

    Synthèse Vocale Avancée (Nouveau): Annonce sonore des nouveaux spots, avec possibilité d'activer/désactiver la voix et de filtrer les alertes par distance (ex: DX > 10000 km) par rapport à votre QRA.

    Historique 30min/12h: Graphique d'activité des bandes sur une fenêtre de 12 heures, avec une granularité de 30 minutes, idéal pour suivre les ouvertures.

    Cartographie Intégrée: Deux cartes distinctes (HF et VHF/UHF) affichant la localisation des spots DX par rapport à votre QTH.

    Watchlist: Suivi prioritaire des indicatifs d'appel (Callsigns) importants.

    Surge Alerts: Détection des pics d'activité inhabituels sur une bande donnée.

    Panneaux Personnalisables: Fonctionnalité Drag & Drop pour organiser les panneaux selon vos préférences (l'ordre est sauvegardé).

    Thèmes: Bascule simple entre les mode SoftTech , Matrix, Dark.

📸 Aperçu de l'Interface

![Apercu du Dashboard](apercu.png)

⚙️ Installation & Démarrage

Ce projet est basé sur Python (Flask) pour le backend et HTML/CSS/JavaScript (Leaflet, Chart.js) pour l'interface client.
Prérequis

    Python 3.x

    Accès Internet

    Bibliothèques Python listées dans requirements.txt (ou installez manuellement flask, telnetlib, requests, feedparser, etc.)

Étapes de Démarrage

    Clonez le dépôt :
    Bash

git clone gh repo clone Eric738/Spot-Watcher-DX
cd neural-dx-watcher-v4

Installez les dépendances Python :
Bash

pip install -r requirements.txt

Configurez votre QRA : Ouvrez webapp.py et modifiez les variables de configuration au début du fichier, notamment MY_CALL et DEFAULT_QRA.

Lancez l'application :
Bash

    python webapp.py

    L'application sera accessible via votre navigateur à l'adresse par défaut : http://127.0.0.1:8000 (ou le port configuré).

🛠️ Configuration (webapp.py)

Les principaux paramètres de l'application se trouvent au début du fichier webapp.py :
Variable	Description	Valeur par Défaut
MY_CALL	Votre indicatif d'appel.	F1SMV
DEFAULT_QRA	Votre localisateur QRA (ex: JN23).	JN23
SPD_THRESHOLD	Seuil du Score de Priorité DX pour les alertes (spots en rouge).	70
SPOT_LIFETIME	Durée pendant laquelle un spot reste actif (en secondes).	1800 (30 minutes)

🎙️ Utilisation du Filtre Vocal de Distance

Le filtre vocal est accessible dans l'en-tête, à côté des indicateurs de temps et du bouton 🔊 VOICE ON/OFF.

Ce filtre permet de n'entendre que les annonces vocales pour les spots correspondant à la plage de distance sélectionnée par rapport à votre QRA :

    ALL: Annonce tous les spots (par défaut).

    < 5000 km: Annonce uniquement les spots de proximité (DX moins lointain).

    5000 - 10000 km: Annonce les DX à moyenne distance.

    > 10000 km: Annonce uniquement les DX "Long Haul" (DX difficiles).

Feel free to modify and share. Created by F1SMV Eric for Ham Radio Communauty with #GIMINI3.