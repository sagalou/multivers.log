"""Tests on the search layer: the one bug found and fixed today, kept in place
so it cannot silently come back.
"""

import sqlite3

from app.db import _sanitize_fts5_query


def test_plural_matches_singular_stem():
    """"factures" and "facture" must produce the same searchable stem

    Regression test for the bug the SWE found: FTS5 does exact-token
    matching, so a plural question ("Donne moi toutes les factures")
    used to return zero results even when singular chunks existed.
    """

    assert _sanitize_fts5_query("facture") == _sanitize_fts5_query("factures")


def test_search_finds_document_indexed_under_singular_form():
    """End to end: index one chunk with "Facture", search with the plural

    A unit test on the query string alone would not have caught the
    original bug if the prefix wildcard had been malformed. This runs
    the real FTS5 engine to prove the match actually happens.
    """

    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE chunks (id INTEGER PRIMARY KEY, content TEXT);
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            content, content='chunks', content_rowid='id'
        );
        """
    )
    conn.execute("INSERT INTO chunks (content) VALUES ('Facture Zanzibar Heritage 600 euros')")
    conn.execute("INSERT INTO chunks_fts(rowid, content) SELECT id, content FROM chunks")
    conn.commit()

    safe_query = _sanitize_fts5_query("factures")
    rows = conn.execute(
        "SELECT content FROM chunks_fts WHERE chunks_fts MATCH ?", (safe_query,)
    ).fetchall()

    assert len(rows) == 1
    assert "Zanzibar Heritage" in rows[0][0]


def test_empty_query_returns_empty_string():
    """A question made only of punctuation must not reach FTS5 as ''

    An empty MATCH string is a syntax error in FTS5, not zero results.
    search_chunks() relies on this function returning "" so it can bail
    out before ever calling MATCH.
    """

    assert _sanitize_fts5_query("???") == ""
    assert _sanitize_fts5_query("") == ""


def test_short_words_are_not_stemmed():
    """Stripping a trailing s/x must not butcher a word down to nothing

    A naive stemmer applied to every word would turn "les" into "le",
    degrading search quality for common short words. The length guard
    (> 3 chars) exists specifically to avoid that.
    """

    assert _sanitize_fts5_query("les") == '"les"*'

def test_very_short_words_are_dropped():
    """Words under 3 letters are removed, they would match the whole corpus

    Searched as a prefix, the "d" of "d'un" matches de, des, du,
    documentation... and drags every document back for a question that has
    nothing to do with them. Observed on a real query: "donne moi la recette
    d'un sandwich" returned 7 passages, none of them about a sandwich.
    """

    assert _sanitize_fts5_query("d") == ""
    assert _sanitize_fts5_query("as") == ""


def test_digits_survive_the_length_filter():
    """A short number is meaningful, unlike a short word

    An invoice number or a year must stay searchable even with two digits.
    """

    assert _sanitize_fts5_query("facture 42") == '"facture"* OR "42"*'


def test_real_query_no_longer_matches_everything():
    """Regression on the false positive found during the palier 5 chaos run"""

    query = _sanitize_fts5_query("donne moi la recette d'un sandwich")
    assert '"recette"*' in query
    assert '"sandwich"*' in query
    # The stop words that used to drag the whole corpus back are gone
    for bruit in ('"la"*', '"un"*', '"d"*'):
        assert bruit not in query
