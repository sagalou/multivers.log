"""FastAPI back end: upload, document listing, questions and source passages"""

import json
import os
import re
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from app import db, extraction, tools

# Must run before reading any variable below, it fills os.environ from .env
load_dotenv()

# Settings read once at startup, with defaults for everything but the API key.
# NVIDIA NIM exposes an OpenAI-compatible endpoint: same client, different
# base_url and key, no other code changes needed.
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")

# Stops the agent looping forever if the model keeps asking for tools
MAX_AGENT_STEPS = 5

# Read by the model before every answer, it is what forbids inventing a source
SYSTEM_PROMPT = """You are Multivers.log, an assistant answering questions about \
the user's own uploaded documents.

Rules you must follow:
- Answer only from what the tools return. Never use outside knowledge.
- Every factual claim must come from a passage returned by search_documents.
- Always include at least one direct quote from a passage, copied exactly, \
character for character, wrapped in double quotes. Do not paraphrase the \
quoted part. Example: passage says "Le budget alloué est de 4200 euros pour \
le premier trimestre.", your answer must contain exactly that sentence in \
quotes somewhere, even if you also explain it in your own words around it.
- If your first search does not return anything relevant to the question, you may \
search once more with different, broader keywords before concluding. Never search \
more than twice for the same question.
- If the tools still return nothing relevant after that, say you found no \
information in the corpus. Do not guess, do not fill the gap.
- If a tool reports an error, say you could not complete the search. Do not pretend \
you succeeded.
- Answer in the language of the question."""

# Without a key the server still starts, only /ask reports it cannot answer
client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY) if NVIDIA_API_KEY else None

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


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete one document, its chunks and its file on disk"""

    deleted = db.delete_document(doc_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    # Files are stored prefixed with their doc_id at upload time
    if os.path.isdir(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            if filename.startswith(f"{doc_id}_"):
                os.remove(os.path.join(UPLOAD_DIR, filename))

    return {"deleted": doc_id}


@app.delete("/documents")
def delete_all_documents():
    """Clear the whole corpus, useful to restart a demo from an empty list"""

    count = db.delete_all_documents()

    if os.path.isdir(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, filename))

    return {"deleted_count": count}


@app.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    """Return one full passage, so clicking a citation can open its source"""

    chunk = db.get_chunk(chunk_id)

    # A citation pointing at nothing is an error worth reporting, not an empty answer
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")

    return chunk


def _no_answer(message: str, trace: list | None = None) -> dict:
    """Build the single failure shape the front handles, whatever went wrong"""

    return {
        "answer": None,
        "citations": [],
        "no_answer": True,
        "message": message,
        "trace": trace or [],
    }


def _citations_from_trace(trace: list, answer_text: str) -> list:
    """Collect only the passages actually quoted in the answer

    search_documents can return passages the model looked at and discarded
    (not relevant enough, or it decided the corpus has no answer). Citing all
    of them would show sources for a claim that was never made. A passage
    only becomes a citation if at least one of its sentences is found word
    for word in the answer: checking the whole passage at once was too
    strict, the model usually quotes a single sentence out of several.
    """

    citations = []
    seen = set()
    answer_text = answer_text or ""

    for entry in trace:
        for passage in entry.get("passages", []):
            if passage["chunk_id"] in seen:
                continue

            sentences = re.split(r"(?<=[.!?])\s+", passage["text"])
            quoted = any(
                len(s.strip()) > 15 and s.strip() in answer_text for s in sentences
            )

            if not quoted:
                continue

            seen.add(passage["chunk_id"])
            citations.append(
                {
                    "chunk_id": passage["chunk_id"],
                    "doc_id": passage["document"],
                    "page": passage["page"],
                    "quote": passage["text"],
                }
            )

    return citations


def _select_citations(answer_text: str, all_passages: list) -> list:
    """Ask the model which passages support its answer, as a fallback

    The prompt asks for a literal quote, but the model sometimes paraphrases
    a data-like passage (a CSV row, for instance) into a natural sentence
    instead of quoting it. When no exact quote is found, this second, small
    request asks the model to point at the chunk_ids it actually used,
    rather than leaving the answer with no citation at all.
    """

    if not all_passages:
        return []

    catalog = "\n".join(f"- {p['chunk_id']}: {p['text']}" for p in all_passages)

    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Given an answer and a list of passages, return the ids of "
                        "the passages that support the answer, as JSON only: "
                        '{"chunk_ids": ["id1", "id2"]}. If none support it, return '
                        '{"chunk_ids": []}. No text outside the JSON.'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Answer: {answer_text}\n\nPassages:\n{catalog}",
                },
            ],
        )
        picked = json.loads(response.choices[0].message.content)
        picked_ids = set(picked.get("chunk_ids", []))
    except Exception:
        # A follow-up call is a nice-to-have: if it fails, the answer still
        # stands, it is just shown without a clickable source this time
        return []

    return [
        {
            "chunk_id": p["chunk_id"],
            "doc_id": p["document"],
            "page": p["page"],
            "quote": p["text"],
        }
        for p in all_passages
        if p["chunk_id"] in picked_ids
    ]


@app.post("/ask")
async def ask_question(payload: dict):
    """Answer a question by letting the model call tools, never raising a 500"""

    question = payload.get("question", "")

    # Two guards below share the failure shape, so the front handles a single case
    if not question:
        return _no_answer("Question vide.")

    if client is None:
        return _no_answer("NVIDIA_API_KEY manquante côté serveur (voir .env).")

    started = time.perf_counter()
    trace = []

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    try:
        # The model decides which tool to call and when to stop, we only run what
        # it asks for and hand the result back until it answers in plain text
        for _ in range(MAX_AGENT_STEPS):
            response = client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=messages,
                tools=tools.TOOL_DECLARATIONS,
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                break

            # The assistant's tool request must be replayed before the tool
            # results, or the model loses track of what it asked for
            messages.append(message.model_dump(exclude_unset=True))

            for call in message.tool_calls:
                args = json.loads(call.function.arguments or "{}")
                result, entry = tools.run_tool(call.function.name, args)

                # Passages travel with the trace so citations survive the loop
                if isinstance(result, dict) and result.get("passages"):
                    entry["passages"] = result["passages"]

                trace.append(entry)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        answer_text = message.content

    except Exception as exc:
        # Refused key, exhausted quota, network cut during the demo: fall back to
        # the same no_answer shape instead of letting a raw 500 reach the front
        return _no_answer(f"Erreur lors de l'appel au LLM : {exc}", trace)

    usage = getattr(response, "usage", None)
    citations = _citations_from_trace(trace, answer_text)

    # Cheap match found nothing, but tools did return passages: ask the model
    # directly rather than showing an answer with zero sources
    if not citations:
        all_passages = [p for entry in trace for p in entry.get("passages", [])]
        citations = _select_citations(answer_text, all_passages)

    return {
        "answer": answer_text,
        "citations": citations,
        "trace": trace,
        # Shown in the UI so the cost of a question is never invisible
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", None),
            "output_tokens": getattr(usage, "completion_tokens", None),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    }


REPORT_SYSTEM_PROMPT = """You summarize a document corpus for the user.
Write a short narrative summary, a few sentences, based only on the excerpts \
given to you. Mention what kinds of documents are present and what they \
seem to cover. Do not invent details not shown in the excerpts. \
Answer in French."""


@app.post("/report")
async def generate_report(payload: dict):
    """Produce a real narrative summary of the corpus, from a sample of each document"""

    documents = [d for d in db.list_documents() if d["status"] == "processed"]

    if not documents:
        return {
            "report": "Le corpus est vide, aucun document traité à résumer.",
            "sources": [],
        }

    if client is None:
        return {
            "report": "NVIDIA_API_KEY manquante côté serveur, impossible de générer le rapport.",
            "sources": [],
        }

    excerpt_blocks = []
    for doc in documents:
        chunks = db.list_chunks_for_document(doc["id"], limit=3)
        preview = " ".join(c["content"][:300] for c in chunks)
        if preview:
            excerpt_blocks.append(f"[{doc['filename']}]\n{preview}")

    if not excerpt_blocks:
        return {
            "report": "Les documents traités ne contiennent aucun texte exploitable.",
            "sources": [d["id"] for d in documents],
        }

    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(excerpt_blocks)},
            ],
        )
        report_text = response.choices[0].message.content
    except Exception as exc:
        return {
            "report": f"Erreur lors de la génération du rapport : {exc}",
            "sources": [],
        }

    return {
        "report": report_text,
        "sources": [d["id"] for d in documents],
    }
