"""Agent tools: what the model can call, how it is described to it, and the trace"""

import time

from app import db

# Kept small on purpose: a tool that returns 40k tokens of raw JSON poisons
# the context and costs money on every turn
MAX_CHUNKS_RETURNED = 5
MAX_CONTENT_CHARS = 600


def search_documents(query: str, k: int = 5) -> dict:
    """Search the corpus and return short passages with the ids needed to cite them"""

    results = db.search_chunks(query, k=min(k, MAX_CHUNKS_RETURNED))

    if not results:
        return {"found": 0, "passages": []}

    # Only the fields the model needs to answer and to cite, nothing else
    passages = [
        {
            "chunk_id": r["id"],
            "document": r["filename"],
            "page": r["page_number"],
            "text": r["content"][:MAX_CONTENT_CHARS],
        }
        for r in results
    ]

    return {"found": len(passages), "passages": passages}


def list_corpus() -> dict:
    """Tell what is in the corpus right now, without reading the documents"""

    documents = db.list_documents()

    return {
        "count": len(documents),
        "documents": [
            {"filename": d["filename"], "status": d["status"]} for d in documents
        ],
    }


# Registry: one place mapping a tool name to the function that runs it
TOOL_FUNCTIONS = {
    "search_documents": search_documents,
    "list_corpus": list_corpus,
}

# Tools switched off from the UI. They stay declared to the model on purpose:
# the point is to watch the agent handle a broken tool, not to hide it
DISABLED_TOOLS = set()


def list_tool_states() -> list[dict]:
    """Report every tool and whether it is currently enabled"""

    return [
        {
            "name": declaration["function"]["name"],
            "description": declaration["function"]["description"],
            "enabled": declaration["function"]["name"] not in DISABLED_TOOLS,
        }
        for declaration in TOOL_DECLARATIONS
    ]


def set_tool_enabled(name: str, enabled: bool) -> bool:
    """Switch one tool on or off, returning False if the name is unknown"""

    if name not in TOOL_FUNCTIONS:
        return False

    if enabled:
        DISABLED_TOOLS.discard(name)
    else:
        DISABLED_TOOLS.add(name)

    return True

# Declarations sent to the model. The descriptions are the real work here:
# the model picks a tool from these words alone, so they say when to use it,
# not just what it does
TOOL_DECLARATIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the user's uploaded documents for passages relevant to a question. "
                "Use this whenever the question is about the content of the documents: "
                "figures, names, dates, facts, what a document says about a topic. "
                "Returns passages with a chunk_id that must be used to cite the source."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for, drawn from the user's question",
                    },
                    "k": {
                        "type": "integer",
                        "description": "How many passages to return, 5 by default",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_corpus",
            "description": (
                "List the documents currently uploaded and their processing status. "
                "Use this when the question is about the corpus itself rather than its "
                "content: how many documents there are, which files were uploaded, "
                "whether a file failed to process. Does not read the documents."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _coerce_args(name: str, args: dict) -> dict:
    """Cast the arguments sent by the model to the types declared for the tool"""

    declaration = next(
        (d for d in TOOL_DECLARATIONS if d["function"]["name"] == name), None
    )

    if declaration is None:
        return args

    properties = declaration["function"].get("parameters", {}).get("properties", {})
    coerced = {}

    for key, value in args.items():
        # An argument the tool never declared would raise a TypeError on call,
        # dropping it lets the tool run with what it does understand
        if key not in properties:
            continue

        expected = properties[key].get("type")

        try:
            if expected == "integer":
                # float() first, so a model sending "2.0" for an integer still works
                coerced[key] = int(float(value))
            elif expected == "number":
                coerced[key] = float(value)
            elif expected == "boolean":
                coerced[key] = str(value).strip().lower() in ("true", "1", "yes")
            elif expected == "string":
                coerced[key] = str(value)
            else:
                coerced[key] = value
        except (TypeError, ValueError):
            # Nonsense value such as "beaucoup" for a count: drop the argument so
            # the tool falls back on its own default instead of failing outright
            continue

    return coerced


def run_tool(name: str, args: dict) -> tuple[dict, dict]:
    """Run one tool by name, returning its result and a trace entry for the UI"""

    started = time.perf_counter()

    # A tool switched off from the UI fails like a broken one, so the agent has
    # to admit it could not run instead of pretending otherwise
    if name in DISABLED_TOOLS:
        return (
            {"error": f"Tool {name} is currently disabled"},
            {
                "tool": name,
                "args": args,
                "status": "error",
                "error": "outil desactive",
                "duration_ms": 0,
            },
        )

    function = TOOL_FUNCTIONS.get(name)

    # An unknown name means the model invented a tool, report it rather than crash
    if function is None:
        return (
            {"error": f"Unknown tool: {name}"},
            {
                "tool": name,
                "args": args,
                "status": "error",
                "error": "unknown tool",
                "duration_ms": 0,
            },
        )

    # The OpenAI-compatible API hands arguments over as decoded JSON with no type
    # guarantee: a model may well send k as the string "5" instead of the number 5
    try:
        result = function(**_coerce_args(name, args))
        status, error = "ok", None
    except Exception as exc:
        # A broken tool must not break the answer: the model is told it failed
        # and can say so, which is what palier 3 asks for
        result = {"error": str(exc)}
        status, error = "error", str(exc)

    duration_ms = round((time.perf_counter() - started) * 1000, 1)

    trace = {
        "tool": name,
        "args": args,
        "status": status,
        "duration_ms": duration_ms,
    }

    if error:
        trace["error"] = error

    return result, trace