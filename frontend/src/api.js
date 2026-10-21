export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function readError(response) {
  try {
    const data = await response.json();
    return data.error || data.detail || JSON.stringify(data);
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) throw new Error(await readError(response));
  if (response.status === 204) return null;
  return response.json();
}

function jsonBody(method, body) {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const checkHealth = () => request("/api/health/");
export const getFiles = () => request("/api/files/").then((d) => d.files);
export const deleteFile = (id) => request(`/api/files/${id}/`, { method: "DELETE" });
export const getFlagged = (id) => request(`/api/files/${id}/flagged/`).then((d) => d.flagged);
export const getSummary = (id, refresh = false) => request(`/api/files/${id}/summary/`, jsonBody("POST", { refresh }));
export const getSessions = () => request("/api/sessions/").then((d) => d.sessions);
export const getSession = (id) => request(`/api/sessions/${id}/`);
export const deleteSession = (id) => request(`/api/sessions/${id}/`, { method: "DELETE" });
export const getTestset = () => request("/api/eval/testset/").then((d) => d.items);
export const saveTestset = (items) => request("/api/eval/testset/", jsonBody("PUT", { items })).then((d) => d.items);
export const runEvaluation = () => request("/api/eval/run/", { method: "POST" });
export const getEvalStatus = () => request("/api/eval/status/");

export function uploadFiles(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return request("/api/upload/", { method: "POST", body: formData });
}

// Streams the answer. onEvent is called for every event sent by the backend:
// session, warnings, token, sources, error, done.
export async function streamChat({ question, sessionId, documentIds }, onEvent) {
  const response = await fetch(`${API_BASE_URL}/api/chat/`, jsonBody("POST", {
    question,
    session_id: sessionId,
    document_ids: documentIds,
  }));
  if (!response.ok) throw new Error(await readError(response));

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}
