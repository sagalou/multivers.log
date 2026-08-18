# Multivers.log

Dépose des documents hétérogènes (PDF, CSV, notes, captures d'écran), pose une question en langage naturel, obtiens une réponse sourcée avec citation cliquable vers le passage exact.

Projet réalisé dans le cadre du hackathon *Le System Prompt Perdu*, sujet ORACLE.

**État actuel : Palier 2 (Socle).** Le squelette tourne de bout en bout, avec un appel LLM réel (Gemini). La recherche dans les documents et les citations sourcées arrivent au palier 4.

## Quickstart (< 5 min)

### Prérequis

- Python 3.12+
- Node.js 18+
- Une clé API Gemini (gratuite sur [aistudio.google.com/apikey](https://aistudio.google.com/apikey))

### Back

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Ouvrir `.env` et renseigner `GEMINI_API_KEY` avec votre clé.

```bash
uvicorn app.main:app --reload --port 8000
```

L'API tourne sur `http://localhost:8000`. Documentation interactive : `http://localhost:8000/docs`.

Vérification rapide : `GET http://localhost:8000/health` doit répondre `{"status": "ok"}`.

### Front

```bash
cd front
npm install
npm run dev
```

Le front tourne sur `http://localhost:5173` (ou le port affiché par Vite).

## Où sont les clés d'API

La clé `GEMINI_API_KEY` vit uniquement dans le fichier `.env` du **back**, jamais exposée côté front, jamais commitée (voir `.gitignore`). Le front ne parle qu'à notre propre API (`localhost:8000`), jamais directement à Gemini.

## Architecture

Voir [`ARCHITECTURE.md`](./ARCHITECTURE.md) pour le schéma détaillé (diagramme mermaid) et la description de chaque couche : front, back FastAPI, pipeline d'ingestion, agent, stockage SQLite.

Le contrat d'API entre front et back est figé dans [`API_CONTRACT.md`](./API_CONTRACT.md).

## Choix techniques

- **SQLite + FTS5** pour le stockage et la recherche (à venir palier 3), plutôt qu'une base vectorielle (Chroma). Gratuit, zéro dépendance externe, zéro appel API supplémentaire.
- **Tesseract (OCR local)** pour extraire le texte des captures d'écran (à venir palier 3), gratuit et local, cohérent avec le choix FTS5.
- **Gemini 2.5 Flash** comme LLM, clé API personnelle (tier gratuit), pas de coût pour le hackathon.
- **FastAPI** pour le back, **React + Vite** pour le front.
- **Pas d'authentification** : un simple champ nom d'utilisateur suffit pour ce hackathon, pas de gestion de comptes.

Détail complet des choix et de ce qui a été écarté dans [`SPEC.md`](./SPEC.md).

## État d'avancement par palier

| Palier | Statut |
|---|---|
| 1 · Cadrage | ✅ SPEC.md, ARCHITECTURE.md |
| 2 · Socle | ✅ Back + front démarrent, appel LLM réel (`/ask`) |
| 3 · Premier outil | 🔲 Pipeline d'ingestion (PDF/CSV/notes/OCR) + SQLite/FTS5 |
| 4 · MVP | 🔲 Boucle complète question → search → LLM → réponse avec citation vérifiée |
| 5 · Durcissement | 🔲 Cas d'échec, bonus |
| 6 · Livraison | 🔲 AGENTS.md, JOURNAL.md, démo |

## Répartition du travail

Voir [`REPARTITION.md`](./REPARTITION.md) pour le détail palier par palier entre Sagal (back) et David (front).

## Limites connues

- Pas de recherche dans les documents pour l'instant : `/ask` interroge directement le LLM sans contexte issu d'un corpus (arrive au palier 3-4).
- Pas de recherche sémantique (embeddings) en V1 : la recherche par mots-clés (FTS5) peut manquer une réponse si la question est formulée très différemment du texte source.
- Une capture d'écran n'a qu'un seul passage indexable (toute l'image via OCR), la citation ne peut pas surligner une portion précise dedans comme pour un PDF.
- Usage mono-utilisateur local, pas d'authentification ni de gestion de comptes.
- Pas de mise à jour incrémentale d'un document déjà uploadé.

## Structure du projet

```
multivers.log/
├── app/
│   └── main.py
├── front/
│   └── ...
├── requirements.txt
├── .env.example
├── SPEC.md
├── ARCHITECTURE.md
├── API_CONTRACT.md
├── REPARTITION.md
├── AGENTS.md
├── JOURNAL.md
└── README.md
```