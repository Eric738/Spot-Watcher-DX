# 📡 Spot Watcher DX Ultimate

![Version](https://img.shields.io/badge/version-v7.1-blue) ![Python](https://img.shields.io/badge/python-3.x-yellow) ![License](https://img.shields.io/badge/license-MIT-green)

**Spot Watcher DX** est une application web autonome conçue pour les **Radioamateurs**. Elle se connecte au réseau DX Cluster mondial via Telnet, analyse les spots en temps réel, et les affiche sur un tableau de bord moderne et réactif.

Conçu pour fonctionner 24h/24 sur un **Raspberry Pi**, c'est l'outil idéal pour surveiller les ouvertures de propagation, les expéditions DX (DXpeditions) et l'activité sur le satellite QO-100.


![Aperçu du logiciel](apercu.png)


## ✨ Fonctionnalités

*   **🌐 Carte du Monde en Temps Réel** : Visualisation géographique des contacts (Greyline, position).
*   **📊 Analyse de Propagation** : Graphique d'activité par bande (160m à QO-100).
*   **📡 Support Multi-Bandes** : HF, VHF (6m, 2m), UHF (70cm) et Satellite QO-100.
*   **🔄 Redondance Cluster** : Connexion automatique à un serveur de secours (ex: F5LEN) si le principal tombe.
*   **🎯 Watchlist Intelligente** : Alertes visuelles et sonores (badges dorés) pour les indicatifs recherchés.
*   **☀️ Données Solaires** : Ticker RSS intégré avec flux NOAA (SFI, A-Index, K-Index).
*   **🎨 Thèmes Visuels** : 6 thèmes inclus (Matrix, Cyberpunk, Océan, Ambre, Light, Default).
*   **📱 Responsive** : Fonctionne sur PC, Tablette et Mobile.

## 🛠️ Matériel Recommandé

Cette application est optimisée pour :
*   **Raspberry Pi** (3B+, 4 ou 5 recommandés).
*   Tout serveur Linux (Ubuntu, Debian) ou même Windows.

## 🚀 Installation

### 1. Prérequis
Assurez-vous d'avoir Python 3 installé :
```bash
sudo apt update
sudo apt install python3 python3-pip

Pour cloner le projet
git clone https://github.com/ERIC738/SpotWatcherDX.git
cd SpotWatcherDX

installer les dependances
pip3 install flask

Ouvrez le fichier webapp.py et modifiez la ligne suivante avec votre indicatif :
MY_CALL = "VOTRE_INDICATIF"  # Ex: F4HZN

demarrez l'application 
python3 webapp.py

accedez à l'interface par 
http://ADRESSE_IP_DU_PI:8000

Démarrage automatique (Systemd)
Pour que l'application se lance au démarrage du Raspberry Pi :

Créer le service : sudo nano /etc/systemd/system/dxwatcher.service
Coller le contenu suivant (adapter le chemin) :
[Unit]
Description=DX Watcher Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/SpotWatcherDX
ExecStart=/usr/bin/python3 /home/pi/SpotWatcherDX/webapp.py
Restart=always

[Install]
WantedBy=multi-user.target

Activer : sudo systemctl enable dxwatcher && sudo systemctl start dxwatcher

🤝 Contribution
vous pouvez me joindre sur f1smv.eric at gmail.com

📜 Licence
Ce projet est sous licence MIT. Pensé par Eric F1SMV réalisé par GIMINI3 .Libre à vous de le modifier et de le partager.
