# Backend — Quickstart

## Installation

```bash
python -m venv venv
source venv/bin/activate  # sous WSL/Linux
pip install -r requirements.txt
```

## Lancer le serveur

```bash
uvicorn app.main:app --reload --port 8000
```

Le serveur tourne sur `http://localhost:8000`.

- Documentation interactive auto-générée : `http://localhost:8000/docs`
- Vérifier que ça tourne : `http://localhost:8000/health`

## État actuel (palier 2 — Socle)

Les 4 endpoints du contrat (`/upload`, `/documents`, `/ask`, `/report`) répondent déjà
avec le bon format JSON (voir `API_CONTRACT.md`), mais avec des données factices.
David peut brancher son front dessus dès maintenant.

Prochaines étapes (paliers 3-4) :
- Palier 3 : brancher le vrai pipeline d'ingestion (extraction PDF/CSV/notes + OCR Tesseract) et la table SQLite + FTS5
- Palier 4 : brancher l'agent réel (search FTS5 -> contexte -> appel Gemini -> réponse avec citation vérifiée)