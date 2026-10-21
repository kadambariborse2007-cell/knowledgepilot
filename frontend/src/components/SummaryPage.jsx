import { useEffect, useState } from "react";
import { getFiles, getSummary } from "../api";

export default function SummaryPage() {
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState("");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getFiles()
      .then((docs) => {
        const ready = docs.filter((d) => d.status === "ready");
        setDocuments(ready);
        if (ready.length) setSelected(String(ready[0].id));
      })
      .catch((err) => setError(err.message));
  }, []);

  async function generate(refresh = false) {
    setLoading(true);
    setError("");
    setSummary(null);
    try {
      setSummary(await getSummary(selected, refresh));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h2>Whole-document summary</h2>
      <p className="muted">
        Uses <strong>map-reduce</strong>: each section is summarised separately (map), then the partial summaries are
        combined into one (reduce). Flagged chunks are skipped.
      </p>
      {documents.length === 0 ? (
        <p className="muted">Upload a document first.</p>
      ) : (
        <div className="row">
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.pages} pages)
              </option>
            ))}
          </select>
          <button onClick={() => generate(false)} disabled={loading || !selected}>
            {loading ? "Summarising…" : "Summarise"}
          </button>
        </div>
      )}
      {loading && <p className="muted">This can take up to a minute for long documents.</p>}
      {error && <div className="alert error">{error}</div>}
      {summary && (
        <div className="summary">
          <div className="summary-meta muted small">
            {summary.cached ? "Saved summary" : `Generated with ${summary.map_calls} map step(s)`}
            {summary.cached && (
              <button className="link" onClick={() => generate(true)}>
                Regenerate
              </button>
            )}
          </div>
          <div className="pre">{summary.summary}</div>
        </div>
      )}
    </div>
  );
}
