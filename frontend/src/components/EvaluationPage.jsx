import { useEffect, useRef, useState } from "react";
import { getEvalStatus, getTestset, runEvaluation, saveTestset } from "../api";

const METRICS = [
  { key: "faithfulness", label: "Faithfulness", help: "Is every claim in the answer supported by the retrieved context?" },
  { key: "answer_relevancy", label: "Answer relevancy", help: "Does the answer actually address the question?" },
  { key: "context_precision", label: "Context precision", help: "Are the relevant chunks ranked at the top of the retrieved results?" },
  { key: "context_recall", label: "Context recall", help: "Does the retrieved context contain everything needed for the expected answer?" },
];

function score(value) {
  return value == null ? "n/a" : value.toFixed(2);
}

function level(value) {
  if (value == null) return "na";
  if (value >= 0.8) return "good";
  if (value >= 0.5) return "mid";
  return "low";
}

export default function EvaluationPage() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const timer = useRef(null);

  async function poll() {
    try {
      const data = await getEvalStatus();
      setStatus(data);
      if (data.running) timer.current = setTimeout(poll, 4000);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    getTestset()
      .then(setItems)
      .catch((err) => setError(err.message));
    poll();
    return () => clearTimeout(timer.current);
  }, []);

  function update(index, field, value) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, [field]: value } : item)));
  }

  async function save() {
    setError("");
    try {
      const saved = await saveTestset(items);
      setItems(saved);
      setMessage(`Saved ${saved.length} question(s).`);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  }

  async function run() {
    setMessage("");
    if (!(await save())) return;
    try {
      await runEvaluation();
      poll();
    } catch (err) {
      setError(err.message);
    }
  }

  const results = status?.results;

  return (
    <div>
      <div className="card">
        <h2>RAGAS evaluation</h2>
        <p className="muted">
          Each metric is reported <strong>separately</strong> (0 to 1, higher is better). They are not combined into one
          accuracy score. Scores are judged by an LLM, so treat them as indicators, not exact truth.
        </p>
        {results ? (
          <>
            <div className="metrics">
              {METRICS.map((m) => (
                <div key={m.key} className={`metric ${level(results.metrics[m.key])}`}>
                  <div className="metric-value">{score(results.metrics[m.key])}</div>
                  <div className="metric-label">{m.label}</div>
                  <div className="metric-help">{m.help}</div>
                </div>
              ))}
            </div>
            <p className="muted small">
              Last run: {new Date(results.run_at).toLocaleString()} · {results.num_questions} question(s) · model{" "}
              {results.model}
            </p>
          </>
        ) : (
          <p className="muted">No evaluation has been run yet.</p>
        )}
        {status?.running && <div className="alert info">Running: {status.progress}</div>}
        {status?.error && !status.running && <div className="alert error">Last run failed: {status.error}</div>}
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Test set ({items.length})</h2>
          <div className="row">
            <button className="secondary" onClick={() => setItems([...items, { question: "", ground_truth: "" }])}>
              + Add question
            </button>
            <button className="secondary" onClick={save}>
              Save
            </button>
            <button onClick={run} disabled={status?.running || items.length === 0}>
              {status?.running ? "Running…" : "Run evaluation"}
            </button>
          </div>
        </div>
        <p className="muted small">
          Write your own questions and the expected (ground-truth) answers from your uploaded documents. The example
          questions are about <code>sample_docs/knowledgepilot_overview.txt</code> - upload it or replace them.
        </p>
        {message && <div className="alert success">{message}</div>}
        {error && <div className="alert error">{error}</div>}
        {items.map((item, i) => (
          <div key={i} className="test-item">
            <div className="test-num">{i + 1}</div>
            <div className="test-fields">
              <input
                value={item.question}
                placeholder="Question"
                onChange={(e) => update(i, "question", e.target.value)}
              />
              <textarea
                value={item.ground_truth}
                placeholder="Expected answer (ground truth)"
                rows={2}
                onChange={(e) => update(i, "ground_truth", e.target.value)}
              />
            </div>
            <button className="link danger" onClick={() => setItems(items.filter((_, j) => j !== i))}>
              ✕
            </button>
          </div>
        ))}
      </div>

      {results?.per_question?.length > 0 && (
        <div className="card">
          <h2>Per-question results</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Answer</th>
                  {METRICS.map((m) => (
                    <th key={m.key}>{m.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.per_question.map((q, i) => (
                  <tr key={i}>
                    <td>{q.question}</td>
                    <td className="small">{q.answer}</td>
                    {METRICS.map((m) => (
                      <td key={m.key}>
                        <span className={`pill ${level(q[m.key])}`}>{score(q[m.key])}</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
