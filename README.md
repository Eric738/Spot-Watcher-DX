NEURAL DX CLUSTER v2.2 📡
Intelligent Dual-Spectrum DX Dashboard

Version Python License
🇫🇷 FRANÇAIS

Neural DX Cluster est une application de surveillance DX nouvelle génération conçue pour les radioamateurs exigeants. Contrairement aux clusters traditionnels qui affichent une liste de texte brute, Neural DX utilise une interface graphique "Dual Spectrum" pour séparer le trafic HF (ondes courtes) du trafic VHF/UHF/Espace.

Il analyse les spots en temps réel, détecte les ouvertures de propagation (Surges), et classe les stations par intérêt grâce à un algorithme de scoring intelligent.
✨ Fonctionnalités Clés

    🖥️ Dashboard Double Spectre :
        Zone HF (160m - 10m) : Carte mondiale, Top Liste DX, Graphiques de propagation ionosphérique.
        Zone VHF (6m - QO-100) : Carte locale/Europe, Top Liste Tropo/ES/EME, Graphiques d'activité spécifiques.
    🧠 Algorithme de Scoring IA : Le système note chaque spot (0-100) en fonction de la rareté du préfixe, du mode, de la bande et des commentaires (ex: "UP", "SPLIT").
    ⚠️ Détection de Surge (Ouvertures) : Analyse statistique glissante pour détecter les pics d'activité anormaux sur une bande (ex: ouverture soudaine du 10m ou 6m).
    🎙️ Alertes Vocales & Watchlist : Synthèse vocale pour annoncer les ouvertures et surveillance prioritaire de vos indicatifs favoris (amis, expéditions).
    🎨 Interface Personnalisable :
        Thèmes visuels : Cyber, Matrix, Amber, Neon.
        Filtres dynamiques : Par Bande et par Mode (CW, SSB, FT8, FM).
    🗺️ Cartographie Live : Affichage des spots sur cartes interactives (Leaflet) avec distinction jour/nuit implicite via le flux.

🛠️ Installation

    Prérequis : Python 3.x installé sur votre machine.
    Installation des dépendances :

pip install flask feedparser

Configuration :
Ouvrez le fichier webapp.py et modifiez la variable MY_CALL avec votre indicatif :

    MY_CALL = "VOTRE_INDICATIF"

![Apercu du Dashboard](capture.png)

🚀 Démarrage

    Lancez l'application :

    python webapp.py

    Ouvrez votre navigateur web et allez à l'adresse :
    http://localhost:8000

Le système va automatiquement télécharger la base de données pays (cty.dat), se connecter aux clusters Telnet et commencer à peupler les cartes.


📜 License

MIT License - Feel free to modify and share.
Created for the Amateur Radio Community pensé par F1SMV, réalisé par gimini3 #codevibing joignable sur mon fil twitter