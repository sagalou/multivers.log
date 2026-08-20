// Fake data used when the app runs without a back end
import mockData from "./mock.json";

// Read the switch and the server address from front/.env, with safe defaults
// Env variables are always strings, so "true" must be compared as text
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// A request that never ends looks exactly like a broken app, so every call has
// a deadline. Reads are quick, a question waits for the model, a report reads
// every document and needs the most room
const TIMEOUT_READ = 15000;
const TIMEOUT_ASK = 90000;
const TIMEOUT_REPORT = 180000;

// Lets the page show which mode it is running in
export function isMockMode() {
  return USE_MOCK;
}

// Fakes network latency so the mock mode behaves like the real server
function pause(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

// Wraps fetch with a deadline, and tells a timeout apart from an unreachable
// server: the user needs different advice in each case
async function request(path, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
    });
  } catch (failure) {
    if (failure.name === "AbortError") {
      throw new Error(
        `le serveur n'a pas repondu en ${Math.round(timeoutMs / 1000)} s`,
      );
    }
    throw new Error("serveur injoignable, verifie qu'il est bien lance");
  } finally {
    // Always clear the timer, even when the request succeeded
    clearTimeout(timer);
  }

  if (!response.ok) {
    throw new Error(`le serveur a repondu ${response.status}`);
  }

  return response.json();
}

// Sends the selected files to the back, or fakes the answer in mock mode
export async function uploadDocuments(files) {
  // Mock mode: build a plausible answer without calling the server
  if (USE_MOCK) {
    await pause(600);
    return files.map((file, index) => ({
      id: `doc_mock${index}`,
      filename: file.name,
      status: "processing",
      error_message: null,
    }));
  }

  // Pack the files into a multipart form, the format FastAPI expects
  const form = new FormData();
  files.forEach((file) => form.append("files", file));

  // Extraction runs during the upload, so it needs the long deadline
  const data = await request("/upload", { method: "POST", body: form }, TIMEOUT_ASK);
  return data.documents;
}

// Fetches every document and its status, used to fill the list on page load
export async function listDocuments() {
  if (USE_MOCK) {
    await pause(300);
    return mockData.documents;
  }

  const data = await request("/documents", {}, TIMEOUT_READ);
  return data.documents;
}

// Sends a natural language question and returns the raw answer object
// The answer may carry no_answer instead of a text, the caller handles both
export async function askQuestion(question) {
  if (USE_MOCK) {
    await pause(800);
    return mockData.ask;
  }

  return request(
    "/ask",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    },
    TIMEOUT_ASK,
  );
}

// Fetches one full passage, used when the user clicks a citation
export async function getChunk(chunkId) {
  if (USE_MOCK) {
    await pause(200);
    const chunk = mockData.chunks[chunkId];
    // Mirrors the 404 the real server sends for an unknown passage
    if (!chunk) {
      throw new Error(`passage ${chunkId} introuvable`);
    }
    return chunk;
  }

  return request(`/chunks/${encodeURIComponent(chunkId)}`, {}, TIMEOUT_READ);
}

// Mock mode keeps the switch states here, the real ones live on the server
const mockToolStates = mockData.tools.map((tool) => ({ ...tool }));

// Lists the agent tools and tells which ones are currently enabled
export async function listTools() {
  if (USE_MOCK) {
    await pause(150);
    return mockToolStates.map((tool) => ({ ...tool }));
  }

  const data = await request("/tools", {}, TIMEOUT_READ);
  return data.tools;
}

// Switches one tool on or off, returning the full list back
export async function setToolEnabled(name, enabled) {
  if (USE_MOCK) {
    await pause(150);
    const tool = mockToolStates.find((item) => item.name === name);
    if (tool) {
      tool.enabled = enabled;
    }
    return mockToolStates.map((item) => ({ ...item }));
  }

  const data = await request(
    `/tools/${encodeURIComponent(name)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    },
    TIMEOUT_READ,
  );
  return data.tools;
}

// Asks for a written summary of the whole corpus, step 6 of the happy path
// The server reads a sample of every document, so this one is the slowest
export async function generateReport() {
  if (USE_MOCK) {
    await pause(1200);
    return mockData.report;
  }

  return request(
    "/report",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "synthese du corpus" }),
    },
    TIMEOUT_REPORT,
  );
}

// Removes one document, its passages and its file on disk
export async function deleteDocument(docId) {
  if (USE_MOCK) {
    await pause(200);
    return { deleted: docId };
  }

  return request(`/documents/${encodeURIComponent(docId)}`, { method: "DELETE" }, TIMEOUT_READ);
}

// Empties the whole corpus, to start a demo from a clean list
export async function deleteAllDocuments() {
  if (USE_MOCK) {
    await pause(300);
    return { deleted_count: mockData.documents.length };
  }

  return request("/documents", { method: "DELETE" }, TIMEOUT_READ);
}
