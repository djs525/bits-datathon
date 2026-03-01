import React, { useState, useEffect } from "react";
import { api } from "./api";
import Opportunities from "./pages/Opportunities";
import Recommendations from "./pages/Recommendations";
import Predict from "./pages/Predict";

const PAGES = [
  { id: "opportunities", label: "Market Gaps", icon: "📍" },
  { id: "recommendations", label: "Recommendations", icon: "🎯" },
  { id: "predict", label: "Survival Predictor", icon: "🧠" },
];

export default function App() {
  const [page, setPage] = useState("opportunities");
  const [cuisines, setCuisines] = useState([]);

  useEffect(() => {
    api.getCuisines().then(d => setCuisines(d.cuisines)).catch(() => { });
  }, []);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        
        :root {
          --bg: #FFFFFF;
          --text-main: #222222;
          --text-secondary: #717171;
          --primary: #FF385C;
          --border: #DDDDDD;
          --header-bg: #FFFFFF;
          --header-border: #EBEBEB;
          --shadow: 0 6px 16px rgba(0,0,0,0.12);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body { 
          background: var(--bg); 
          color: var(--text-main); 
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
        }

        select, button, input { font-family: inherit; }
        
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #EBEBEB; border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: #DDDDDD; }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
        {/* ── Header ── */}
        <header style={{
          display: "flex", alignItems: "center", gap: 32,
          padding: "0 40px", height: 80, flexShrink: 0,
          background: "var(--header-bg)", borderBottom: "1px solid var(--header-border)",
          boxShadow: "0 1px 12px rgba(0,0,0,0.05)", zIndex: 100,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }} onClick={() => setPage("opportunities")}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%",
              background: "var(--primary)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
              color: "white", boxShadow: "0 2px 8px rgba(255,56,92,0.3)",
            }}>📍</div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.5px", color: "var(--primary)" }}>
                GSD <span style={{ color: "var(--text-main)" }}>.AI</span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-secondary)", fontWeight: 500, letterSpacing: "0.2px" }}>
                Garden State Detector
              </div>
            </div>
          </div>

          <nav style={{ display: "flex", gap: 8, marginLeft: 24 }}>
            {PAGES.map(p => (
              <button key={p.id} onClick={() => setPage(p.id)} style={{
                background: page === p.id ? "#F7F7F7" : "transparent",
                border: "none",
                color: page === p.id ? "var(--text-main)" : "var(--text-secondary)",
                borderRadius: 24, padding: "10px 18px", cursor: "pointer",
                fontSize: 14, fontWeight: 600,
                transition: "all 0.2s cubic-bezier(0.2, 0, 0, 1)",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <span style={{ fontSize: 16 }}>{p.icon}</span> {p.label}
              </button>
            ))}
          </nav>

          <div style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-secondary)", fontWeight: 500 }}>
            POWERED BY <span style={{ fontWeight: 700 }}>YELP DATA</span> · NJ · 3,341 VENUES
          </div>
        </header>

        {/* ── Page content ── */}
        <main style={{ flex: 1, overflowY: "auto", animation: "fadeIn 0.4s ease-out" }}>
          {page === "opportunities" && <Opportunities cuisines={cuisines} />}
          {page === "recommendations" && <Recommendations cuisines={cuisines} />}
          {page === "predict" && <Predict cuisines={cuisines} />}
        </main>
      </div>
    </>
  );
}
