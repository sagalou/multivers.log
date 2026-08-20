# Multivers.log

Dépose des documents hétérogènes (PDF, CSV, notes, captures d'écran), pose une
question en langage naturel, obtiens une réponse sourcée avec citation cliquable
vers le passage exact.

Projet réalisé dans le cadre du hackathon *Le System Prompt Perdu*, sujet ORACLE.

## Quickstart

Prérequis : Python 3.12+, Node.js 18+, Tesseract, et une clé API NVIDIA gratuite. Sans clé,
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

L'OCR des captures d'écran passe par Tesseract, un programme système que `pip`
ne peut pas installer :

```bash
sudo apt install tesseract-ocr tesseract-ocr-fra
```

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Ouvrir `.env` et renseigner `NVIDIA_API_KEY` avec votre clé, obtenue gratuitement
sur [build.nvidia.com](https://build.nvidia.com).

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

La clé `NVIDIA_API_KEY` vit uniquement dans le fichier `.env` du **back**, jamais
exposée côté front, jamais commitée (voir `.gitignore`, qui couvre `.env`,
`*.env`, `.env.local` et `.env.*.local`). Le front ne parle qu'à notre propre API
sur `localhost:8000`, jamais directement au fournisseur du modèle.

Attention au préfixe `VITE_` : Vite expose au navigateur toute variable qui le
porte. Aucun secret ne doit jamais être préfixé ainsi.

Vérifié : la clé n'apparaît ni dans `front/src/`, ni dans le paquet construit et
livré au navigateur (`front/dist/`). Les seules variables qui y arrivent sont
`VITE_USE_MOCK`, `VITE_API_URL`, `VITE_MAX_FILE_MB` et les deux tarifs
d'affichage. Le front n'appelle aucun service externe, uniquement `localhost:8000`.

L'injection de prompt est traitée côté serveur : le prompt système refuse de
révéler ou de reformuler ses instructions, y compris si on lui affirme être en
mode debug ou d'ignorer ce qui précède.

## Documentation

- [`API_CONTRACT.md`](./API_CONTRACT.md) — contrat front/back, formats relevés sur le serveur réel
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — schéma des couches et diagramme
- [`SPEC.md`](./SPEC.md) — problème, user stories, hors-scope, choix assumés
- [`REPARTITION.md`](./REPARTITION.md) — qui fait quoi, palier par palier
- [`BACKEND_QUICKSTART.md`](./BACKEND_QUICKSTART.md) — détail back
- [`eval/cases.md`](./eval/cases.md) — jeu d'évaluation de l'agent et score actuel

## Évaluation et tests

Cinq cas d'évaluation sont décrits dans [`eval/cases.md`](./eval/cases.md), avec
pour chacun l'entrée, le résultat attendu et le résultat observé. Ils couvrent
les comportements critiques : sourcer une réponse, refuser d'inventer hors
corpus, agréger sur une question au pluriel, résister à une injection de prompt.

Les tests automatisés portent sur la recherche, dont le bug du pluriel trouvé au
palier 5 :

```bash
source venv/bin/activate
pytest tests/ -v
```

## Choix techniques

- **SQLite + FTS5** pour le stockage et la recherche plein texte, plutôt qu'une base vectorielle. Gratuit, zéro dépendance externe, zéro appel API supplémentaire pour indexer.
- **Tesseract (OCR local)** pour extraire le texte des captures d'écran, gratuit et local, cohérent avec le choix FTS5.
- **NVIDIA NIM** comme fournisseur de modèle, via son API compatible OpenAI. Changer de modèle, ou même de fournisseur, ne demande que trois lignes dans le `.env`.
- **FastAPI** pour le back, **React + Vite** pour le front, sans librairie d'interface.
- **Vérification des citations** : avant affichage, le `chunk_id` cité doit exister en base et la citation doit se retrouver dans le texte du passage. Voir `app/verification.py`.
- **Pas d'authentification** : usage local mono-utilisateur pour ce hackathon.

## État d'avancement

| Palier | Statut |
|---|---|
| 1 · Cadrage | validé — SPEC.md, ARCHITECTURE.md, REPARTITION.md |
| 2 · Socle | validé — back et front démarrent, appel LLM réel affiché à l'écran |
| 3 · Premier outil | validé — deux outils appelés par l'agent, trace visible, erreurs gérées |
| 4 · MVP | validé — parcours complet dans le navigateur, citations cliquables, rapport |
| 5 · Durcissement | en cours — délais maximum, limites de taille, jeu d'évaluation |
| 6 · Livraison | à faire — AGENTS.md, JOURNAL.md, répétition démo |

## Limites connues

- La recherche est sensible à la forme des mots : les pluriels sont traités, mais une faute de frappe ne trouvera rien. C'est la contrepartie assumée de FTS5 face à une recherche sémantique.
- Pas de recherche entre langues : une question posée en français ne trouvera pas un passage écrit uniquement en russe ou en chinois, sauf sur des termes identiques comme des chiffres ou des noms propres. La recherche compare des mots, pas des sens.
- Taille des fichiers limitée à 20 Mo. Au-delà, le document est refusé avec un message explicite, avant lecture en mémoire. La limite est appliquée deux fois : dans le navigateur pour répondre tout de suite, et sur le serveur qui reste la vraie garde.
- L'OCR d'une capture d'écran introduit ses propres erreurs de lecture, qui se retrouvent dans l'index. Un mot mal reconnu ne sera pas retrouvé.
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
├── eval/cases.md         jeu d'evaluation de l'agent
├── tests/test_search.py  tests de non-regression sur la recherche
├── requirements.txt
├── .env.example
└── *.md                  documentation (voir section Documentation)
```
