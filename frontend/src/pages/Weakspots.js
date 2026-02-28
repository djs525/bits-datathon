import React, { useState } from "react";
import { api } from "../api";
import { ZipCard, Loader, EmptyState, RiskBadge } from "../components/ui";

export default function Weakspots({ cuisines }) {
  const [cuisine, setCuisine] = useState("");
  const [minClosure, setMinClosure] = useState(0.25);
  const [maxStars, setMaxStars] = useState(5.0);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const data = await api.getWeakspots({
        cuisine: cuisine || undefined,
        min_closure_rate: minClosure,
        max_avg_stars: maxStars,
        min_existing: cuisine ? 1 : 0,
      });
      setResults(data);
    } finally { setLoading(false); }
  };

  return (
    <div style={{ padding: "32px 40px", maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 6 }}>
          Weak Spot Finder
        </div>
        <div style={{ fontFamily: "DM Mono, monospace", fontSize: 12, color: "#6b6b8a" }}>
          Where is existing competition failing? High closure + low quality = frustrated demand waiting to be captured.
        </div>
      </div>

      <div style={{ background: "#12121a", border: "1px solid #2a2a3a", borderRadius: 14, padding: 28, marginBottom: 28 }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div>
            <Label>Cuisine to Evaluate</Label>
            <select value={cuisine} onChange={e => setCuisine(e.target.value)} style={sel}>
              <option value="">Any (worst performing overall)</option>
              {cuisines.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>

          <div>
            <Label>Min Closure Rate</Label>
            <div style={{ display: "flex", gap: 6 }}>
              {[["0.2", "20%+"], ["0.25", "25%+"], ["0.35", "35%+"], ["0.45", "45%+"]].map(([v, label]) => (
                <button key={v} onClick={() => setMinClosure(v)} style={{
                  background: String(minClosure) === v ? "rgba(255,108,108,0.12)" : "#0a0a0f",
                  border: `1px solid ${String(minClosure) === v ? "#ff6c6c" : "#2a2a3a"}`,
                  color: String(minClosure) === v ? "#ff6c6c" : "#6b6b8a",
                  borderRadius: 8, padding: "8px 14px", cursor: "pointer",
                  fontFamily: "DM Mono, monospace", fontSize: 11, transition: "all 0.15s",
                }}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label>Max Avg Quality (weaker = better opp)</Label>
            <div style={{ display: "flex", gap: 6 }}>
              {[["3.0", "Under 3★"], ["3.5", "Under 3.5★"], ["5.0", "Any"]].map(([v, label]) => (
                <button key={v} onClick={() => setMaxStars(v)} style={{
                  background: String(maxStars) === v ? "rgba(255,209,102,0.1)" : "#0a0a0f",
                  border: `1px solid ${String(maxStars) === v ? "#ffd166" : "#2a2a3a"}`,
                  color: String(maxStars) === v ? "#ffd166" : "#6b6b8a",
                  borderRadius: 8, padding: "8px 14px", cursor: "pointer",
                  fontFamily: "DM Mono, monospace", fontSize: 11, transition: "all 0.15s",
                }}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button onClick={run} style={{
          background: "#ff6c6c", border: "none", borderRadius: 10,
          color: "#fff", fontFamily: "Syne, sans-serif", fontSize: 14, fontWeight: 800,
          padding: "12px 32px", cursor: "pointer", marginTop: 20, width: "100%",
        }}>
          Find Weak Spots →
        </button>
      </div>

      {loading ? <Loader text="Scanning for weak competition…" /> :
       results ? (
         <>
           <div style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color: "#6b6b8a", marginBottom: 12 }}>
             {results.count} zip codes with weak competition
           </div>
           {results.results.length === 0
             ? <EmptyState icon="💪" text="No weak spots found with these filters.\nTry loosening the closure rate threshold." />
             : <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                 {results.results.map(z => (
                   <div key={z.zip}>
                     <ZipCard z={z} />
                     {z.weak_competitor_signal && (
                       <div style={{
                         marginTop: -4, marginBottom: 4, padding: "8px 16px",
                         background: "rgba(255,108,108,0.06)", border: "1px solid rgba(255,108,108,0.2)",
                         borderTop: "none", borderRadius: "0 0 10px 10px",
                         fontFamily: "DM Mono, monospace", fontSize: 10, color: "#ff6c6c",
                       }}>
                         ⚠ {z.existing_count} existing {cuisine || "restaurant"}(s) — high demand, poor execution
                       </div>
                     )}
                   </div>
                 ))}
               </div>
           }
         </>
       ) : null}
    </div>
  );
}

function Label({ children }) {
  return <div style={{ fontFamily: "DM Mono, monospace", fontSize: 10, color: "#6b6b8a", letterSpacing: "0.8px", textTransform: "uppercase", marginBottom: 8 }}>{children}</div>;
}

const sel = {
  background: "#0a0a0f", border: "1px solid #2a2a3a", borderRadius: 8,
  color: "#e8e8f0", fontFamily: "Syne, sans-serif", fontSize: 13,
  padding: "8px 12px", outline: "none", cursor: "pointer", minWidth: 200,
};
