# Multivers.log

Dépose des documents hétérogènes (PDF, CSV, notes, captures d'écran), pose une
question en langage naturel, obtiens une réponse sourcée avec citation cliquable
vers le passage exact.

Projet réalisé dans le cadre du hackathon *Le System Prompt Perdu*, sujet ORACLE.

## Quickstart

Prérequis : Python 3.12+, Node.js 18+, et une clé API Gemini gratuite. Sans clé,
voir la section "Lancer sans clé API" juste en dessous : l'interface est
consultable quand même.

L'installation des dépendances prend 2 à 5 minutes selon la connexion. Le back et
le front se lancent dans deux terminaux séparés.

### 1. Cloner

```bash
git clone https://github.com/sagalou/multivers.log.git
cd multivers.log
```

### 2. Back (terminal 1)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Ouvrir `.env` et renseigner `GEMINI_API_KEY` avec votre clé, obtenue gratuitement
sur [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
uvicorn app.main:app --reload --port 8000
```

Vérification : `http://localhost:8000/health` doit répondre `{"status": "ok"}`.

La racine `http://localhost:8000/` renvoie une 404, c'est normal : le back est une
API, pas un site. La documentation interactive est sur
`http://localhost:8000/docs`, et permet d'essayer chaque route depuis le
navigateur.

### 3. Front (terminal 2)

```bash
cd front
npm install
npm run dev
```

L'interface est sur `http://localhost:5173`. Le front fonctionne sans
configuration : `front/.env.example` documente les réglages disponibles, mais des
valeurs par défaut prennent le relais si aucun `.env` n'est présent.

## Lancer sans clé API

L'interface complète est consultable sans aucune clé, avec des données de
démonstration au format réel du contrat d'API.

```bash
cd front
cp .env.example .env
```

Mettre `VITE_USE_MOCK=true` dans `front/.env`, puis `npm run dev`. Vite redémarre
tout seul.

On y voit quatre documents avec les trois statuts possibles, dont un en erreur
avec son message, et une réponse accompagnée de deux citations sourcées. Un badge
orange "Données de démonstration" s'affiche en haut à droite, pour qu'on ne
confonde jamais ce mode avec le fonctionnement réel.

Le back démarre aussi sans clé : le dépôt et l'extraction de documents
fonctionnent, seule la réponse à une question est indisponible, avec un message
explicite plutôt qu'une erreur.

## Où sont les clés d'API

La clé `GEMINI_API_KEY` vit uniquement dans le fichier `.env` du **back**, jamais
exposée côté front, jamais commitée (voir `.gitignore`, qui couvre `.env`,
`*.env`, `.env.local` et `.env.*.local`). Le front ne parle qu'à notre propre API
sur `localhost:8000`, jamais directement à Gemini.

Attention au préfixe `VITE_` : Vite expose au navigateur toute variable qui le
porte. Aucun secret ne doit jamais être préfixé ainsi.

## Documentation

- [`API_CONTRACT.md`](./API_CONTRACT.md) — contrat front/back, formats relevés sur le serveur réel
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — schéma des couches et diagramme
- [`SPEC.md`](./SPEC.md) — problème, user stories, hors-scope, choix assumés
- [`REPARTITION.md`](./REPARTITION.md) — qui fait quoi, palier par palier
- [`BACKEND_QUICKSTART.md`](./BACKEND_QUICKSTART.md) — détail back

## Choix techniques

- **SQLite + FTS5** pour le stockage et la recherche plein texte, plutôt qu'une base vectorielle. Gratuit, zéro dépendance externe, zéro appel API supplémentaire pour indexer.
- **Tesseract (OCR local)** pour extraire le texte des captures d'écran, gratuit et local, cohérent avec le choix FTS5.
- **Gemini 3.6 Flash** comme LLM, clé API personnelle en offre gratuite, pas de coût pour le hackathon.
- **FastAPI** pour le back, **React + Vite** pour le front, sans librairie d'interface.
- **Vérification des citations** : avant affichage, le `chunk_id` cité doit exister en base et la citation doit se retrouver dans le texte du passage. Voir `app/verification.py`.
- **Pas d'authentification** : usage local mono-utilisateur pour ce hackathon.

## État d'avancement

| Palier | Statut |
|---|---|
| 1 · Cadrage | fait — SPEC.md, ARCHITECTURE.md, REPARTITION.md |
| 2 · Socle | fait — back et front démarrent, appel Gemini réel affiché à l'écran |
| 3 · Premier outil | en cours — extraction et SQLite/FTS5 branchés, OCR à finir |
| 4 · MVP | à faire — brancher `search_chunks` dans `/ask`, citations vérifiées |
| 5 · Durcissement | à faire |
| 6 · Livraison | à faire — AGENTS.md, JOURNAL.md, répétition démo |

## Limites connues

- `/ask` interroge le LLM sans contexte issu du corpus : la recherche documentaire est branchée en base mais pas encore dans la boucle de réponse. Les réponses ne citent donc aucune source pour l'instant.
- Pas de recherche sémantique en V1 : FTS5 travaille sur les mots, et peut manquer une réponse formulée très différemment du texte source.
- Une capture d'écran donne un seul passage indexable, l'image entière via OCR. La citation ne peut pas y surligner une portion précise comme dans un PDF.
- Pas de mise à jour incrémentale : déposer deux fois le même fichier crée deux documents distincts.
- Usage mono-utilisateur local, pas d'authentification ni de gestion de comptes.

## Structure du projet

```
multivers.log/
├── app/
│   ├── main.py           routes FastAPI
│   ├── db.py             SQLite, FTS5, accès aux passages
│   ├── extraction.py     lecture des documents, découpage en passages
│   └── verification.py   vérification des citations
├── front/
│   ├── src/App.jsx       la page unique
│   ├── src/api.js        appels au back, bascule mock
│   └── src/mock.json     données de démonstration
├── requirements.txt
├── .env.example
└── *.md                  documentation (voir section Documentation)
```
