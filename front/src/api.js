import mockData from "./mock.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function isMockMode() {
  return USE_MOCK;
}

function pause(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function readJson(response) {
  if (!response.ok) {
    throw new Error(`le serveur a repondu ${response.status}`);
  }
  return response.json();
}

export async function uploadDocuments(files) {
  if (USE_MOCK) {
    await pause(600);
    return files.map((file, index) => ({
      id: `doc_mock${index}`,
      filename: file.name,
      status: "processing",
      error_message: null,
    }));
  }

  const form = new FormData();
  files.forEach((file) => form.append("files", file));

  const response = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: form,
  });
  const data = await readJson(response);
  return data.documents;
}

export async function listDocuments() {
  if (USE_MOCK) {
    await pause(300);
    return mockData.documents;
  }

  const response = await fetch(`${API_URL}/documents`);
  const data = await readJson(response);
  return data.documents;
}

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
