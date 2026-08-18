import { useEffect, useState } from "react";
import { askQuestion, isMockMode, listDocuments, uploadDocuments } from "./api";
import "./App.css";

const STATUS_LABELS = {
  processing: "en cours",
  processed: "traite",
  error: "erreur",
};

function statusLabel(status) {
  if (STATUS_LABELS[status]) {
    return STATUS_LABELS[status];
  }
  return status;
}

function App() {
  const [documents, setDocuments] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [dragging, setDragging] = useState(false);

  async function refreshDocuments() {
    try {
      const list = await listDocuments();
      setDocuments(list);
    } catch (failure) {
      setError(`Liste des documents indisponible : ${failure.message}`);
    }
  }

  useEffect(() => {
    refreshDocuments();
  }, []);

  async function handleFiles(fileList) {
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
      setUploading(false);
    }
  }

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

  async function handleSubmit(event) {
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
      <header className="header">
        <div>
          <h1>Multivers.log</h1>
          <p className="baseline">
            Depose tes documents, pose une question, obtiens une reponse sourcee.
          </p>
        </div>
        <span className={modeClass}>{modeLabel}</span>
      </header>

      {error !== "" && <p className="banner banner-error">{error}</p>}

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

      <section className="card">
        <h2>Documents ({documents.length})</h2>
        {documents.length === 0 && (
          <p className="hint">Aucun document depose pour le moment.</p>
        )}
        {documents.length > 0 && (
          <ul className="documents">
            {documents.map((doc) => (
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

      <section className="card">
        <h2>Reponse</h2>
        {asking && <p className="hint">Le serveur reflechit...</p>}
        {!asking && answer === null && (
          <p className="hint">La reponse s&apos;affichera ici.</p>
        )}
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
