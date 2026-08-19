import { useEffect, useState } from "react";
import { askQuestion, isMockMode, listDocuments, uploadDocuments } from "./api";
import "./App.css";

// Maps the raw status sent by the back to the wording shown on screen
const STATUS_LABELS = {
  processing: "en cours",
  processed: "traite",
  error: "erreur",
};

// Falls back to the raw value if the back ever sends an unknown status
function statusLabel(status) {
  if (STATUS_LABELS[status]) {
    return STATUS_LABELS[status];
  }
  return status;
}

function App() {
  // Everything the page displays lives in these seven states
  // Changing one of them makes React redraw the affected part of the page
  const [documents, setDocuments] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [dragging, setDragging] = useState(false);

  // Reloads the document list from the server, after an upload or on page load
  async function refreshDocuments() {
    try {
      const list = await listDocuments();
      setDocuments(list);
    } catch (failure) {
      setError(`Liste des documents indisponible : ${failure.message}`);
    }
  }

  // Empty brackets mean: run this once, when the page opens
  useEffect(() => {
    refreshDocuments();
  }, []);

  // Handles both ways of picking files: the file dialog and the drop zone
  async function handleFiles(fileList) {
    // A FileList is not an array, Array.from makes it usable with map and forEach
    const files = Array.from(fileList);
    if (files.length === 0) {
      return;
    }

    // Clear the previous error and lock the zone while the upload runs
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

  // Sends the question, keeping the previous answer hidden while waiting
  async function handleSubmit(event) {
    // Without this, the browser reloads the whole page on form submit
    event.preventDefault();
    if (question.trim() === "") {
      return;
    }

    setError("");
    setAnswer(null);
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
            {/* Citations stay empty until search is wired into /ask */}
            {answer.citations.length === 0 && (
              <p className="hint">Aucune citation rattachee a cette reponse.</p>
            )}
            {answer.citations.length > 0 && (
              <ul className="citations">
                {answer.citations.map((citation) => (
                  <li key={citation.chunk_id} className="citation">
                    <span className="quote">{citation.quote}</span>
                    <span className="source">
                      {citation.doc_id}
                      {citation.page !== null && ` page ${citation.page}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default App;
