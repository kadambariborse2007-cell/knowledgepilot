import { useEffect, useState } from "react";
import { checkHealth } from "./api";
import DocumentsPage from "./components/DocumentsPage";
import ChatPage from "./components/ChatPage";
import SummaryPage from "./components/SummaryPage";
import EvaluationPage from "./components/EvaluationPage";
import "./App.css";

const TABS = [
  { id: "documents", label: "Documents" },
  { id: "chat", label: "Ask Questions" },
  { id: "summary", label: "Summary" },
  { id: "evaluation", label: "Evaluation" },
];

export default function App() {
  const [tab, setTab] = useState("documents");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    checkHealth()
      .then((data) => setHealth({ online: true, gemini: data.gemini_configured }))
      .catch(() => setHealth({ online: false }));
  }, []);

  let statusClass = "checking";
  let statusText = "Connecting to backend... (free server may take ~1 min to wake up)";
  if (health?.online) {
    statusClass = health.gemini ? "online" : "warn";
    statusText = health.gemini ? "Backend online" : "Backend online - Gemini key missing";
  } else if (health) {
    statusClass = "offline";
    statusText = "Backend offline";
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">KP</span>
          <div>
            <h1>KnowledgePilot AI</h1>
            <p>Evidence-grounded document research assistant</p>
          </div>
        </div>
        <span className={`status ${statusClass}`}>{statusText}</span>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      <main className="content">
        {tab === "documents" && <DocumentsPage />}
        {tab === "chat" && <ChatPage />}
        {tab === "summary" && <SummaryPage />}
        {tab === "evaluation" && <EvaluationPage />}
      </main>

      <footer className="footer">
        Answers are generated only from your uploaded documents. This reduces hallucination but is not 100% accurate -
        always verify an answer using its sources.
      </footer>
    </div>
  );
}
