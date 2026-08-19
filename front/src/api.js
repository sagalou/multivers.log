// Fake data used when the app runs without a back end
import mockData from "./mock.json";

// Read the switch and the server address from front/.env, with safe defaults
// Env variables are always strings, so "true" must be compared as text
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Lets the page show which mode it is running in
export function isMockMode() {
  return USE_MOCK;
}

// Fakes network latency so the mock mode behaves like the real server
function pause(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

// Turns any failed request into a readable error instead of a silent undefined
async function readJson(response) {
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

  // Send them, then keep only the documents list from the answer
  const response = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: form,
  });
  const data = await readJson(response);
  return data.documents;
}

// Fetches every document and its status, used to fill the list on page load
export async function listDocuments() {
  if (USE_MOCK) {
    await pause(300);
    return mockData.documents;
  }

  const response = await fetch(`${API_URL}/documents`);
  const data = await readJson(response);
  return data.documents;
}

// Sends a natural language question and returns the raw answer object
// The answer may carry no_answer instead of a text, the caller handles both
export async function askQuestion(question) {
  if (USE_MOCK) {
    await pause(800);
    return mockData.ask;
  }

  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return readJson(response);
}
