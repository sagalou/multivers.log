# Architecture — Multivers.log

## Vue d'ensemble

Multivers.log ingère des documents hétérogènes issus de plusieurs univers thématiques (archéologie, espace, JDR, jeu vidéo), en extrait une structure exploitable, et répond à des questions en langage naturel avec citation systématique de la source exacte.

## Schéma

```mermaid
flowchart TB
    subgraph Front["Front — Interface"]
        Upload["Zone d'upload<br/>(multi-fichiers)"]
        Chat["Zone de question<br/>(langage naturel)"]
        Result["Réponse + citations<br/>cliquables"]
        DocList["Liste documents<br/>+ statut"]
    end

    subgraph Back["Back — FastAPI"]
        APIUpload["POST /upload"]
        APIAsk["POST /ask"]
        APIReport["POST /report"]
    end

    subgraph Ingestion["Pipeline d'ingestion"]
        Detect["Détection type<br/>PDF / CSV / note / capture"]
        Extract["Extraction adaptée<br/>par type de fichier"]
        Chunk["Découpage en chunks<br/>+ métadonnées<br/>(source, page, catégorie)"]
    end

    subgraph Agent["Agent / boucle de réponse"]
        SearchTool["Outil search()<br/>search(query: str, k: int) -> list[Chunk]"]
        Context["Construction<br/>du contexte"]
        LLM["Appel LLM<br/>citation obligatoire"]
    end

    subgraph Storage["SQLite"]
        DocsTable[("documents")]
        ChunksTable[("chunks")]
        FTSTable[("chunks_fts<br/>index FTS5")]
    end

    Upload --> APIUpload
    APIUpload --> Detect
    Detect --> Extract
    Extract --> Chunk
    Chunk --> DocsTable
    Chunk --> ChunksTable
    ChunksTable --> FTSTable

    Chat --> APIAsk
    APIAsk --> SearchTool
    SearchTool --> FTSTable
    FTSTable --> Context
    Context --> LLM
    LLM --> Result

    APIReport --> SearchTool

    DocsTable --> DocList
```

## Description des couches

### Front
- Zone d'upload de documents (drag & drop, multi-fichiers)
- Zone de chat/questions en langage naturel
- Affichage des réponses avec citations cliquables
- Vue liste des documents avec statut (en cours / traité / erreur)

### Back (FastAPI)
- `POST /upload` : reçoit les fichiers, déclenche le pipeline d'ingestion
- `POST /ask` : reçoit une question, déclenche la boucle agent
- `POST /report` : génère une synthèse du corpus

### Pipeline d'ingestion
1. Détection du type de fichier (PDF, CSV, note texte, capture d'écran)
2. Extraction adaptée par type (texte, tableau, OCR si besoin)
3. Découpage en chunks avec métadonnées (document source, page/position, catégorie thématique : archéo / espace / JDR / jeu vidéo)
4. Écriture en base SQLite + indexation FTS5

### Agent / boucle de réponse
1. Réception de la question utilisateur
2. Appel de l'outil `search()` sur l'index FTS5
3. Construction du contexte à partir des chunks trouvés
4. Appel au LLM avec obligation de citer ses sources
5. Renvoi réponse + références cliquables vers les passages exacts

### Stockage (SQLite)
- `documents` : métadonnées des fichiers uploadés
- `chunks` : passages extraits, un document en a plusieurs
- `chunks_fts` : table virtuelle FTS5 pour la recherche plein texte

## Choix techniques justifiés

- **SQLite + FTS5 plutôt que base vectorielle** : pas de dépendance externe, pas d'appel API supplémentaire pour indexer, setup minimal. Compromis assumé : moins bon sur les questions reformulées différemment du texte source, acceptable pour un MVP de 3 jours avec un vocabulaire technique répétitif.
- **FastAPI** : rapide à mettre en place, écosystème Python cohérent avec le reste du pipeline d'extraction.