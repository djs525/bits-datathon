import React, { useState, useEffect } from "react";
import { api } from "../api";
import { ZipCard, Loader, EmptyState, SectionTitle, StatBox, RiskBadge, GapBar } from "../components/ui";

export default function Opportunities({ cuisines }) {
  const [filters, setFilters] = useState({
    cuisine: "", min_gap_score: 0, min_market_size: 0,
    max_risk: "", sort: "opportunity_score", limit: 25,
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetch = async () => {
    setLoading(true);
    try {
      const data = await api.getOpportunities(filters);
      setResults(data);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetch(); }, []); // eslint-disable-line

  const selectZip = async (zip) => {
    setSelected(zip);
    setDetailLoading(true);
    try {
      const d = await api.getOpportunity(zip);
      setDetail(d);
    } finally { setDetailLoading(false); }
  };

  const set = (k, v) => setFilters(f => ({ ...f, [k]: v }));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 400px", height: "100%", overflow: "hidden" }}>
      {/* ── Left: filters + results ── */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", borderRight: "1px solid #2a2a3a" }}>
        {/* filters */}
        <div style={{ padding: "20px 28px", borderBottom: "1px solid #2a2a3a", background: "#12121a" }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#6b6b8a", fontFamily: "DM Mono, monospace", marginBottom: 14, letterSpacing: 1 }}>
            WHERE SHOULD I OPEN A…
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
            <select value={filters.cuisine} onChange={e => set("cuisine", e.target.value)} style={sel}>
              <option value="">Any Cuisine</option>
              {cuisines.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={filters.max_risk} onChange={e => set("max_risk", e.target.value)} style={sel}>
              <option value="">Any Risk</option>
              <option value="low">Low Risk Only</option>
              <option value="medium">Medium or Lower</option>
              <option value="high">All</option>
            </select>
            <select value={filters.min_market_size} onChange={e => set("min_market_size", e.target.value)} style={sel}>
              <option value="0">Any Market Size</option>
              <option value="1000">1k+ Reviews</option>
              <option value="3000">3k+ Reviews</option>
              <option value="5000">5k+ Reviews</option>
            </select>
            <select value={filters.sort} onChange={e => set("sort", e.target.value)} style={sel}>
              <option value="opportunity_score">Sort: Opportunity</option>
              <option value="market_size">Sort: Market Size</option>
              <option value="stars">Sort: Rating</option>
              <option value="closure_risk">Sort: Closure Risk</option>
            </select>
            <button onClick={fetch} style={btn}>Search →</button>
          </div>
        </div>

        {/* results */}
        <div style={{ overflowY: "auto", padding: "16px 28px", display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
          {loading ? <Loader text="Finding opportunities…" /> :
           !results ? null :
           results.results.length === 0 ? <EmptyState text="No zip codes match these filters.\nTry loosening your criteria." /> :
           <>
             <div style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color: "#6b6b8a", marginBottom: 4 }}>
               {results.count} zip codes found
             </div>
             {results.results.map(z => (
               <ZipCard key={z.zip} z={z} selected={selected === z.zip} onClick={() => selectZip(z.zip)} />
             ))}
           </>}
        </div>
      </div>

      {/* ── Right: detail ── */}
      <div style={{ overflowY: "auto", background: "#12121a" }}>
        {!selected ?
          <EmptyState icon="📍" text="← Select a zip code\nto see full breakdown" /> :
         detailLoading ? <Loader text="Loading detail…" /> :
         detail ? <DetailPanel d={detail} /> : null}
      </div>
    </div>
  );
}

function DetailPanel({ d }) {
  const maxGap = Math.max(...d.cuisine_gaps.map(g => g.gap_score), 1);

  return (
    <div style={{ padding: 28 }}>
      {/* header */}
      <div style={{ marginBottom: 24, paddingBottom: 20, borderBottom: "1px solid #2a2a3a" }}>
        <div style={{
          fontSize: 52, fontWeight: 800, letterSpacing: -3,
          background: "linear-gradient(135deg, #00e5a0, #7c6cff)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          lineHeight: 1,
        }}>{d.zip}</div>
        <div style={{ fontSize: 14, color: "#6b6b8a", marginTop: 6, fontWeight: 600 }}>
          {d.city}, NJ
        </div>
        <div style={{ marginTop: 10, display: "flex", gap: 8, alignItems: "center" }}>
          <RiskBadge risk={d.risk} />
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color: "#6b6b8a" }}>
            Opp Score: <b style={{ color: "#00e5a0" }}>{d.opportunity_score}</b>
          </span>
        </div>
      </div>

      {/* market stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 24 }}>
        <StatBox value={d.market.open_restaurants} label="Open Now" color="#00e5a0" />
        <StatBox value={`${Math.round(d.market.closure_rate * 100)}%`} label="Closure Rate"
          color={d.market.closure_rate > 0.35 ? "#ff6c6c" : d.market.closure_rate > 0.2 ? "#ffd166" : "#00e5a0"} />
        <StatBox value={`${d.market.avg_stars}★`} label="Avg Rating" />
        <StatBox value={d.market.total_reviews.toLocaleString()} label="Total Reviews" color="#7c6cff" />
        <StatBox value={`${"$".repeat(Math.round(d.market.avg_price_tier))}`} label="Price Tier" />
        <StatBox value={d.market.num_neighbors_analyzed} label="Neighbors (20km)" />
      </div>

      {/* signal */}
      <div style={{ marginBottom: 24 }}>
        <SectionTitle>Signal Summary</SectionTitle>
        <div style={{
          background: "rgba(255,209,102,0.06)", border: "1px solid rgba(255,209,102,0.2)",
          borderRadius: 10, padding: 16, fontSize: 12, lineHeight: 1.7,
          color: "#ffd166", fontWeight: 600,
        }}>
          {d.signal_summary}
        </div>
      </div>

      {/* cuisine gaps */}
      {d.cuisine_gaps.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <SectionTitle>Cuisine Gaps</SectionTitle>
          {d.cuisine_gaps.map(g => (
            <div key={g.cuisine} style={{
              background: "#0a0a0f", border: "1px solid #2a2a3a",
              borderRadius: 10, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 14 }}>{g.cuisine}</span>
                <span style={{
                  fontFamily: "DM Mono, monospace", fontSize: 11,
                  background: "rgba(124,108,255,0.12)", border: "1px solid rgba(124,108,255,0.35)",
                  color: "#7c6cff", borderRadius: 6, padding: "2px 8px",
                }}>
                  score {g.gap_score.toFixed(1)}
                </span>
              </div>
              <GapBar value={g.gap_score} max={maxGap} />
              <div style={{ display: "flex", gap: 16, marginTop: 8, fontFamily: "DM Mono, monospace", fontSize: 10, color: "#6b6b8a" }}>
                <span>Local: <b style={{ color: "#e8e8f0" }}>{g.local_count}</b></span>
                <span>Neighbor demand: <b style={{ color: "#e8e8f0" }}>{g.neighbor_demand}</b></span>
                <span style={{ color: g.local_count === 0 ? "#00e5a0" : "#ffd166" }}>
                  {g.local_count === 0 ? "✓ no competition" : "⚠ weak competitor"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* attribute gaps */}
      {d.attribute_gaps.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <SectionTitle>Attribute Gaps</SectionTitle>
          {d.attribute_gaps.map(a => (
            <div key={a.attribute} style={{
              background: "#0a0a0f", border: "1px solid rgba(0,229,160,0.15)",
              borderRadius: 10, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 13, color: "#00e5a0" }}>{a.attribute}</span>
                <span style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color: "#00e5a0" }}>
                  +{Math.round(a.gap * 100)}% gap
                </span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[["This Zip", a.local_rate, "#ff6c6c"], ["Neighbor Avg", a.neighbor_avg, "#00e5a0"]].map(([label, rate, color]) => (
                  <div key={label}>
                    <div style={{ fontFamily: "DM Mono, monospace", fontSize: 9, color: "#6b6b8a", marginBottom: 4, textTransform: "uppercase" }}>{label}</div>
                    <div style={{ height: 6, background: "#2a2a3a", borderRadius: 3, overflow: "hidden", marginBottom: 4 }}>
                      <div style={{ height: "100%", width: `${Math.min(rate * 100, 100)}%`, background: color, borderRadius: 3 }} />
                    </div>
                    <span style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color }}>{Math.round(rate * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* existing competition */}
      <div style={{ marginBottom: 24 }}>
        <SectionTitle>Existing Competition</SectionTitle>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Object.entries(d.existing_cuisines).sort((a, b) => b[1] - a[1]).map(([cuisine, count]) => (
            <span key={cuisine} style={{
              background: "#1a1a26", border: "1px solid #2a2a3a",
              borderRadius: 6, padding: "4px 10px", fontFamily: "DM Mono, monospace", fontSize: 10, color: "#6b6b8a",
              display: "flex", alignItems: "center", gap: 5,
            }}>
              {cuisine}
              <span style={{ background: "#2a2a3a", borderRadius: 3, padding: "1px 5px", color: "#e8e8f0" }}>{count}</span>
            </span>
          ))}
        </div>
      </div>

      {/* top local restaurants */}
      {d.local_restaurants?.length > 0 && (
        <div>
          <SectionTitle>Top Local Competitors</SectionTitle>
          {d.local_restaurants.slice(0, 8).map((r, i) => (
            <div key={i} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 0", borderBottom: "1px solid #1a1a26",
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{r.name}</div>
                <div style={{ fontFamily: "DM Mono, monospace", fontSize: 10, color: "#6b6b8a", marginTop: 2 }}>
                  {r.categories?.split(",").slice(0, 2).join(", ")}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: "DM Mono, monospace", fontSize: 11, color: "#ffd166" }}>
                  {r.stars}★ · {r.review_count} reviews
                </div>
                <div style={{ fontFamily: "DM Mono, monospace", fontSize: 10, color: r.is_open ? "#00e5a0" : "#ff6c6c", marginTop: 2 }}>
                  {r.is_open ? "Open" : "Closed"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const sel = {
  background: "#0a0a0f", border: "1px solid #2a2a3a", borderRadius: 8,
  color: "#e8e8f0", fontFamily: "Syne, sans-serif", fontSize: 13,
  padding: "8px 12px", outline: "none", cursor: "pointer", minWidth: 140,
};
const btn = {
  background: "#00e5a0", border: "none", borderRadius: 8,
  color: "#000", fontFamily: "Syne, sans-serif", fontSize: 13, fontWeight: 700,
  padding: "8px 20px", cursor: "pointer",
};
