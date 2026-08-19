"""FastAPI back end: upload, document listing, questions and source passages"""

import os
import uuid

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app import db, extraction

# Must run before reading any variable below, it fills os.environ from .env
load_dotenv()

# Settings read once at startup, with defaults for everything but the API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")

# Without a key the server still starts, only /ask reports it cannot answer
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Multivers.log API")

# The front runs on another port, so the browser needs this to allow the calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # to be restricted before production, palier 5
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Create the SQLite tables if needed, when the server boots"""

    db.init_db()


@app.get("/health")
def health():
    """Tell the caller the server is alive, used by the front during development"""

    return {"status": "ok"}


@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """Store the uploaded files, extract their content, return the final statuses"""

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    results = []

    for f in files:
        # Random short id, enough to stay unique without a counter in the database
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        file_type = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "unknown").lower()
        doc = db.insert_document(doc_id, f.filename, file_type, status="processing")

        # Prefix the saved name with the id, so two identical names never collide
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{f.filename}")
        content = await f.read()
        with open(file_path, "wb") as out:
            out.write(content)

        # Reads the file and fills the chunks table, then sets processed or error
        extraction.process_document(doc_id, file_path, file_type)

        # Return the updated status, not the processing one recorded a moment ago
        updated = next((d for d in db.list_documents() if d["id"] == doc_id), doc)
        results.append(updated)

    return {"documents": results}


@app.get("/documents")
def list_documents():
    """List every document and its status, so the front can fill its list on load"""

    return {"documents": db.list_documents()}


@app.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    """Return one full passage, so clicking a citation can open its source"""

    chunk = db.get_chunk(chunk_id)

    # A citation pointing at nothing is an error worth reporting, not an empty answer
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} introuvable.")

    return chunk


@app.post("/ask")
async def ask_question(payload: dict):
    """Answer a natural language question, never raising a 500 to the caller"""

    question = payload.get("question", "")

    # Three guards below share one answer shape, so the front handles a single case
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

    # Real call to the model, palier 4 will add db.search_chunks() for context
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(question)
        answer_text = response.text
    except Exception as exc:
        # Refused key, exhausted quota, network cut during the demo: fall back to
        # the same no_answer shape instead of letting a raw 500 reach the front
        return {
            "answer": None,
            "citations": [],
            "no_answer": True,
            "message": f"Erreur lors de l'appel au LLM : {exc}",
        }

    return {
        "answer": answer_text,
        "citations": [],  # filled at palier 4, once search is wired in
    }


@app.post("/report")
async def generate_report(payload: dict):
    """Produce a summary of the whole corpus, still a placeholder"""

    return {
        "report": "Rapport factice en attendant l'implémentation.",
        "sources": [doc["id"] for doc in db.list_documents()],
    }
