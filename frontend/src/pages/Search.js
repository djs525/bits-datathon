import React, { useState } from "react";
import { api } from "../api";
import { ZipCard, Loader, EmptyState } from "../components/ui";

const ATTRS = ["BYOB", "Delivery", "Outdoor Seating", "Kid-Friendly", "Late Night", "Free WiFi", "Reservations"];

export default function Search({ cuisines }) {
  const [cuisine, setCuisine] = useState("");
  const [attrs, setAttrs] = useState({});
  const [maxPrice, setMaxPrice] = useState("");
  const [minMarket, setMinMarket] = useState(500);
  const [maxRisk, setMaxRisk] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const toggleAttr = (a) => setAttrs(prev => ({ ...prev, [a]: !prev[a] }));

  const run = async () => {
    setLoading(true);
    const params = {
      cuisine, min_market_size: minMarket,
      max_risk: maxRisk || undefined,
      max_price_tier: maxPrice || undefined,
    };
    ATTRS.forEach(a => { if (attrs[a]) params[a.toLowerCase().replace(/ /g, "_")] = true; });

    // map to API param names
    const apiParams = {
      cuisine: params.cuisine || undefined,
      min_market_size: params.min_market_size,
      max_risk: params.max_risk,
      max_price_tier: params.max_price_tier,
      byob: attrs["BYOB"] || undefined,
      delivery: attrs["Delivery"] || undefined,
      outdoor: attrs["Outdoor Seating"] || undefined,
      late_night: attrs["Late Night"] || undefined,
      kid_friendly: attrs["Kid-Friendly"] || undefined,
    };

    try {
      const data = await api.search(apiParams);
      setResults(data);
    } finally { setLoading(false); }
  };

  return (
    <div style={{ padding: "32px 40px", maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 6 }}>
          Concept Search
        </div>
        <div style={{ fontFamily: "DM Mono, monospace", fontSize: 12, color: "#6b6b8a" }}>
          "I want to open a _____ restaurant that offers _____. Where?"
        </div>
      </div>

      {/* builder */}
      <div style={{
        background: "#12121a", border: "1px solid #2a2a3a", borderRadius: 14,
        padding: 28, marginBottom: 28,
      }}>
        <Row label="Cuisine Type">
          <select value={cuisine} onChange={e => setCuisine(e.target.value)} style={sel}>
            <option value="">Any cuisine</option>
            {cuisines.map(c => <option key={c}>{c}</option>)}
          </select>
        </Row>

        <Row label="Must Offer (attribute gaps)">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {ATTRS.map(a => (
              <button key={a} onClick={() => toggleAttr(a)} style={{
                background: attrs[a] ? "rgba(0,229,160,0.12)" : "#0a0a0f",
                border: `1px solid ${attrs[a] ? "#00e5a0" : "#2a2a3a"}`,
                color: attrs[a] ? "#00e5a0" : "#6b6b8a",
                borderRadius: 20, padding: "6px 14px", cursor: "pointer",
                fontFamily: "DM Mono, monospace", fontSize: 11, transition: "all 0.15s",
              }}>
                {attrs[a] ? "✓ " : ""}{a}
              </button>
            ))}
          </div>
        </Row>

        <Row label="Price Market">
          <div style={{ display: "flex", gap: 8 }}>
            {[["", "Any"], ["1", "$ Budget"], ["2", "$$ Mid"], ["3", "$$$ Upscale"]].map(([v, label]) => (
              <button key={v} onClick={() => setMaxPrice(v)} style={{
                background: maxPrice === v ? "rgba(124,108,255,0.12)" : "#0a0a0f",
                border: `1px solid ${maxPrice === v ? "#7c6cff" : "#2a2a3a"}`,
                color: maxPrice === v ? "#7c6cff" : "#6b6b8a",
                borderRadius: 8, padding: "6px 14px", cursor: "pointer",
                fontFamily: "DM Mono, monospace", fontSize: 11, transition: "all 0.15s",
              }}>
                {label}
              </button>
            ))}
          </div>
        </Row>

        <Row label="Risk Tolerance">
          <div style={{ display: "flex", gap: 8 }}>
            {[["", "Any"], ["low", "Low only"], ["medium", "Low / Medium"]].map(([v, label]) => (
              <button key={v} onClick={() => setMaxRisk(v)} style={{
                background: maxRisk === v ? "rgba(255,209,102,0.1)" : "#0a0a0f",
                border: `1px solid ${maxRisk === v ? "#ffd166" : "#2a2a3a"}`,
                color: maxRisk === v ? "#ffd166" : "#6b6b8a",
                borderRadius: 8, padding: "6px 14px", cursor: "pointer",
                fontFamily: "DM Mono, monospace", fontSize: 11, transition: "all 0.15s",
              }}>
                {label}
              </button>
            ))}
          </div>
        </Row>

        <Row label="Minimum Market Size">
          <select value={minMarket} onChange={e => setMinMarket(e.target.value)} style={sel}>
            <option value="0">No minimum</option>
            <option value="500">500+ reviews</option>
            <option value="1000">1,000+ reviews</option>
            <option value="3000">3,000+ reviews</option>
            <option value="5000">5,000+ reviews</option>
          </select>
        </Row>

        <button onClick={run} style={{
          background: "#00e5a0", border: "none", borderRadius: 10,
          color: "#000", fontFamily: "Syne, sans-serif", fontSize: 14, fontWeight: 800,
          padding: "12px 32px", cursor: "pointer", marginTop: 8, width: "100%",
          letterSpacing: -0.3,
        }}>
          Find My Market →
        </button>
      </div>

      {/* results */}
      {loading ? <Loader text="Scanning 91 zip codes…" /> :
       results ? (
         <>
           <div style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color: "#6b6b8a", marginBottom: 12 }}>
             {results.count} matching zip codes
           </div>
           <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
             {results.results.length === 0
               ? <EmptyState text="No matches.\nTry loosening your filters — fewer required attributes or wider risk tolerance." />
               : results.results.map(z => <ZipCard key={z.zip} z={z} />)
             }
           </div>
         </>
       ) : null}
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontFamily: "DM Mono, monospace", fontSize: 10, color: "#6b6b8a", letterSpacing: "0.8px", textTransform: "uppercase", marginBottom: 10 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

const sel = {
  background: "#0a0a0f", border: "1px solid #2a2a3a", borderRadius: 8,
  color: "#e8e8f0", fontFamily: "Syne, sans-serif", fontSize: 13,
  padding: "8px 12px", outline: "none", cursor: "pointer", minWidth: 160,
};
