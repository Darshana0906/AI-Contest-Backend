import { useState, useRef } from "react";
import axios from "axios";
import "./App.css";

const API_URL = "http://localhost:5000/api";

export default function App() {
  const [file, setFile]           = useState(null);
  const [preview, setPreview]     = useState(null);
  const [loading, setLoading]     = useState(false);
  const [results, setResults]     = useState(null);
  const [error, setError]         = useState(null);
  const fileInputRef              = useRef();

  // ── File Selection ──────────────────────────────────────────────────────────

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (!selected) return;
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setResults(null);
    setError(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;
    setFile(dropped);
    setPreview(URL.createObjectURL(dropped));
    setResults(null);
    setError(null);
  };

  // ── API Call ────────────────────────────────────────────────────────────────

  const handleScan = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(`${API_URL}/scan`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });

      if (res.data.success) {
        setResults(res.data);
      } else {
        setError(res.data.error || "Something went wrong");
      }
    } catch (err) {
      setError(err.response?.data?.error || "Could not connect to server. Is Flask running?");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setPreview(null);
    setResults(null);
    setError(null);
    fileInputRef.current.value = "";
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="app">

      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">+</span>
            <span className="logo-text">Medsaver AI</span>
          </div>
          <p className="header-tagline">Find affordable generic alternatives to branded medicines</p>
        </div>
      </header>

      <main className="main">

        {/* Upload Section */}
        {!results && (
          <div className="upload-section">
            <div
              className={`dropzone ${file ? "dropzone--has-file" : ""}`}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => fileInputRef.current.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".jpg,.jpeg,.png,.webp"
                style={{ display: "none" }}
              />
              {preview ? (
                <img src={preview} alt="Prescription preview" className="preview-img" />
              ) : (
                <div className="dropzone-placeholder">
                  <div className="upload-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="17 8 12 3 7 8"/>
                      <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                  </div>
                  <p className="dropzone-text">Click or drag prescription image here</p>
                  <p className="dropzone-subtext">Supports JPG, PNG, WEBP</p>
                </div>
              )}
            </div>

            {file && (
              <div className="file-info">
                <span className="file-name">{file.name}</span>
                <button className="btn-secondary" onClick={handleReset}>Remove</button>
              </div>
            )}

            {error && (
              <div className="error-box">
                <span className="error-icon">!</span>
                {error}
              </div>
            )}

            <button
              className="btn-primary"
              onClick={handleScan}
              disabled={!file || loading}
            >
              {loading ? (
                <span className="loading-text">
                  <span className="spinner" />
                  Analysing prescription...
                </span>
              ) : "Find Generic Alternatives"}
            </button>
          </div>
        )}

        {/* Results Section */}
        {results && (
          <div className="results-section">

            {/* Summary bar */}
            <div className="summary-bar">
              <div className="summary-stat">
                <span className="summary-label">Medicines found</span>
                <span className="summary-value">{results.total_drugs}</span>
              </div>
              <div className="summary-stat">
                <span className="summary-label">Generics available</span>
                <span className="summary-value">
                  {results.drugs.filter(d => d.generics.length > 0).length}
                </span>
              </div>
              <button className="btn-secondary" onClick={handleReset}>
                Scan another
              </button>
            </div>

            {/* Drug cards */}
            {results.drugs.map((drug, i) => (
              <DrugCard key={i} drug={drug} />
            ))}
          </div>
        )}

      </main>

      <footer className="footer">
        <p>For informational purposes only. Always consult your doctor before changing medicines.</p>
      </footer>
    </div>
  );
}


// ── Drug Card Component ───────────────────────────────────────────────────────

function DrugCard({ drug }) {
  const [expanded, setExpanded] = useState(true);
  const hasGenerics = drug.generics.length > 0;

  return (
    <div className="drug-card">

      {/* Drug header */}
      <div className="drug-header" onClick={() => setExpanded(!expanded)}>
        <div className="drug-info">
          <div className="drug-title-row">
            <h2 className="drug-brand">{drug.brand_name}</h2>
            <span className={`match-badge match-badge--${drug.match_level?.toLowerCase()}`}>
              {drug.match_level === "EXACT" ? "Exact match" :
               drug.match_level === "GOOD"  ? "Close match" :
               drug.match_level === "PARTIAL" ? "Partial match" : "No match"}
            </span>
          </div>
          <p className="drug-salt">{drug.salt_composition}</p>
          <div className="drug-meta">
            <span className="drug-tag">{drug.drug_class}</span>
            <span className="drug-tag">{drug.dosage_form}</span>
          </div>
        </div>
        <span className="expand-icon">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* Low confidence warning */}
      {drug.needs_fallback && (
        <div className="warning-box">
          Low confidence identification — please verify salt composition with your pharmacist.
        </div>
      )}

      {/* Generics table */}
      {expanded && (
        <div className="generics-section">
          {hasGenerics ? (
            <table className="generics-table">
              <thead>
                <tr>
                  <th>Generic name</th>
                  <th>Pack size</th>
                  <th>MRP</th>
                  <th>Per unit</th>
                </tr>
              </thead>
              <tbody>
                {drug.generics.map((g, j) => (
                  <tr key={j} className={j === 0 ? "row-best" : ""}>
                    <td>
                      {j === 0 && <span className="best-badge">Best match</span>}
                      {g.generic_name}
                    </td>
                    <td>{g.unit_size}</td>
                    <td>₹{g.mrp.toFixed(2)}</td>
                    <td className="price-cell">₹{g.price_per_unit.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="no-generics">
              No generics found in Jan Aushadhi database for this medicine.
            </div>
          )}
        </div>
      )}
    </div>
  );
}