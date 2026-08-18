"""
Multivers.log — Couche base de données (SQLite + FTS5)
Palier 3 : schéma et fonctions de base. L'extraction (PDF/CSV/notes/OCR)
vient ensuite, elle appellera insert_chunk() pour chaque passage extrait.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def _database_path() -> str:
    """
    Lecture différée (pas au chargement du module) pour ne pas dépendre
    de l'ordre entre load_dotenv() et l'import de ce module : si ce module
    est importé avant que le .env soit chargé, une valeur lue une seule
    fois à l'import figerait le défaut et ignorerait le .env pour toujours.
    """
    return os.getenv("DATABASE_PATH", "./data/multivers.db")


def _ensure_data_dir():
    """Crée le dossier data/ si besoin (SQLite ne le fait pas tout seul)."""
    os.makedirs(os.path.dirname(_database_path()) or ".", exist_ok=True)


@contextmanager
def get_connection():
    """
    Fournit une connexion SQLite avec les bonnes options (clés étrangères
    activées, résultats accessibles par nom de colonne).
    """
    _ensure_data_dir()
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """
    Crée les tables si elles n'existent pas encore. Appelée au démarrage
    de l'app (voir main.py), sans danger si déjà existantes (IF NOT EXISTS).
    """
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                page_number INTEGER,
                position INTEGER,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content,
                content='chunks',
                content_rowid='rowid'
            );

            -- Garde chunks_fts synchronisé automatiquement avec chunks
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, content) VALUES (new.rowid, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.rowid, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                INSERT INTO chunks_fts(rowid, content) VALUES (new.rowid, new.content);
            END;
            """
        )


# --- Documents ---------------------------------------------------------

def insert_document(doc_id: str, filename: str, file_type: str, status: str = "processing") -> dict:
    """Enregistre un nouveau document déposé, statut par défaut 'processing'."""
    uploaded_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO documents (id, filename, file_type, uploaded_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (doc_id, filename, file_type, uploaded_at, status),
        )
    return {"id": doc_id, "filename": filename, "status": status}


def update_document_status(doc_id: str, status: str, error_message: str | None = None):
    """Met à jour le statut d'un document (processing -> processed / error)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE documents SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, doc_id),
        )


def list_documents() -> list[dict]:
    """Liste tous les documents avec leur statut, pour GET /documents."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, status, error_message FROM documents ORDER BY uploaded_at"
        ).fetchall()
        return [dict(row) for row in rows]


# --- Chunks --------------------------------------------------------------

def insert_chunk(chunk_id: str, document_id: str, content: str, page_number: int | None = None, position: int | None = None):
    """
    Insère un chunk (passage extrait) rattaché à un document.
    L'indexation FTS5 se fait automatiquement via le trigger chunks_ai.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chunks (id, document_id, content, page_number, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk_id, document_id, content, page_number, position),
        )


def get_chunk(chunk_id: str) -> dict | None:
    """Récupère un chunk par son id, utilisé pour vérifier une citation."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT c.id, c.document_id, c.content, c.page_number, c.position, d.filename "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()
        return dict(row) if row else None


def _sanitize_fts5_query(raw_query: str) -> str:
    """
    Transforme une question en langage naturel en requête FTS5 sûre.
    FTS5 a sa propre syntaxe (guillemets, parenthèses, AND/OR/NOT, -, *,
    filtres de colonne avec ':'). Envoyer une question brute ("Qu'est-ce
    que l'utilisateur a payé ?") peut lever une erreur de syntaxe FTS5.
    On extrait uniquement les mots (alphanumériques, accents compris),
    chacun entre guillemets doubles (recherche littérale du terme, pas
    interprété comme opérateur), joints par OR pour maximiser le rappel.
    """
    words = re.findall(r"\w+", raw_query, flags=re.UNICODE)
    if not words:
        return ""
    # Chaque mot entre guillemets doubles : neutralise -, *, :, etc.
    # dans le mot lui-même, et empêche AND/OR/NOT d'être interprétés
    # comme opérateurs plutôt que comme mots cherchés.
    return " OR ".join(f'"{w}"' for w in words)


def search_chunks(query: str, k: int = 5) -> list[dict]:
    """
    Recherche plein texte via FTS5. Signature conforme à SPEC.md :
    search(query: str, k: int) -> list[Chunk]
    La requête est assainie avant d'être envoyée à FTS5 (voir
    _sanitize_fts5_query) ; en cas d'échec malgré tout, on retourne une
    liste vide plutôt que de laisser remonter une erreur 500 au client.
    """
    safe_query = _sanitize_fts5_query(query)
    if not safe_query:
        return []

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.document_id, c.content, c.page_number, c.position, d.filename
                FROM chunks_fts
                JOIN chunks c ON c.rowid = chunks_fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, k),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        # Erreur de syntaxe FTS5 malgré l'assainissement (cas limite) :
        # on ne casse pas la réponse, on considère juste qu'il n'y a
        # pas de résultat pertinent.
        return []