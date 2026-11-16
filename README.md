# Règlement de comptes

**Êtes-vous vraiment l’investisseur que vous pensez être ?**

À travers des débats financiers interactifs entre deux avocats virtuels, prenez des décisions, rendez vos verdicts et découvrez si vos choix reflètent réellement le profil d’investisseur que vous pensiez avoir.

Projet réalisé dans le cadre du **Datathon PolyFinances 2026 (AlphaForge AI)**.

## 🐳 Guide Docker

Ce guide détaille pas à pas comment installer **Docker**, configurer l'environnement et lancer le projet **Règlement de Comptes** en conteneur sur votre machine (Windows, macOS ou Linux).

---

## 📑 Sommaire
1. [Prérequis & Installation de Docker](#1-prérequis--installation-de-docker)
2. [Lancement Rapide (En 1 commande)](#2-lancement-rapide-en-1-commande)
3. [Configuration des Environnements (.env & AWS Bedrock)](#3-configuration-des-environnements-env--aws-bedrock)
4. [Architecture des Conteneurs Locaux](#4-architecture-des-conteneurs-locaux)
5. [Commandes Utiles au Quotidien](#5-commandes-utiles-au-quotidien)
6. [Image Unifiée de Production (Dockerfile.aws)](#6-image-unifiée-de-production-dockerfileaws)
7. [Dépannage & FAQ](#7-dépannage--faq)

---

## 1. Prérequis & Installation de Docker

### 🪟 Sur Windows 10 / 11 (Recommandé avec WSL2)
1. **Téléchargez Docker Desktop pour Windows :**  
   👉 [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Lors de l'installation, assurez-vous de cocher l'option **« Use WSL 2 instead of Hyper-V »**.
3. Redémarrez votre ordinateur si demandé.
4. Lancez **Docker Desktop** depuis le menu Démarrer et attendez que l'icône de la baleine dans la barre des tâches indique que le moteur est en cours d'exécution (*Docker Desktop is running*).
5. Vérifiez l'installation dans un terminal PowerShell :
   ```powershell
   docker --version
   docker compose version
   ```

### 🍏 Sur macOS (Apple Silicon M1/M2/M3/M4 ou Intel)
1. Téléchargez et installez **Docker Desktop pour Mac** depuis le site officiel.
2. Déplacez Docker dans votre dossier Applications et lancez-le.
3. Vérifiez dans votre Terminal :
   ```bash
   docker --version
   docker compose version
   ```

### 🐧 Sur Linux (Ubuntu / Debian / Fedora)
```bash
# Installation via le script officiel Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
# Permettre d'utiliser Docker sans sudo
sudo usermod -aG docker $USER
newgrp docker
```

---

## 2. Lancement Rapide (En 1 commande)

Placez-vous dans le dossier racine du projet `reglement-de-comptes` :

```bash
docker compose up --build
```

> 💡 **Ce qui se passe :**
> - Docker compile l'image de l'API Python FastAPI (`reglement-de-comptes-api`).
> - Docker compile l'interface Angular 19+ avec Node.js 22 et la sert via Nginx (`reglement-de-comptes-interface`).
> - Nginx relaie automatiquement les requêtes `/api/` vers FastAPI.
> - **Aucune installation de Node.js, Python ou Nginx n'est requise sur votre ordinateur.**

### 🌐 Accéder à l'application
Une fois les conteneurs démarrés :
- 🏠 **Page d'accueil & Menu :** [http://localhost:4200](http://localhost:4200)
- ⚖️ **Accès direct au Tribunal :** [http://localhost:4200/tribunal](http://localhost:4200/tribunal)
- 🤺 **Mode Duel d'actifs :** [http://localhost:4200/duel](http://localhost:4200/duel)
- 📚 **Documentation Swagger de l'API :** [http://localhost:4200/api/docs](http://localhost:4200/api/docs)

*Note de sécurité : Seul le port 4200 est ouvert sur votre boucle locale (`127.0.0.1`), l'application n'est pas exposée sur votre réseau Wi-Fi public.*

Pour arrêter l'application, appuyez sur `Ctrl + C` dans le terminal, ou lancez :
```bash
docker compose down
```

---

## 3. Configuration des Environnements (.env & AWS Bedrock)

Le projet dispose de deux modes de fonctionnement :

### Mode A : Mode Déterministe / Hors-Ligne (Sans clé AWS)
Par défaut, si aucun identifiant AWS n'est fourni, l'application fonctionne immédiatement en **Mode Gabarit**. Les calculs financiers réels (1 304 séances quotidiennes en CAD), les pièces à conviction scellées `[P-01]` à `[P-06]`, l'audit anti-hallucination du Greffier et le verdict du Juge fonctionnent **à 100 % hors-ligne**.

### Mode B : Mode Connecté Amazon Bedrock (Claude Sonnet 5)
Pour activer les agents cognitifs en langage naturel (Me Vigor, Me Austère) sur **Amazon Bedrock**, créez un fichier `.env` à la racine de `reglement-de-comptes` (à côté de `docker-compose.yml`) :

```env
# Configuration AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=VOTRE_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=VOTRE_SECRET_KEY
AWS_SESSION_TOKEN=VOTRE_SESSION_TOKEN_TEMPORAIRE
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-5

# Données & Datalake S3 (optionnel)
RDC_S3_BUCKET=reglement-de-comptes-alphaforge
RDC_S3_PREFIX=alphaforge/
```

Relancez ensuite les conteneurs :
```bash
docker compose up --build
```

> ⚠️ **Sécurité :** Le fichier `.env` est déjà inscrit dans le fichier `.gitignore`. **Ne le committez jamais dans Git.**

---

## 4. Architecture des Conteneurs Locaux

Le fichier `docker-compose.yml` orchestre deux services isolés au sein d'un réseau interne Docker :

```
                        NAVIGATEUR WEB
                              │
                    http://localhost:4200
                              │
                    ┌─────────▼─────────┐
                    │  Service Interface│  Port 4200 -> 80 (Nginx)
                    │  (Angular 19 Dist)│  Sert la SPA
                    └─────────┬─────────┘
                              │
                    Relais proxy interne
                    location /api/ -> http://api:8000
                              │
                    ┌─────────▼─────────┐
                    │    Service API    │  Port 8000 interne (Expose)
                    │ (FastAPI/Python)  │  Calculs financiers
                    └─────────┬─────────┘  Agents Bedrock & Greffier
                              │
                     Volume de données /data
                     (1 304 séances quotidiennes)
```

1. **`interface` (Nginx + Angular) :**
   - Sert l'application compilée avec un routage HTML5 propre (`try_files $uri /index.html`).
   - Relaie les appels `/api/*` directement vers le conteneur `api:8000` avec un `proxy_read_timeout` de 600s pour permettre aux agents Bedrock de débattre sereinement.
2. **`api` (FastAPI + Python 3.12) :**
   - Exécute le moteur financier `rdc`, les 44 tests, le simulateur de stress et l'orchestration multi-agents.
   - Embarque un healthcheck natif validant l'intégrité du service toutes les 30 secondes.

---

## 5. Commandes Utiles au Quotidien

### 🧪 Exécuter les tests Pytest dans le conteneur
Vous pouvez lancer la suite de tests automatisés directement dans l'environnement conteneurisé sans rien installer sur votre machine :

```bash
docker compose run --rm api pytest -q backend/tests
```

### 📜 Consulter les logs en direct
```bash
# Tous les logs
docker compose logs -f

# Uniquement les logs de l'API Python
docker compose logs -f api

# Uniquement les logs Nginx de l'interface
docker compose logs -f interface
```

### 🔄 Reconstruire complètement sans cache
En cas de modification majeure des dépendances (`package.json` ou `requirements.txt`) :
```bash
docker compose build --no-cache
docker compose up
```

### 🧹 Nettoyer les conteneurs et volumes résiduels
```bash
docker compose down --volumes --remove-orphans
```

---

## 6. Image Unifiée de Production (Dockerfile.aws)

En plus de l'environnement de développement multi-conteneurs, le projet dispose d'un **`Dockerfile.aws` unifié**.  
Cette image multi-stage regroupe à la fois l'application Angular compilée et le backend FastAPI dans un conteneur unique allégé sous utilisateur non-root, optimisé pour **AWS ECS Fargate**.

### Pour tester l'image de production AWS localement :
```bash
# 1. Construction de l'image de production
docker build -f Dockerfile.aws -t reglement-prod-aws .

# 2. Exécution locale sur le port 8501 (conforme AWS ECS)
docker run --rm -p 8501:8501 --env-file .env reglement-prod-aws
```
Ouvrez ensuite [http://localhost:8501](http://localhost:8501) dans votre navigateur.

---

## 7. Dépannage & FAQ

### ❌ Erreur : `port 4200 is already allocated`
Un autre processus (ex: un ancien `ng serve` local) occupe déjà le port 4200.
- **Solution sous Windows (PowerShell) :**
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 4200).OwningProcess | Stop-Process -Force
  ```
- **Ou modifiez le port dans `docker-compose.yml` :**
  ```yaml
  ports:
    - "127.0.0.1:4201:80"  # Accédez ensuite à http://localhost:4201
  ```

### ❌ Erreur : `Cannot connect to the Docker daemon`
Docker Desktop n'est pas démarré.  
- Lancez **Docker Desktop** et patientez jusqu'à ce que l'indicateur d'état soit vert.

### ❌ Erreur : `ExpiredToken` ou `AccessDeniedException` avec Bedrock
Les jetons temporaires fournis par AWS Workshop Studio expirent régulièrement.  
1. Rendez-vous sur Workshop Studio et copiez de nouveaux identifiants (*Get AWS CLI credentials*).
2. Mettez à jour votre fichier `.env`.
3. Relancez `docker compose up`.  
*(Si vous n'avez pas de nouveaux jetons immédiatement, supprimez les variables AWS du `.env` : l'application basculera automatiquement en mode Gabarit sans planter).*

### ❌ Erreur de montage du volume `/data`
Vérifiez que le dossier `data` ou `../Datathon2026/alphaforge_starter` existe bien. Si votre dossier de données est ailleurs, ajustez le volume dans `docker-compose.yml` :
```yaml
volumes:
  - ./votre_chemin_de_donnees:/data:ro
```
