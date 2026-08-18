# SPEC.md — ORACLE

## Le problème (5 lignes)

Un chercheur ou une équipe de terrain accumule des documents hétérogènes sur un site archéologique ou patrimonial : rapports de fouille en PDF, tableurs de mesures en CSV, notes de terrain, captures d'écran de plans ou de relevés. Ces documents s'accumulent sans être interrogeables entre eux. ORACLE ingère ce fonds documentaire, en extrait une structure exploitable, et permet de poser des questions en langage naturel sur l'ensemble du corpus. Chaque réponse est accompagnée d'une citation source cliquable qui ouvre le passage exact d'origine. L'utilisateur peut aussi demander un rapport de synthèse sur le corpus.

## User stories (3 max)

1. En tant qu'utilisateur, je dépose entre 10 et 50 documents hétérogènes (PDF, CSV, notes, captures) et je vois leur statut de traitement (en cours, traité, erreur).
2. En tant qu'utilisateur, je pose une question en langage naturel sur le corpus et j'obtiens une réponse accompagnée d'au moins une citation cliquable qui ouvre le passage source exact.
3. En tant qu'utilisateur, je demande un rapport de synthèse et j'obtiens un document structuré résumant les informations clés extraites du corpus.

## Hors scope (5 items minimum)

1. Pas de traduction automatique des documents multilingues (on suppose un corpus en français).
2. Pas d'édition collaborative multi-utilisateurs en temps réel (un seul utilisateur à la fois).
3. Pas d'authentification / gestion de comptes (hackathon = usage local mono-utilisateur).
4. Pas de traitement vidéo ou audio, uniquement documents texte, tabulaires et images statiques.
5. Pas de mise à jour incrémentale d'un document déjà uploadé (un nouvel upload = un nouveau document).
6. Pas de génération d'embeddings / recherche sémantique en V1 (FTS5 uniquement, embeddings en bonus si le temps le permet).

**Carte bonus "non argumenté" à choisir** : probablement l'item 6 (FTS5 vs embeddings), à défendre à l'oral — c'est un vrai choix d'ingénierie budget/temps, pas une facilité.

## Schéma d'architecture

```
[Front — upload + chat]
        |
        v
[Back — FastAPI]
        |
        +--> [Pipeline d'ingestion]
        |         extraction PDF/CSV/notes/images
        |         → chunks + métadonnées
        |         → SQLite (documents, chunks, chunks_fts)
        |
        +--> [Agent / boucle de réponse]
                  question utilisateur
                  → outil search() sur chunks_fts (SQLite FTS5)
                  → contexte + passages retrouvés
                  → appel LLM avec citations obligatoires
                  → réponse + liens vers passages sources
```

## Outils de l'agent (nom, signature typée, effet de bord)

| Outil | Signature | Effet de bord |
|---|---|---|
| `search` | `search(query: str, k: int) -> list[Chunk]` | Non (lecture seule) |
| `get_document` | `get_document(document_id: int) -> Document` | Non (lecture seule) |
| `extract_document` | `extract_document(file_path: str, file_type: str) -> list[Chunk]` | Oui (écrit en base) |
| `generate_report` | `generate_report(query: str) -> ReportResult` | Non (lecture seule, génère un texte de synthèse) |

## Happy path de la démo finale (6 étapes)

1. L'utilisateur ouvre l'application, la liste de documents est vide.
2. L'utilisateur dépose 5 documents hétérogènes (2 PDF, 1 CSV, 1 note texte, 1 capture d'écran) ; chaque document passe de "en cours" à "traité".
3. L'utilisateur pose une question en langage naturel sur le corpus (ex : "Quelles structures ont été identifiées sur le site X ?").
4. L'application affiche une réponse en langage naturel avec au moins une citation cliquable.
5. L'utilisateur clique sur la citation, le passage source exact s'ouvre (surligné, avec référence au document et à la page/position).
6. L'utilisateur demande un rapport de synthèse et obtient un document structuré résumant les informations extraites.

## Répartition du travail

- **[Toi]** : pipeline d'extraction/structuration des documents (PDF, CSV, notes, images), schéma SQLite (documents, chunks, chunks_fts), traçabilité et citations.
- **[Binôme]** : front (upload + interface de chat), orchestration de l'agent (appel LLM, outil `search`, mise en forme des réponses avec citations).
- Alternance obligatoire à chaque checkpoint pour la présentation orale.

## Stack retenue

- Back : FastAPI (Python)
- Extraction : `pypdf`/`pdfplumber` (PDF), `pandas` (CSV)
- Recherche : SQLite + FTS5 (choix délibéré, pas d'embeddings en V1 — voir hors scope #6)
- Front : à définir avec le binôme (React ou HTML/JS simple selon le temps)
- LLM : API déjà utilisée en interne