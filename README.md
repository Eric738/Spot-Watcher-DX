# 📡 Radio Spot Watcher DX — v6.2

**DX Cluster Dashboard & Advanced Radio Analysis Engine**

Application web locale de surveillance DX et d’analyse radio destinée aux radioamateurs exigeants.  
Conçue pour **observer**, **comprendre** et **prendre du recul** — pas pour faire du bruit visuel.

---

## 🧭 Présentation générale

**Radio Spot Watcher DX** est une application web locale qui :

- se connecte à un ou plusieurs **DX Clusters (Telnet)**
- affiche les **spots en temps réel** (HF / VHF / UHF)
- intègre les **indices solaires** (SFI, A, Kp…)
- conserve une **mémoire exploitable** de l’activité
- propose **plusieurs niveaux de lecture**, du live à l’analyse stratégique

> L’objectif n’est pas de voir beaucoup,  
> mais de **voir juste**.

---

## 🖥️ Pages principales

### 1️⃣ Page **Index** — Temps réel & suivi opérateur

Page d’observation immédiate.

Elle affiche :
- le flux de spots en direct
- les bandes actives
- les DX recherchés (*wanted*)
- les indices solaires
- les signaux de **surge** d’activité

👉 **Objectif : savoir ce qui se passe maintenant.**

---

### 📡 Pavé **WATCHLIST · Tracking**

Fonction introduite pour répondre à un besoin simple :

> *« Je n’étais pas devant l’écran : qu’ai-je raté ? »*

- basé sur la watchlist
- exploite un historique en mémoire
- affiche les derniers spots par indicatif

Philosophie :
- ❌ pas un log brut  
- ❌ pas un dump massif  
- ✅ un outil de rattrapage  
- ✅ pensé pour l’opérateur humain  

---

### 2️⃣ Page **Map** — Carte d’observation (micro-lecture)

Carte classique des **spots individuels** :

- chaque point = **une station**
- représentation géographique immédiate
- vision instantanée

👉 **Objectif : voir où ça se passe.**

La page **Map** est un **outil d’exécution**.

---

### 3️⃣ Page **Analyse** — META ANALYSE différée

Outil volontairement **non temps réel**, basé sur l’analyse du log applicatif.

👉 **Outil de recul**, pas un gadget.

---

### 4️⃣ Page **World** — Forecast & Anomalies

La page **World** est **fondamentalement différente** de la page Map.

| Page | Nature | Question |
|---|---|---|
| Map | Observation brute | Qui est actif maintenant ? |
| World | Analyse interprétée | Où la propagation est anormalement favorable ? |

- affichage de **zones**, pas de stations
- clustering spatio-temporel
- filtrage du bruit
- rafraîchissement contrôlé

👉 **World décide, Map exécute.**

### 5️⃣ « Briefing » qui se met a jour toutes les 12 heures, reprenant les infos dx essentielles et surtout maintenant 
la possibilite d'ajouter automatiquement les call (si vous voulez) dans la "watching list" de la page Index. 
Donc vous ne raterez aucune expedition car des que le call d'un expedition sera spoté il s'affichera en jaune  
---
📸 Aperçu

![Apercu du Dashboard](apercu.png)

## ⚙️ Architecture technique

- Backend : Python / Flask  
- Frontend : HTML / CSS / JavaScript  
- Cluster : Telnet DX Cluster  
- Analyse : scripts Python dédiés  
- Stockage : mémoire + JSON locaux  

Aucune dépendance cloud.

---

## 🗂️ Historique des versions

### v6.2 ajout sur option des calls dans la watching list du dashboard et rajout du nouveau mode FT2

### v6.1 nouvelle page « briefing dxpeditions » et modification des cartes de la page index.html

### v6.0 — Release stable
- Finalisation de la page **World**
- Séparation claire Map / World
- Clustering stabilisé
- Rafraîchissement automatique
- UX clarifiée
- Sauvegarde état utilisateur

> Passage de **v5.7 à v6.0**  
> dû à plusieurs versions d’essai non publiées.

### v5.7 — Versions de travail
- prototypes World
- ajustements de scoring
- corrections structurelles

### v5.6
- Introduction de World (expérimentale)
- Pavé WATCHLIST · Tracking

### v5.2
- Introduction de la META ANALYSE

---

## 👤 Auteur

Développé par **F1SMV – Eric**  
avec l’assistance de ChatGPT 5.2 et Gemini  
au service de la communauté radioamateur.
vous pouvez me contacter via X
