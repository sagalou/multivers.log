"""Database layer: SQLite schema, chunk storage and FTS5 full text search"""

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def _database_path() -> str:
    """Read the database path on every call, never once at import time"""

    # Reading at import would freeze the default value if this module were
    # imported before load_dotenv() ran, silently ignoring the .env forever
    return os.getenv("DATABASE_PATH", "./data/multivers.db")


def _ensure_data_dir():
    """Create the data directory, SQLite does not create it by itself"""

    os.makedirs(os.path.dirname(_database_path()) or ".", exist_ok=True)


@contextmanager
def get_connection():
    """Open a SQLite connection with the right options, and always close it"""

    _ensure_data_dir()
    conn = sqlite3.connect(_database_path())

    # Row lets results be read by column name instead of by index
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()
    finally:
        # finally runs even if the caller raised, so no connection leaks
        conn.close()


def init_db():
    """Create the tables if they do not exist yet, called at server startup"""

    with get_connection() as conn:
        conn.executescript(
            """
            -- One row per uploaded file, error_message explains a failed status
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT
            );

            -- One row per extracted passage, page_number is null for CSV and notes
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                page_number INTEGER,
                position INTEGER,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            -- Search index over chunks.content, stores no copy of the text itself
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content,
                content='chunks',
                content_rowid='rowid'
            );

            -- These three triggers keep the index in sync with the chunks table
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
    """Record a newly uploaded document, before its content is extracted"""

    # Stored in UTC ISO format so ORDER BY sorts chronologically as plain text
    uploaded_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO documents (id, filename, file_type, uploaded_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (doc_id, filename, file_type, uploaded_at, status),
        )

    # Same shape as GET /documents, so the front reads both the same way
    return {"id": doc_id, "filename": filename, "status": status}


def update_document_status(doc_id: str, status: str, error_message: str | None = None):
    """Move a document from processing to processed or error"""

    with get_connection() as conn:
        conn.execute(
            "UPDATE documents SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, doc_id),
        )


def list_documents() -> list[dict]:
    """List every document and its status, for GET /documents"""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, status, error_message FROM documents ORDER BY uploaded_at"
        ).fetchall()
        return [dict(row) for row in rows]


# --- Chunks --------------------------------------------------------------

def insert_chunk(chunk_id: str, document_id: str, content: str, page_number: int | None = None, position: int | None = None):
    """Store one extracted passage attached to its document"""

    # No indexing call here, the chunks_ai trigger fills chunks_fts on its own
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chunks (id, document_id, content, page_number, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk_id, document_id, content, page_number, position),
        )


def get_chunk(chunk_id: str) -> dict | None:
    """Fetch one passage by id, used to verify a citation and to open the source"""

    with get_connection() as conn:
        # The join brings the file name along, the front needs it to label the source
        row = conn.execute(
            "SELECT c.id, c.document_id, c.content, c.page_number, c.position, d.filename "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()
        return dict(row) if row else None


def _sanitize_fts5_query(raw_query: str) -> str:
    """Turn a natural language question into a safe FTS5 query"""

    # FTS5 has its own syntax: quotes, parentheses, AND OR NOT, -, *, column
    # filters with ':'. A raw French question would raise a syntax error
    words = re.findall(r"\w+", raw_query, flags=re.UNICODE)
    if not words:
        return ""

    # FTS5 matches whole tokens: "factures" never matches an indexed
    # "facture". Stripping a naive plural ending and searching as a
    # prefix makes both forms match the same tokens either way.
    stems = [w[:-1] if w[-1] in "sx" and len(w) > 3 else w for w in words]

    # Double quotes make each stem literal, * turns it into a prefix search,
    # OR between them widens the search instead of requiring every word
    return " OR ".join(f'"{s}"*' for s in stems)


def search_chunks(query: str, k: int = 5) -> list[dict]:
    """Full text search over the chunks, returning the k best passages"""

    safe_query = _sanitize_fts5_query(query)

    # A question made only of punctuation leaves nothing to search for
    if not safe_query:
        return []

    try:
        with get_connection() as conn:
            # ORDER BY rank uses the FTS5 relevance score, best matches first
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
        # Edge case FTS5 syntax error despite sanitizing: treat it as no result
        # rather than letting a 500 reach the client
        return []


def delete_document(doc_id: str) -> bool:
    """Delete a document and its chunks, return False if it does not exist"""

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

        if existing is None:
            return False

        # Chunks first: the foreign key constraint refuses to delete
        # a document still referenced by chunks
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        return True


def delete_all_documents() -> int:
    """Clear the whole corpus, return how many documents were removed"""

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM documents")

        return count

def list_chunks_for_document(document_id: str, limit: int = 3) -> list[dict]:
    """Return a sample of chunks for one document, in reading order

    Used by /report to build a compact preview of the corpus: sending every
    chunk of every document would repeat the palier 3 trap of dumping raw
    content into the model's context, so only the first few chunks per
    document are used.
    """

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, content, page_number, position FROM chunks "
            "WHERE document_id = ? ORDER BY position LIMIT ?",
            (document_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
