import { useEffect, useState } from "react";
import {
  askQuestion,
  getChunk,
  isMockMode,
  listDocuments,
  listTools,
  setToolEnabled,
  uploadDocuments,
} from "./api";
import "./App.css";

// Maps the raw status sent by the back to the wording shown on screen
const STATUS_LABELS = {
  processing: "en cours",
  processed: "traite",
  error: "erreur",
};

// Price per million tokens, editable in front/.env without touching the code
// Check the current rates on ai.google.dev/pricing, they change with the model
const PRICE_INPUT = Number(import.meta.env.VITE_PRICE_INPUT_PER_M || 0);
const PRICE_OUTPUT = Number(import.meta.env.VITE_PRICE_OUTPUT_PER_M || 0);

// Falls back to the raw value if the back ever sends an unknown status
function statusLabel(status) {
  if (STATUS_LABELS[status]) {
    return STATUS_LABELS[status];
  }
  return status;
}

// Reuses the document status colours for a tool call result
function stepStatusClass(status) {
  if (status === "ok") {
    return "status status-processed";
  }
  return "status status-error";
}

// Class and wording of the on/off button, kept out of the markup
function toggleClass(enabled) {
  if (enabled) {
    return "toggle toggle-on";
  }
  return "toggle toggle-off";
}

function toggleLabel(enabled) {
  if (enabled) {
    return "actif";
  }
  return "desactive";
}

// Turns a token count into an estimated price in dollars
function estimateCost(usage) {
  const input = (usage.input_tokens || 0) / 1000000;
  const output = (usage.output_tokens || 0) / 1000000;
  return input * PRICE_INPUT + output * PRICE_OUTPUT;
}

function App() {
  // Everything the page displays lives in these states
  // Changing one of them makes React redraw the affected part of the page
  const [documents, setDocuments] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [dragging, setDragging] = useState(false);

  // Source passage opened by clicking a citation, null when nothing is open
  const [passage, setPassage] = useState(null);
  const [loadingPassage, setLoadingPassage] = useState("");

  // Agent tools and their on/off state, mirrored from the server
  const [tools, setTools] = useState([]);
  const [togglingTool, setTogglingTool] = useState("");

  // Reloads the document list from the server, after an upload or on page load
  async function refreshDocuments() {
    try {
      const list = await listDocuments();
      setDocuments(list);
    } catch (failure) {
      setError(`Liste des documents indisponible : ${failure.message}`);
    }
  }

  // Reads which tools the agent may currently call
  async function refreshTools() {
    try {
      const list = await listTools();
      setTools(list);
    } catch (failure) {
      setError(`Liste des outils indisponible : ${failure.message}`);
    }
  }

  // Empty brackets mean: run this once, when the page opens
  useEffect(() => {
    refreshDocuments();
    refreshTools();
  }, []);

  // Switches a tool off to show the agent coping with a broken tool, or back on
  async function handleToggleTool(tool) {
    setError("");
    setTogglingTool(tool.name);

    try {
      const list = await setToolEnabled(tool.name, !tool.enabled);
      setTools(list);
    } catch (failure) {
      setError(`Impossible de changer l'etat de l'outil : ${failure.message}`);
    } finally {
      setTogglingTool("");
    }
  }

  // Handles both ways of picking files: the file dialog and the drop zone
  async function handleFiles(fileList) {
    // A FileList is not an array, Array.from makes it usable with map and forEach
    const files = Array.from(fileList);
    if (files.length === 0) {
      return;
    }

    setError("");
    setUploading(true);

    try {
      await uploadDocuments(files);
      await refreshDocuments();
    } catch (failure) {
      setError(`Le depot a echoue : ${failure.message}`);
    } finally {
      // finally runs even on failure, so the zone never stays locked
      setUploading(false);
    }
  }

  // preventDefault stops the browser from opening the file instead of dropping it
  function handleDragOver(event) {
    event.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    handleFiles(event.dataTransfer.files);
  }

  // Sends the question, clearing the previous answer and passage while waiting
  async function handleSubmit(event) {
    // Without this, the browser reloads the whole page on form submit
    event.preventDefault();
    if (question.trim() === "") {
      return;
    }

    setError("");
    setAnswer(null);
    setPassage(null);
    setAsking(true);

    try {
      const result = await askQuestion(question);
      setAnswer(result);
    } catch (failure) {
      setError(`La question n'a pas abouti : ${failure.message}`);
    } finally {
      setAsking(false);
    }
  }

  // Opens the full source passage behind a citation, step 5 of the happy path
  async function handleOpenCitation(citation) {
    // Clicking the open citation again closes it
    if (passage && passage.id === citation.chunk_id) {
      setPassage(null);
      return;
    }

    setError("");
    setLoadingPassage(citation.chunk_id);

    try {
      const chunk = await getChunk(citation.chunk_id);
      // Keep the quote so the passage can be highlighted inside its context
      setPassage({ ...chunk, quote: citation.quote });
    } catch (failure) {
      setError(`Passage source indisponible : ${failure.message}`);
      setPassage(null);
    } finally {
      setLoadingPassage("");
    }
  }

  // Labels and classes computed before the display, to keep the markup readable
  let modeClass = "mode mode-live";
  let modeLabel = "Connecte au serveur";
  if (isMockMode()) {
    modeClass = "mode mode-mock";
    modeLabel = "Donnees de demonstration";
  }

  let dropzoneClass = "dropzone";
  if (dragging) {
    dropzoneClass = "dropzone dropzone-active";
  }

  let submitLabel = "Demander";
  if (asking) {
    submitLabel = "Recherche...";
  }

  return (
    <div className="page">
      {/* Title, tagline, and the badge telling real data from demo data */}
      <header className="header">
        <div>
          <h1>Multivers.log</h1>
          <p className="baseline">
            Depose tes documents, pose une question, obtiens une reponse sourcee.
          </p>
        </div>
        <span className={modeClass}>{modeLabel}</span>
      </header>

      {/* Single place where every failure is reported to the user */}
      {error !== "" && <p className="banner banner-error">{error}</p>}

      {/* Drop zone: a label wrapping a hidden file input, so both ways work */}
      <section className="card">
        <h2>Deposer des documents</h2>
        <label
          className={dropzoneClass}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            multiple
            onChange={(event) => handleFiles(event.target.files)}
          />
          <strong>Glisse tes fichiers ici</strong>
          <span>ou clique pour les choisir</span>
          <small>PDF, CSV, notes, captures d&apos;ecran</small>
        </label>
        {uploading && <p className="hint">Envoi en cours...</p>}
      </section>

      {/* Document list with its status badge, empty until something is uploaded */}
      <section className="card">
        <h2>Documents ({documents.length})</h2>
        {documents.length === 0 && (
          <p className="hint">Aucun document depose pour le moment.</p>
        )}
        {documents.length > 0 && (
          <ul className="documents">
            {documents.map((doc) => (
              // key lets React tell the rows apart when the list changes
              <li key={doc.id} className="document">
                <span className="filename">{doc.filename}</span>
                <span className={`status status-${doc.status}`}>
                  {statusLabel(doc.status)}
                </span>
                {doc.error_message && (
                  <span className="reason">{doc.error_message}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Tool switches: unplug one live to show the agent handling the failure */}
      {tools.length > 0 && (
        <section className="card">
          <h2>Outils de l&apos;agent</h2>
          <ul className="tools">
            {tools.map((tool) => (
              <li key={tool.name} className="tool">
                <div className="tool-head">
                  <span className="tool-name">{tool.name}</span>
                  <button
                    type="button"
                    className={toggleClass(tool.enabled)}
                    onClick={() => handleToggleTool(tool)}
                    disabled={togglingTool === tool.name}
                  >
                    {toggleLabel(tool.enabled)}
                  </button>
                </div>
                <p className="tool-description">{tool.description}</p>
              </li>
            ))}
          </ul>
          <p className="hint">
            Un outil desactive reste annonce au modele. Il l&apos;appelle, recoit une
            erreur, et doit dire qu&apos;il n&apos;a pas pu.
          </p>
        </section>
      )}

      {/* Question form, disabled while a request is in flight or the field is empty */}
      <section className="card">
        <h2>Poser une question</h2>
        <form className="ask" onSubmit={handleSubmit}>
          <input
            type="text"
            value={question}
            placeholder="Quel est le montant total facture ?"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button type="submit" disabled={asking || question.trim() === ""}>
            {submitLabel}
          </button>
        </form>
      </section>

      {/* Answer area, covering the four states: waiting, empty, refused, answered */}
      <section className="card">
        <h2>Reponse</h2>
        {asking && <p className="hint">Le serveur reflechit...</p>}
        {!asking && answer === null && (
          <p className="hint">La reponse s&apos;affichera ici.</p>
        )}
        {/* no_answer covers an empty question, a missing API key, or a failed LLM call */}
        {answer !== null && answer.no_answer && (
          <p className="banner banner-warning">{answer.message}</p>
        )}
        {answer !== null && answer.answer && (
          <div>
            <p className="answer">{answer.answer}</p>
            {answer.citations.length === 0 && (
              <p className="hint">Aucune citation rattachee a cette reponse.</p>
            )}
            {answer.citations.length > 0 && (
              <ul className="citations">
                {answer.citations.map((citation) => (
                  <li key={citation.chunk_id}>
                    {/* A button, not a div: keyboard and screen readers reach it */}
                    <button
                      type="button"
                      className="citation"
                      onClick={() => handleOpenCitation(citation)}
                    >
                      <span className="quote">{citation.quote}</span>
                      <span className="source">
                        {citation.doc_id}
                        {citation.page !== null && ` page ${citation.page}`}
                        {loadingPassage === citation.chunk_id && " · ouverture..."}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {/* Source passage, opened on demand so the user can check the citation himself */}
      {passage !== null && (
        <section className="card">
          <h2>Passage source</h2>
          <p className="passage-source">
            {passage.filename}
            {passage.page_number !== null && ` · page ${passage.page_number}`}
            {` · ${passage.id}`}
          </p>
          <p className="passage-content">{passage.content}</p>
        </section>
      )}

      {/* Tool trace, shown without any click: the checkpoint allows 30 seconds */}
      {answer !== null && answer.trace && answer.trace.length > 0 && (
        <section className="card">
          <h2>Trace des outils ({answer.trace.length})</h2>
          <ol className="trace">
            {answer.trace.map((step, index) => (
              <li key={index} className={`step step-${step.status}`}>
                <span className="step-tool">{step.tool}</span>
                <span className="step-args">{JSON.stringify(step.args)}</span>
                <span className="step-time">{step.duration_ms} ms</span>
                <span className={stepStatusClass(step.status)}>
                  {step.status}
                </span>
                {step.error && <span className="reason">{step.error}</span>}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* What the question actually cost, in tokens, money and time */}
      {answer !== null && answer.usage && (
        <section className="card">
          <h2>Cout de cette requete</h2>
          <ul className="metrics">
            <li>
              <span className="metric-value">{answer.usage.input_tokens ?? "-"}</span>
              <span className="metric-label">tokens entree</span>
            </li>
            <li>
              <span className="metric-value">{answer.usage.output_tokens ?? "-"}</span>
              <span className="metric-label">tokens sortie</span>
            </li>
            <li>
              <span className="metric-value">
                {estimateCost(answer.usage).toFixed(6)} $
              </span>
              <span className="metric-label">cout estime</span>
            </li>
            <li>
              <span className="metric-value">
                {(answer.usage.latency_ms / 1000).toFixed(2)} s
              </span>
              <span className="metric-label">latence</span>
            </li>
          </ul>
          <p className="hint">
            Estimation basee sur {PRICE_INPUT} $ par million de tokens en entree et{" "}
            {PRICE_OUTPUT} $ en sortie, reglables dans front/.env.
          </p>
        </section>
      )}
    </div>
  );
}

export default App;
