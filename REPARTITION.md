# REPARTITION.md — Multivers.log

Répartition des tâches par palier. L'alternance à l'oral est obligatoire à chaque checkpoint : ce n'est pas parce que tu codes une partie que c'est toi qui la présenteras forcément.

## Sagal — Back

| Palier | Tâches |
|---|---|
| 1 · Cadrage | Rédaction SPEC.md (schéma d'extraction, outils, hors-scope) ; schéma SQLite (documents, chunks, chunks_fts) |
| 2 · Socle | Setup FastAPI, endpoints `/upload` `/ask` `/report` (squelette) ; connexion SQLite + FTS5 |
| 3 · Premier outil | Pipeline d'ingestion complet (PDF, CSV, notes, OCR captures via Tesseract) ; outil `search()` branché à l'agent |
| 4 · MVP | Boucle question → search → LLM → réponse avec citation |
| 5 · Durcissement | Gestion des cas d'échec back (document illisible, question sans réponse) ; validation structurée des extractions ; bonus si temps (embeddings Chroma, détection contradictions) |
| 6 · Livraison | AGENTS.md (prompts système, outils, boucle) ; relecture README section technique |

## David — Front

| Palier | Tâches |
|---|---|
| 1 · Cadrage | Schéma d'architecture (avec Sagal) ; happy path démo (6 étapes) |
| 2 · Socle | Setup front (framework à définir), page basique reliée au back |
| 3 · Premier outil | Interface d'upload multi-fichiers avec retour de statut (en cours/traité/erreur) |
| 4 · MVP | Interface de chat/question ; affichage réponse + citation cliquable qui ouvre le passage source ; vérification citation (chunk_id existant en base avant affichage) |
| 5 · Durcissement | Affichage des cas d'échec côté utilisateur (message clair si document illisible ou pas de réponse trouvée) ; polish UI ; bonus si temps (export rapport PDF/Word) |
| 6 · Livraison | README.md (quickstart <5min, archi, limites connues) ; répétition démo |

## Zone de collaboration (les deux)

- **Question sans réponse dans le corpus** : Sagal détecte côté agent, David affiche proprement côté UI. À synchroniser ensemble avant le palier 4.
- **JOURNAL.md** : 5 entrées minimum, à remplir à deux au fil de l'eau (pas le dernier soir).
- **Démo scriptée** : préparée et répétée à deux, alternance qui parle à chaque partie.
- **`.gitignore` / `.env.example`** : à vérifier ensemble avant le premier commit de code (palier 2).

## Rappel alternance à l'oral

| Checkpoint | Qui explique (à tirer au sort réellement, ceci est indicatif) |
|---|---|
| Palier 1 | Sagal |
| Palier 2 | David |
| Palier 3 | Sagal |
| Palier 4 | David |
| Palier 5 | Sagal |
| Palier 6 | David |

Le formateur désigne qui répond au hasard, donc les deux doivent pouvoir expliquer l'intégralité du projet, pas seulement leur partie.