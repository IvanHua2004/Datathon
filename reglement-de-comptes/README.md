# Règlement de comptes

*Avant d'investir, faites passer votre idée en procès.*

Prototype pour le Datathon PolyFinances 2026 (AlphaForge AI). Un investisseur **fictif**
soumet une demande (« placer 20 % de mon portefeuille dans NVDA »). Un tribunal d'agents
examine si elle est cohérente avec le profil qu'il a déclaré, et explique son verdict avec
des pièces vérifiables.

> Simulation pédagogique. Aucune transaction réelle, aucun conseil financier personnalisé,
> aucune prédiction de rendement. Les profils et leurs montants sont fictifs.

## Démarrer

```bash
cd reglement-de-comptes
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run frontend/app.py
pytest -q backend/tests          # 7 tests
```

Les données sont lues par défaut dans `../Datathon2026/alphaforge_starter`. Pour un autre
emplacement : `export RDC_DATA_DIR=/chemin/vers/alphaforge_starter`.

L'application fonctionne tout de suite en mode **« Sans modèle »** : les plaidoiries sont
alors écrites par des gabarits. C'est le mode pour développer, et le filet de sécurité de la démo.

## Menu Angular

Lancez Streamlit avec la commande ci-dessus. Dans un deuxième terminal, depuis
le dossier `reglement-de-comptes` :

```bash
cd frontend
npm ci
npm start
```

Dans PowerShell sous Windows, utilisez `npm.cmd ci` et `npm.cmd start`.

Ouvrez `http://localhost:4200`. Le bouton **Débuter** ouvre l'application
Streamlit sur `http://localhost:8501`.

## Avec Docker

```bash
cd reglement-de-comptes
docker compose up --build        # puis ouvrir http://localhost:8501
docker compose run --rm tribunal pytest -q backend/tests     # les tests, dans le conteneur
```

Le jeu de départ est monté en lecture seule depuis `../Datathon2026/alphaforge_starter`. Pour
le mode Bedrock, exportez vos variables AWS avant `docker compose up`, ou placez-les dans un
fichier `.env` à côté de `docker-compose.yml` (ce fichier est ignoré par git, ne le publiez pas).

## Les rôles

| Rôle | Fichier | Ce qu'il fait |
| --- | --- | --- |
| Moteur de calcul | `backend/rdc/moteur.py` | Tous les chiffres. Aucun modèle de langage ne calcule. |
| Témoins | `backend/rdc/temoins.py` | `risque`, `diversification`, `valeurs`, `macro`. Chacun lit sa source et dépose des faits, sans opinion. |
| Greffier | `backend/rdc/greffier.py` | Numérote chaque déposition (P-01, P-02…) et signale tout chiffre cité qui n'est dans aucune pièce. |
| Défense, Procureur | `backend/rdc/agents.py` | Plaident pour et contre. En mode Bedrock, ils choisissent eux-mêmes les témoins à convoquer. |
| Juge | `backend/rdc/agents.py` + `backend/rdc/proces.py` | Le verdict vient d'une **règle** (`regle_verdict`). Le juge ne fait que le motiver. |
| La salle | `backend/rdc/proces.py` | Rejoue la règle en changeant une hypothèse à la fois : ce qui changerait le verdict. |

Quatre verdicts possibles : contraire à une contrainte déclarée, en tension avec le profil
déclaré, indécidable (information manquante), compatible avec le profil déclaré. Le tribunal
ne dit jamais quoi acheter : il montre la conséquence, et l'investisseur décide.

## Brancher AWS (compte d'équipe du Datathon)

Règles de l'atelier AWS du Datathon qui comptent ici :

- **Tout dans us-east-1** (Virginie du Nord). Mélanger les régions donne des erreurs qui
  ressemblent à des problèmes de permissions.
- **Pas d'instance EC2 avec un groupe de sécurité ouvert à Internet**, pas de bucket S3
  public. L'application tourne donc sur votre ordinateur (ou dans Docker) et appelle AWS.
- **Jamais d'identifiants AWS dans Git.** Ceux du Datathon sont temporaires et expirent :
  en cas de `ExpiredToken`, recopiez-en de nouveaux depuis Workshop Studio.

### 1. Identifiants

Dans Workshop Studio, menu de gauche, **Get AWS CLI credentials** : copiez le bloc
`export ...` dans votre terminal, puis vérifiez :

```bash
export AWS_REGION=us-east-1
aws sts get-caller-identity
```

### 2. Vérifier les modèles (une fois pour l'équipe, dans AWS CloudShell)

```bash
aws bedrock-runtime converse --region us-east-1 \
  --model-id global.anthropic.claude-sonnet-5 \
  --messages '[{"role":"user","content":[{"text":"Répondez exactement : prêt"}]}]' \
  --query 'output.message.content[?text].text' --output text
```

Le premier appel à un modèle Anthropic peut exiger un formulaire de première utilisation ;
en cas d'`AccessDeniedException`, attendez quelques minutes, réessayez, puis voyez un mentor.

### 3. Lancer le tribunal sur Bedrock

Modèle par défaut : `global.anthropic.claude-sonnet-5`, région `us-east-1`. Pour itérer à
faible coût pendant le développement :

```bash
export BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0   # facultatif
streamlit run app.py          # ou : docker compose up --build
```

Dans la barre latérale, choisissez **Amazon Bedrock (Strands)**. Si l'appel échoue,
l'application affiche l'erreur et rejoue le procès en mode gabarit.

Pièges connus : Claude Sonnet 5, Opus 5 et 5.5 refusent `temperature` (le code n'en passe
pas) ; Claude Sonnet 5.5, Haiku 5.5 et Fable ne sont pas disponibles dans les comptes du
Datathon ; l'erreur « on-demand throughput isn't supported » veut dire qu'il manque le
préfixe `global.` à l'identifiant du modèle.

### 4. Les données dans S3 (bucket privé)

```bash
BUCKET=reglement-de-comptes-$(aws sts get-caller-identity --query Account --output text)
aws s3 mb s3://$BUCKET --region us-east-1        # Block Public Access reste activé par défaut
aws s3 sync ../Datathon2026/alphaforge_starter s3://$BUCKET/alphaforge/ --exclude "*.py"
export RDC_S3_BUCKET=$BUCKET RDC_S3_PREFIX=alphaforge/
```

### 5. Pour aller plus loin (si le temps le permet)

AgentCore Observability ou Runtime pour montrer les traces d'exécution des agents à côté des
pièces du greffier. L'atelier rappelle que le jury n'évalue pas l'hébergement : faites
d'abord fonctionner le procès sur Bedrock.

## Données et traitements

- Source : jeu de départ des organisateurs (Yahoo Finance via yfinance, Banque du Canada,
  FRED), période du 2021-11-12 au 2026-11-12, extraction du 2026-11-13.
- Prix : `adj_close` (ajusté pour dividendes et fractionnements).
- Devise : tout est converti en dollars canadiens avec le taux USD/CAD quotidien.
- Calendrier : jours ouvrables du lundi au vendredi ; un prix manquant est remplacé par le
  dernier connu (5 jours au plus) ; les variations de fin de semaine des cryptoactifs sont
  comptées le lundi.
- Portefeuille : poids constants (rééquilibrage quotidien), sans frais ni impôt.
- Inflation : prise avec 45 jours de délai de publication (hypothèse), pour ne pas utiliser
  une valeur avant qu'elle soit connue.
- ESG : le jeu de départ n'en contient pas. Voir `backend/donnees_externes/LISEZMOI.md` ; la table
  `esg_preuves.csv` est livrée vide et se remplit à la main.

## Hypothèses de l'équipe (à valider et à documenter)

- Capital, budget de perte, plafonds et portefeuille de départ de chaque profil
  (`backend/rdc/profils.py`) : inventés. Seuls l'âge, l'horizon, le niveau de risque et les
  préférences viennent du cas officiel.
- Seuil « une position porte plus de 50 % du risque » (`SEUIL_PART_RISQUE`).
- Jours de crise = les 10 % pires jours du portefeuille actuel.

## Limites connues

- Cinq ans de données, une seule grande crise (2022) : la fourchette par rééchantillonnage
  ne peut pas inventer des crises jamais observées.
- Biais du survivant : les 31 actifs ont été choisis en 2026 parmi des titres aujourd'hui
  importants, donc le passé observé est flatteur (NVDA a fini par remonter).
- Les FNB ne sont pas décomposés : la concentration cachée (un titre déjà présent dans un
  FNB détenu) n'est pas mesurée.
- Le greffier vérifie que chaque chiffre cité existe dans une pièce, pas que la phrase qui
  l'entoure l'interprète correctement.
- Les autres comptes et actifs de l'investisseur sont inconnus.

## À faire

- [ ] Tester le mode Bedrock avec vos identifiants et ajuster les consignes des agents.
- [ ] Remplir `backend/donnees_externes/esg_preuves.csv` pour ENB, CNQ, XOM (procès de Mateo).
- [ ] Ajouter les dix premiers titres de SPY, QQQ et XIU pour mesurer la concentration cachée.
- [ ] Vidéo : Robert et NVDA, puis Amira et ETH, pour montrer deux situations contrastées.
