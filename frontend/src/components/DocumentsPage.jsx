import { Fragment, useEffect, useRef, useState } from "react";
import { deleteFile, getFiles, getFlagged, uploadFiles } from "../api";

const ALLOWED_EXTENSIONS = [".pdf", ".txt"];
const MAX_FILES = 10;
const MAX_SIZE_MB = 20;

function formatSize(bytes) {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function validateFiles(files) {
  if (files.length === 0) return "Please select at least one file.";
  if (files.length > MAX_FILES) return `You can upload at most ${MAX_FILES} files at once.`;
  for (const file of files) {
    const name = file.name.toLowerCase();
    if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      return `"${file.name}" is not allowed. Only PDF and TXT files are supported.`;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) return `"${file.name}" is larger than ${MAX_SIZE_MB} MB.`;
  }
  return null;
}

export default function DocumentsPage() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [flagged, setFlagged] = useState({});
  const inputRef = useRef(null);

  async function loadFiles() {
    try {
      setDocuments(await getFiles());
    } catch (err) {
      setError(`Could not load files: ${err.message}`);
    }
  }

  useEffect(() => {
    getFiles()
      .then(setDocuments)
      .catch((err) => setError(`Could not load files: ${err.message}`));
  }, []);

  function handleSelect(fileList) {
    const files = Array.from(fileList);
    setSuccess("");
    const validationError = validateFiles(files);
    setError(validationError || "");
    setSelectedFiles(validationError ? [] : files);
  }

  async function handleUpload() {
    setIsUploading(true);
    setError("");
    setSuccess("");
    try {
      const result = await uploadFiles(selectedFiles);
      const failed = result.uploaded.filter((d) => d.status === "error" || d.status === "empty");
      const flaggedCount = result.uploaded.reduce((sum, d) => sum + d.flagged_chunks, 0);
      let message = `${result.uploaded.length - failed.length} file(s) uploaded and indexed.`;
      if (flaggedCount) message += ` ${flaggedCount} suspicious chunk(s) were flagged and will be kept out of answers.`;
      setSuccess(message);
      if (failed.length) setError(failed.map((d) => `${d.name}: ${d.error}`).join(" | "));
      setSelectedFiles([]);
      if (inputRef.current) inputRef.current.value = "";
      await loadFiles();
    } catch (err) {
      setError(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.name}"?`)) return;
    try {
      await deleteFile(doc.id);
      await loadFiles();
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  }

  async function toggleFlagged(doc) {
    if (flagged[doc.id]) {
      setFlagged((f) => ({ ...f, [doc.id]: null }));
      return;
    }
    try {
      const items = await getFlagged(doc.id);
      setFlagged((f) => ({ ...f, [doc.id]: items }));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <div
        className={`dropzone ${isDragging ? "dragging" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleSelect(e.dataTransfer.files);
        }}
      >
        <p className="dropzone-title">Drag & drop files here, or click to browse</p>
        <p className="muted">
          PDF or TXT only · max {MAX_FILES} files · max {MAX_SIZE_MB} MB each · scanned PDFs (images) are not supported
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.txt"
          hidden
          onChange={(e) => handleSelect(e.target.files)}
        />
      </div>

      {selectedFiles.length > 0 && (
        <div className="card">
          <h2>Selected files ({selectedFiles.length})</h2>
          <ul className="file-list">
            {selectedFiles.map((file) => (
              <li key={file.name}>
                <span>{file.name}</span>
                <span className="muted">{formatSize(file.size)}</span>
              </li>
            ))}
          </ul>
          <button onClick={handleUpload} disabled={isUploading}>
            {isUploading ? "Uploading & indexing..." : "Upload"}
          </button>
        </div>
      )}

      {error && <div className="alert error">{error}</div>}
      {success && <div className="alert success">{success}</div>}

      <div className="card">
        <div className="card-header">
          <h2>Your documents ({documents.length})</h2>
          <button className="secondary" onClick={loadFiles}>
            Refresh
          </button>
        </div>
        {documents.length === 0 ? (
          <p className="muted">No documents yet. Upload a PDF or TXT file to get started.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>File</th>
                <th>Size</th>
                <th>Pages</th>
                <th>Chunks</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <Fragment key={doc.id}>
                  <tr>
                    <td className="break">{doc.name}</td>
                    <td>{formatSize(doc.size)}</td>
                    <td>{doc.pages}</td>
                    <td>{doc.chunks}</td>
                    <td>
                      <span className={`badge ${doc.status}`}>{doc.status}</span>
                      {doc.flagged_chunks > 0 && (
                        <button className="badge flagged" onClick={() => toggleFlagged(doc)} title="Show flagged chunks">
                          ⚠ {doc.flagged_chunks} flagged
                        </button>
                      )}
                    </td>
                    <td>
                      <button className="link danger" onClick={() => handleDelete(doc)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                  {doc.error && (
                    <tr>
                      <td colSpan={6} className="muted">
                        {doc.error}
                      </td>
                    </tr>
                  )}
                  {flagged[doc.id] && (
                    <tr>
                      <td colSpan={6}>
                        <div className="alert warning">
                          <strong>Possible prompt injection.</strong> These chunks look like instructions aimed at the AI.
                          They are excluded from the LLM prompt.
                          {flagged[doc.id].map((f, i) => (
                            <div key={i} className="flag-item">
                              <div className="muted">
                                Page {f.page} · {f.reasons.join(", ")}
                              </div>
                              <blockquote>{f.text}</blockquote>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
