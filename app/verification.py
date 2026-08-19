"""Verification of the citations produced by the agent"""

import re
import unicodedata

from app import db

# Curly and prime apostrophes, all folded to the straight one
APOSTROPHES = "’ʼ′"

# Non breaking and thin spaces from PDFs, plus tabs and line breaks
SPACES = "     \t\r\n"


def normalize(text: str) -> str:
    """Return a comparable form of a text, ignoring typographic differences"""

    # NFC unifies the two Unicode ways of writing an accented letter
    normalized = unicodedata.normalize("NFC", text)

    for sign in APOSTROPHES:
        normalized = normalized.replace(sign, "'")

    for space in SPACES:
        normalized = normalized.replace(space, " ")

    # Chunking a PDF leaves runs of spaces that carry no meaning
    normalized = re.sub(r" +", " ", normalized)

    return normalized.strip().lower()


def verify_citation(citation: dict) -> dict:
    """Check that a citation points to a real chunk and quotes it faithfully"""

    chunk_id = citation.get("chunk_id")
    quote = citation.get("quote")

    # A malformed citation is rejected before touching the database
    if not chunk_id:
        return {"valid": False, "reason": "chunk_id manquant", "chunk": None}

    if not quote:
        return {"valid": False, "reason": "citation vide", "chunk": None}

    chunk = db.get_chunk(chunk_id)

    # Catches an invented reference: the model cited a passage that never existed
    if chunk is None:
        return {"valid": False, "reason": "passage introuvable en base", "chunk": None}

    # Catches a distorted quote: right passage, but the wording was altered
    if normalize(quote) not in normalize(chunk["content"]):
        return {"valid": False, "reason": "citation absente du passage source", "chunk": chunk}

    return {"valid": True, "reason": "verifiee", "chunk": chunk}


def verify_citations(citations: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split a list of citations between the verified ones and the rejected ones"""

    verified = []
    rejected = []

    for citation in citations:
        result = verify_citation(citation)

        if result["valid"]:
            # Add what the front needs to display and open the source passage
            enriched = dict(citation)
            enriched["filename"] = result["chunk"]["filename"]
            enriched["content"] = result["chunk"]["content"]
            enriched["page"] = result["chunk"]["page_number"]
            verified.append(enriched)
        else:
            # Rejected ones are kept with their motive, never shown to the user
            rejected.append({"citation": citation, "reason": result["reason"]})

    return verified, rejected
