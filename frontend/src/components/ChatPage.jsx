import { useEffect, useRef, useState } from "react";
import { deleteSession, getFiles, getSession, getSessions, streamChat } from "../api";

const NOT_FOUND = "Answer not found in the documents.";

function renderAnswer(text, onCite) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      return (
        <button key={i} className="cite" onClick={() => onCite(Number(match[1]))}>
          {match[1]}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function Warnings({ warnings }) {
  if (!warnings?.length) return null;
  return (
    <div className="alert warning">
      <strong>⚠ Prompt injection warning:</strong> {warnings.length} matching chunk(s) contained suspicious
      instructions and were <strong>excluded</strong> from the AI prompt.
      {warnings.map((w, i) => (
        <details key={i} className="flag-item">
          <summary>
            {w.file_name} · page {w.page} · {w.reasons.join(", ")}
          </summary>
          <blockquote>{w.text}</blockquote>
        </details>
      ))}
    </div>
  );
}

function Message({ message }) {
  const [openSource, setOpenSource] = useState(null);
  const [uid] = useState(() => Math.random().toString(36).slice(2));

  function showSource(number) {
    setOpenSource(number);
    document.getElementById(`src-${uid}-${number}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  if (message.role === "user") {
    return <div className="msg user">{message.content}</div>;
  }
  const notFound = message.content.trim() === NOT_FOUND;
  return (
    <div className="msg assistant">
      <Warnings warnings={message.warnings} />
      <div className={`answer ${notFound ? "not-found" : ""}`}>
        {message.content ? renderAnswer(message.content, showSource) : <span className="typing">Thinking…</span>}
        {message.streaming && message.content && <span className="cursor">▍</span>}
      </div>
      {message.error && <div className="alert error">{message.error}</div>}
      {message.sources?.length > 0 && (
        <div className="sources">
          <div className="sources-title">Sources</div>
          {message.sources.map((s) => (
            <div
              key={s.number}
              id={`src-${uid}-${s.number}`}
              className={`source ${openSource === s.number ? "open" : ""}`}
            >
              <button className="source-head" onClick={() => setOpenSource(openSource === s.number ? null : s.number)}>
                <span className="cite static">{s.number}</span>
                <span className="break">
                  <strong>{s.file_name}</strong> · page {s.page}
                </span>
              </button>
              {openSource === s.number && <blockquote>{s.text}</blockquote>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [documents, setDocuments] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const bottomRef = useRef(null);

  async function refreshSessions() {
    try {
      setSessions(await getSessions());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    getSessions()
      .then(setSessions)
      .catch((err) => setError(err.message));
    getFiles()
      .then((docs) => setDocuments(docs.filter((d) => d.status === "ready")))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function openSession(id) {
    setError("");
    try {
      const data = await getSession(id);
      setSessionId(id);
      setMessages(data.messages);
    } catch (err) {
      setError(err.message);
    }
  }

  function newChat() {
    setSessionId(null);
    setMessages([]);
    setError("");
  }

  async function removeSession(id) {
    await deleteSession(id);
    if (id === sessionId) newChat();
    refreshSessions();
  }

  function updateLast(update) {
    setMessages((prev) => {
      const copy = [...prev];
      copy[copy.length - 1] = { ...copy[copy.length - 1], ...update(copy[copy.length - 1]) };
      return copy;
    });
  }

  async function ask(event) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion("");
    setError("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", sources: [], warnings: [], streaming: true },
    ]);

    try {
      await streamChat({ question: text, sessionId, documentIds: selectedDocs }, (evt) => {
        if (evt.type === "session") setSessionId(evt.session_id);
        if (evt.type === "token") updateLast((m) => ({ content: m.content + evt.text }));
        if (evt.type === "warnings") updateLast(() => ({ warnings: evt.warnings }));
        if (evt.type === "sources") updateLast(() => ({ sources: evt.sources }));
        if (evt.type === "error") updateLast(() => ({ error: evt.message }));
      });
    } catch (err) {
      updateLast(() => ({ error: err.message }));
    } finally {
      updateLast(() => ({ streaming: false }));
      setBusy(false);
      refreshSessions();
    }
  }

  function toggleDoc(id) {
    setSelectedDocs((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  }

  return (
    <div className="chat-layout">
      <aside className="sidebar">
        <button onClick={newChat} className="full">
          + New chat
        </button>
        <div className="sidebar-title">Chat history</div>
        {sessions.length === 0 && <p className="muted small">No chats yet.</p>}
        {sessions.map((s) => (
          <div key={s.id} className={`session ${s.id === sessionId ? "active" : ""}`}>
            <button className="session-title" onClick={() => openSession(s.id)} title={s.title}>
              {s.title}
            </button>
            <button className="link danger small" onClick={() => removeSession(s.id)} title="Delete chat">
              ✕
            </button>
          </div>
        ))}
      </aside>

      <section className="chat">
        {documents.length > 0 && (
          <div className="doc-filter">
            <span className="muted small">Search in:</span>
            <button className={`chip ${selectedDocs.length === 0 ? "on" : ""}`} onClick={() => setSelectedDocs([])}>
              All documents
            </button>
            {documents.map((d) => (
              <button key={d.id} className={`chip ${selectedDocs.includes(d.id) ? "on" : ""}`} onClick={() => toggleDoc(d.id)}>
                {d.name}
              </button>
            ))}
          </div>
        )}

        <div className="messages">
          {messages.length === 0 && (
            <div className="empty-chat">
              <h2>Ask a question about your documents</h2>
              <p className="muted">
                Every answer cites its sources with file name and page number. Click a number like{" "}
                <span className="cite static">1</span> to see the exact source text.
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <Message key={m.id || i} message={m} />
          ))}
          <div ref={bottomRef} />
        </div>

        {error && <div className="alert error">{error}</div>}

        <form className="ask" onSubmit={ask}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Type your question…"
            maxLength={2000}
            disabled={busy}
          />
          <button type="submit" disabled={busy || !question.trim()}>
            {busy ? "Answering…" : "Ask"}
          </button>
        </form>
      </section>
    </div>
  );
}
