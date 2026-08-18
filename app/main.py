"""
Multivers.log — Back FastAPI
Palier 2 (Socle) : squelette des endpoints, conforme à API_CONTRACT.md.
La logique réelle (extraction, FTS5, appel LLM) sera branchée aux paliers 3 et 4.
"""

import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="Multivers.log API")

# Autorise le front (autre origine en dev) à appeler l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en prod / durcissement (palier 5)
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage en mémoire pour le squelette (remplacé par SQLite au palier 3)
_documents_store: dict[str, dict] = {}


@app.get("/health")
def health():
    """Vérifie que le serveur tourne, utile pour le front pendant le dev."""
    return {"status": "ok"}


@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """
    Reçoit un ou plusieurs documents.
    TODO palier 3 : brancher le pipeline d'ingestion réel
    (détection type -> extraction -> OCR si capture -> chunks -> SQLite).
    """
    results = []
    for f in files:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        _documents_store[doc_id] = {
            "id": doc_id,
            "filename": f.filename,
            "status": "processing",  # deviendra "processed" ou "error" une fois le pipeline branché
        }
        results.append(_documents_store[doc_id])
    return {"documents": results}


@app.get("/documents")
def list_documents():
    """Liste les documents et leur statut, pour la vue liste du front."""
    return {"documents": list(_documents_store.values())}


@app.post("/ask")
async def ask_question(payload: dict):
    """
    Reçoit une question en langage naturel.
    TODO palier 4 : brancher search() (FTS5) + appel LLM + vérification citation.
    Réponse au format exact du contrat API_CONTRACT.md, avec des valeurs
    factices pour l'instant afin que le front puisse déjà s'y brancher.
    """
    question = payload.get("question", "")

    if not question:
        return {
            "answer": None,
            "citations": [],
            "no_answer": True,
            "message": "Question vide.",
        }

    # Réponse factice conforme au contrat, à remplacer par la vraie boucle agent.
    return {
        "answer": "Réponse factice en attendant le branchement de l'agent (palier 4).",
        "citations": [
            {
                "chunk_id": "c_demo",
                "doc_id": "exemple.pdf",
                "page": 1,
                "char_start": 0,
                "char_end": 42,
                "quote": "Passage exemple pour tester le front",
            }
        ],
    }


@app.post("/report")
async def generate_report(payload: dict):
    """
    Génère un rapport de synthèse sur le corpus.
    TODO bonus (palier 5) : implémenter la vraie synthèse.
    """
    return {
        "report": "Rapport factice en attendant l'implémentation.",
        "sources": list(_documents_store.keys()),
    }
