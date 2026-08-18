"""
Multivers.log — Extraction de documents
Palier 3 : transforme un fichier déposé en chunks exploitables, insérés en base.
Un extracteur par format, tous convergent vers la même fonction chunk_and_store().
"""

import re
import uuid

import pdfplumber

from app import db


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """
    Découpe un texte en chunks d'environ max_chars caractères, en coupant
    de préférence aux frontières de phrases pour ne pas tronquer au milieu
    d'une idée (important pour que les citations restent lisibles).
    """
    text = text.strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def extract_pdf(file_path: str) -> list[dict]:
    """
    Extrait le texte d'un PDF page par page, découpe chaque page en chunks.
    Retourne une liste de dicts {content, page_number, position} prêts à
    être insérés via db.insert_chunk(), sans dépendre de son propre id.
    """
    results = []
    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            page_chunks = chunk_text(page_text)
            for position, chunk_content in enumerate(page_chunks):
                results.append(
                    {
                        "content": chunk_content,
                        "page_number": page_number,
                        "position": position,
                    }
                )
    return results


def process_document(document_id: str, file_path: str, file_type: str) -> None:
    """
    Point d'entrée du pipeline d'extraction, appelé depuis /upload une fois
    le fichier sauvegardé sur disque. Met à jour le statut du document
    ("processed" ou "error") selon le résultat, jamais laissé en "processing".
    """
    try:
        if file_type == "pdf":
            extracted = extract_pdf(file_path)
        else:
            db.update_document_status(
                document_id, "error", f"Type de fichier non supporté pour l'instant : {file_type}"
            )
            return

        if not extracted:
            db.update_document_status(
                document_id, "error", "Aucun texte extrait (document vide ou illisible)."
            )
            return

        for chunk in extracted:
            chunk_id = f"c_{uuid.uuid4().hex[:8]}"
            db.insert_chunk(
                chunk_id,
                document_id,
                chunk["content"],
                page_number=chunk["page_number"],
                position=chunk["position"],
            )

        db.update_document_status(document_id, "processed")

    except Exception as exc:
        # Ne jamais laisser un document bloqué en "processing" : un fichier
        # corrompu ou illisible passe en erreur explicite, sans faire
        # planter le reste de l'upload (voir cas d'échec géré dans SPEC.md).
        db.update_document_status(document_id, "error", str(exc))