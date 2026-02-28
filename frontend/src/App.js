import React, { useState, useEffect } from "react";
import { api } from "./api";
import Opportunities from "./pages/Opportunities";
import Search from "./pages/Search";
import Weakspots from "./pages/Weakspots";

const PAGES = [
  { id: "opportunities", label: "Where to Open?", icon: "📍" },
  { id: "search", label: "Concept Search", icon: "🔍" },
  { id: "weakspots", label: "Weak Spots", icon: "⚠️" },
];

export default function App() {
  const [page, setPage] = useState("opportunities");
  const [cuisines, setCuisines] = useState([]);

  useEffect(() => {
    api.getCuisines().then(d => setCuisines(d.cuisines)).catch(() => {});
  }, []);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0a0f; color: #e8e8f0; font-family: 'Syne', sans-serif; }
        select, button, input { font-family: inherit; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2a3a; border-radius: 2px; }
      `}</style>

      <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
        {/* ── Header ── */}
        <header style={{
          display: "flex", alignItems: "center", gap: 32,
          padding: "0 32px", height: 60, flexShrink: 0,
          background: "#0d0d18", borderBottom: "1px solid #2a2a3a",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "linear-gradient(135deg, #00e5a0, #7c6cff)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
            }}>📍</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: -0.3 }}>
                NJ <span style={{ color: "#00e5a0" }}>Market Gap</span>
              </div>
              <div style={{ fontFamily: "DM Mono, monospace", fontSize: 9, color: "#6b6b8a", letterSpacing: "0.5px" }}>
                RESTAURANT OPPORTUNITY DETECTOR
              </div>
            </div>
          </div>

          <nav style={{ display: "flex", gap: 4, marginLeft: 16 }}>
            {PAGES.map(p => (
              <button key={p.id} onClick={() => setPage(p.id)} style={{
                background: page === p.id ? "rgba(0,229,160,0.1)" : "transparent",
                border: `1px solid ${page === p.id ? "rgba(0,229,160,0.35)" : "transparent"}`,
                color: page === p.id ? "#00e5a0" : "#6b6b8a",
                borderRadius: 8, padding: "6px 14px", cursor: "pointer",
                fontFamily: "Syne, sans-serif", fontSize: 13, fontWeight: page === p.id ? 700 : 400,
                transition: "all 0.15s", display: "flex", alignItems: "center", gap: 6,
              }}>
                <span>{p.icon}</span> {p.label}
              </button>
            ))}
          </nav>

          <div style={{ marginLeft: "auto", fontFamily: "DM Mono, monospace", fontSize: 10, color: "#2a2a3a" }}>
            POWERED BY YELP ACADEMIC DATASET · NJ · 3,341 RESTAURANTS · 91 ZIP CODES
          </div>
        </header>

        {/* ── Page content ── */}
        <main style={{ flex: 1, overflow: "hidden" }}>
          {page === "opportunities" && <Opportunities cuisines={cuisines} />}
          {page === "search" && <Search cuisines={cuisines} />}
          {page === "weakspots" && <Weakspots cuisines={cuisines} />}
        </main>
      </div>
    </>
  );
}
