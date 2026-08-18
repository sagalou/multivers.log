"""
Multivers.log — Back FastAPI
Palier 3 : schéma SQLite + FTS5 branché (documents, chunks).
L'extraction réelle (PDF/CSV/notes/OCR) reste à brancher ensuite dans /upload.
"""

import os
import uuid

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app import db, extraction

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Multivers.log API")

# Autorise le front (autre origine en dev) à appeler l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en prod / durcissement (palier 5)
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Crée les tables SQLite si besoin, au démarrage du serveur."""
    db.init_db()


@app.get("/health")
def health():
    """Vérifie que le serveur tourne, utile pour le front pendant le dev."""
    return {"status": "ok"}


@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """
    Reçoit un ou plusieurs documents, les sauvegarde sur disque, les
    enregistre en base (statut "processing"), puis lance l'extraction
    réelle. Le statut final ("processed" ou "error") est mis à jour par
    extraction.process_document(), jamais laissé bloqué en "processing".
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    results = []
    for f in files:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        file_type = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "unknown").lower()
        doc = db.insert_document(doc_id, f.filename, file_type, status="processing")

        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{f.filename}")
        content = await f.read()
        with open(file_path, "wb") as out:
            out.write(content)

        extraction.process_document(doc_id, file_path, file_type)

        # Renvoie le statut à jour (processed/error), pas celui d'origine.
        updated = next((d for d in db.list_documents() if d["id"] == doc_id), doc)
        results.append(updated)

    return {"documents": results}


@app.get("/documents")
def list_documents():
    """Liste les documents et leur statut, pour la vue liste du front."""
    return {"documents": db.list_documents()}


@app.post("/ask")
async def ask_question(payload: dict):
    """
    Reçoit une question en langage naturel.
    Palier 3 : toujours pas de recherche branchée dans la boucle de réponse
    (le contexte issu du corpus arrive au palier 4, via db.search_chunks()).
    """
    question = payload.get("question", "")

    if not question:
        return {
            "answer": None,
            "citations": [],
            "no_answer": True,
            "message": "Question vide.",
        }

    if not GEMINI_API_KEY:
        return {
            "answer": None,
            "citations": [],
            "no_answer": True,
            "message": "GEMINI_API_KEY manquante côté serveur (voir .env).",
        }

    # Appel réel au LLM (palier 4 : brancher db.search_chunks() pour le contexte).
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(question)
        answer_text = response.text
    except Exception as exc:
        # Clé refusée, quota épuisé, réseau coupé pendant la démo, etc. :
        # on ne laisse jamais remonter une 500 brute, on retombe sur le
        # même format no_answer que pour une question vide ou une clé
        # manquante, cohérent pour le front.
        return {
            "answer": None,
            "citations": [],
            "no_answer": True,
            "message": f"Erreur lors de l'appel au LLM : {exc}",
        }

    return {
        "answer": answer_text,
        "citations": [],  # les vraies citations arrivent au palier 4, avec search_chunks()
    }


@app.post("/report")
async def generate_report(payload: dict):
    """
    Génère un rapport de synthèse sur le corpus.
    TODO bonus (palier 5) : implémenter la vraie synthèse.
    """
    return {
        "report": "Rapport factice en attendant l'implémentation.",
        "sources": [doc["id"] for doc in db.list_documents()],
    }