"""
Multivers.log — Extraction de documents
Palier 3 : transforme un fichier déposé en chunks exploitables, insérés en base.
Un extracteur par format, tous convergent vers la même fonction chunk_and_store().
"""

import re
import uuid

import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image

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


def extract_csv(file_path: str) -> list[dict]:
    """
    Extrait un CSV ligne par ligne. Chaque ligne devient un chunk séparé
    (pas de découpage par phrases ici, une ligne de tableur est déjà une
    unité de sens : une facture, une mesure, une entrée). "page_number"
    n'a pas de sens pour un CSV, on utilise "position" comme numéro de
    ligne pour permettre malgré tout une citation précise.
    """
    df = pd.read_csv(file_path)
    results = []
    for position, row in df.iterrows():
        row_text = "; ".join(f"{col}: {val}" for col, val in row.items())
        if row_text.strip():
            results.append(
                {
                    "content": row_text,
                    "page_number": None,
                    "position": int(position),
                }
            )
    return results


def extract_note(file_path: str) -> list[dict]:
    """
    Extrait une note texte brute (.txt, .md). Pas de notion de page,
    juste un découpage en chunks comme pour un PDF.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    chunks = chunk_text(text)
    return [
        {"content": c, "page_number": None, "position": position}
        for position, c in enumerate(chunks)
    ]


def extract_image(file_path: str) -> list[dict]:
    """
    Extrait le texte d'une capture d'écran via OCR (Tesseract, local et
    gratuit, cohérent avec le choix FTS5 plutôt qu'un service cloud).
    Une image n'a qu'un seul passage indexable : contrairement à un PDF,
    on ne peut pas surligner une portion précise dedans (limite connue,
    documentée dans README.md).
    Nécessite le pack de langue française de Tesseract installé sur la
    machine (paquet système, pas pip) : voir README pour l'installation.
    """
    try:
        text = pytesseract.image_to_string(Image.open(file_path), lang="fra")
    except pytesseract.TesseractError as exc:
        if "fra" in str(exc):
            raise RuntimeError(
                "Pack de langue française Tesseract manquant sur cette machine "
                "(sudo apt install tesseract-ocr-fra)."
            ) from exc
        raise
    chunks = chunk_text(text)
    return [
        {"content": c, "page_number": None, "position": position}
        for position, c in enumerate(chunks)
    ]


EXTRACTORS = {
    "pdf": extract_pdf,
    "csv": extract_csv,
    "txt": extract_note,
    "md": extract_note,
    "png": extract_image,
    "jpg": extract_image,
    "jpeg": extract_image,
}


def process_document(document_id: str, file_path: str, file_type: str) -> None:
    """
    Point d'entrée du pipeline d'extraction, appelé depuis /upload une fois
    le fichier sauvegardé sur disque. Met à jour le statut du document
    ("processed" ou "error") selon le résultat, jamais laissé en "processing".
    """
    extractor = EXTRACTORS.get(file_type)

    try:
        if extractor is None:
            db.update_document_status(
                document_id, "error", f"Type de fichier non supporté pour l'instant : {file_type}"
            )
            return

        extracted = extractor(file_path)

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