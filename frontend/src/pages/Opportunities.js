import React, { useState, useEffect, useRef } from "react";
import { api } from "../api";
import { ZipCard, Loader, EmptyState, SectionTitle, StatBox, RiskBadge, GapBar, ErrorCard } from "../components/ui";
import Map from "../components/Map";

export default function Opportunities({ cuisines, preload, onClearPreload }) {
  const [filters, setFilters] = useState({
    cuisine: "", min_gap_score: 0, min_market_size: 0,
    risk_levels: ["low", "medium", "high"], sort: "opportunity_score", target_zip: "", limit: 91,
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(preload?.zip || null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getOpportunities(filters);
      setResults(data);
    } catch (e) {
      setError(e.message || "Failed to load opportunities.");
    } finally { setLoading(false); }
  };

  useEffect(() => { fetch(); }, []); // eslint-disable-line

  const selectZip = async (zip) => {
    setSelected(zip);
    setDetailLoading(true);
    try {
      const d = await api.getOpportunity(zip);
      setDetail(d);
    } catch (e) {
      setError(e.message || `Failed to load details for ${zip}.`);
    } finally { setDetailLoading(false); }
  };

  // Auto-load detail panel when arriving from Decision Flow with a zip pre-selected
  useEffect(() => {
    if (preload?.zip) selectZip(preload.zip);
  }, []); // eslint-disable-line

  const set = (k, v) => setFilters(f => ({ ...f, [k]: v }));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "300px 1fr 450px", height: "100%", overflow: "hidden", background: "#F7F7F7" }}>
      {/* ── Left: filters + results ── */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", borderRight: "1px solid var(--border)", background: "white" }}>
        {/* filters */}
        <div style={{ padding: "20px", borderBottom: "1px solid var(--border)", background: "white" }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 14, textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Find your next location
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <select value={filters.cuisine} onChange={e => set("cuisine", e.target.value)} style={sel}>
              <option value="">Any Cuisine</option>
              {cuisines.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <div style={{ padding: "12px", border: "1px solid var(--border)", borderRadius: 12, background: "#fafafa" }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Risk Regions (Select Multiple)
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {["low", "medium", "high"].map(v => {
                  const isSelected = filters.risk_levels.includes(v);
                  const labelMap = { low: "Low", medium: "Med", high: "High" };
                  return (
                    <button key={v} onClick={() => {
                      set("risk_levels", isSelected
                        ? filters.risk_levels.filter(r => r !== v)
                        : [...filters.risk_levels, v]
                      );
                    }} style={{
                      background: isSelected ? "var(--text-main)" : "white",
                      border: `1px solid ${isSelected ? "var(--text-main)" : "var(--border)"}`,
                      color: isSelected ? "white" : "var(--text-secondary)",
                      borderRadius: 8, padding: "8px 0", cursor: "pointer",
                      fontSize: 12, transition: "all 0.2s", fontWeight: 600, flex: 1,
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 4
                    }}>
                      {isSelected && <span style={{ fontSize: 11 }}>✓</span>}
                      {labelMap[v]}
                    </button>
                  );
                })}
              </div>
            </div>
            <select value={filters.min_market_size} onChange={e => set("min_market_size", e.target.value)} style={sel}>
              <option value="0">Any market size</option>
              <option value="1000">1k+ reviews</option>
              <option value="3000">3k+ reviews</option>
              <option value="5000">5k+ reviews</option>
            </select>
            <select value={filters.sort} onChange={e => set("sort", e.target.value)} style={sel}>
              <option value="opportunity_score">Sort by Opportunity</option>
              <option value="market_size">Sort by Market Size</option>
              <option value="stars">Sort by Quality</option>
              <option value="closure_risk">Sort by Risk</option>
              <option value="distance_to_target">Sort by Distance</option>
            </select>
            {filters.sort === "distance_to_target" && (
              <input
                type="text"
                placeholder="Target Zip Code (e.g. 08053)"
                value={filters.target_zip || ""}
                onChange={e => set("target_zip", e.target.value)}
                style={{ ...sel, background: "white" }}
              />
            )}
            <button onClick={fetch} style={btn}>Search</button>
          </div>
        </div>

        {/* results */}
        <div style={{ overflowY: "auto", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8, flex: 1, background: "#F7F7F7" }}>
          {loading ? <Loader text="Analyzing NJ markets…" /> :
            error ? <ErrorCard message={error} /> :
              !results ? null :
                results.results.length === 0 ? <EmptyState icon="" text={`No results for these filters.\nTry broadening your search.`} /> :
                  <>
                    <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600, marginBottom: 4 }}>
                      {results.count} locations found in New Jersey
                    </div>
                    {results.results.map(z => (
                      <ZipCard key={z.zip} z={z} selected={selected === z.zip} onClick={() => selectZip(z.zip)} />
                    ))}
                  </>}
        </div>
      </div>

      {/* ── Middle: Map ── */}
      <div style={{ position: "relative", background: "#F7F7F7", padding: 16 }}>
        <Map results={results?.results || []} selectedZip={selected} onZipSelect={selectZip} />
        {results && (
          <div style={{
            position: "absolute", bottom: 28, left: 28, zIndex: 1000,
            background: "#FFFFFF", border: "1px solid var(--border)",
            padding: "8px 16px", borderRadius: 20,
            boxShadow: "0 2px 10px rgba(0,0,0,0.08)",
            fontSize: 13, color: "var(--text-secondary)",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <span>Showing <b style={{ color: "var(--text-main)" }}>{results.results.length}</b> locations</span>
          </div>
        )}
      </div>

      {/* ── Right: detail ── */}
      <div style={{ position: "relative", overflow: "hidden", background: "white", borderLeft: "1px solid var(--border)" }}>
        {!selected ? (
          <EmptyState icon="" text="Select a zip code to see market insights for your concept" />
        ) : detailLoading ? (
          <Loader text="Fetching market data…" />
        ) : detail ? (
          <ScrollableDetailPanel d={detail} />
        ) : null}
      </div>
    </div>
  );
}

function ScrollableDetailPanel({ d }) {
  const scrollRef = useRef(null);
  const [showArrow, setShowArrow] = useState(true);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    // Hide arrow if we are within 50px of the bottom
    setShowArrow(scrollTop + clientHeight < scrollHeight - 50);
  };

  // Re-check scroll anytime `d` changes to see if we even need the arrow
  useEffect(() => {
    setTimeout(handleScroll, 100);
  }, [d]);

  return (
    <>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{ height: "100%", overflowY: "auto", paddingBottom: "80px" }}
      >
        <DetailPanel d={d} />
      </div>

      {/* Floating Scroll Indicator */}
      <div style={{
        position: "absolute", bottom: 24, left: "50%", transform: "translateX(-50%)",
        background: "rgba(34,34,34,0.9)", color: "white", padding: "10px 20px",
        borderRadius: 30, fontSize: 13, fontWeight: 600,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        display: "flex", alignItems: "center", gap: 8,
        opacity: showArrow ? 1 : 0, transition: "opacity 0.3s ease",
        pointerEvents: "none", zIndex: 10,
      }}>
        Scroll for details <span style={{ animation: "bounce 1.5s infinite" }}>↓</span>
      </div>
      <style>{`
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(3px); }
        }
      `}</style>
    </>
  );
}

function DetailPanel({ d }) {
  const maxGap = Math.max(...d.cuisine_gaps.map(g => g.gap_score), 1);

  return (
    <div style={{ padding: "40px" }}>
      {/* header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{
          fontSize: 48, fontWeight: 800, letterSpacing: "-2px",
          color: "var(--text-main)", lineHeight: 1,
        }}>{d.zip}</div>
        <div style={{ fontSize: 18, color: "var(--text-secondary)", marginTop: 8, fontWeight: 600 }}>
          {d.city}, New Jersey
        </div>
        <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center" }}>
          <RiskBadge risk={d.risk} />
          <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>
            Market Opportunity: <span style={{ color: "var(--primary)", fontWeight: 800 }}>{d.opportunity_score}</span>
          </span>
        </div>
      </div>

      {/* market stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginBottom: 32 }}>
        <StatBox value={d.market.open_restaurants} label="Open Venues" color="var(--primary)" />
        <StatBox value={`${Math.round(d.market.closure_rate * 100)}%`} label="Closure Rate"
          color={d.market.closure_rate > 0.35 ? "#C13515" : d.market.closure_rate > 0.2 ? "#E67E22" : "#008A05"} />
        <StatBox value={`${d.market.avg_stars}★`} label="Avg Rating" />
        <StatBox value={d.market.total_reviews.toLocaleString()} label="Total Reviews" />
      </div>

      {/* signal */}
      <div style={{ marginBottom: 32 }}>
        <SectionTitle>Market Signal</SectionTitle>
        <div style={{
          background: "#F7F7F7", border: "1px solid var(--border)",
          borderRadius: 16, padding: "24px", fontSize: 14, lineHeight: 1.6,
          color: "var(--text-main)", fontWeight: 500,
        }}>
          {d.signal_summary}
        </div>
      </div>

      {/* cuisine gaps */}
      {d.cuisine_gaps.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <SectionTitle>High Demand Cuisines</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {d.cuisine_gaps.map(g => (
              <div key={g.cuisine} style={{
                background: "white", border: "1px solid var(--border)",
                borderRadius: 16, padding: "20px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.02)"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, alignItems: "center" }}>
                  <span style={{ fontWeight: 700, fontSize: 15 }}>{g.cuisine}</span>
                  <span style={{
                    fontSize: 12, fontWeight: 700, color: "var(--primary)",
                    background: "#FFF0F0", padding: "4px 8px", borderRadius: 6
                  }}>
                    Gap {g.gap_score.toFixed(1)}
                  </span>
                </div>
                <GapBar value={g.gap_score} max={maxGap} />
                <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--primary)" }} /> {g.local_count} matching venues
                  </span>
                  <span style={{ color: g.local_count === 0 ? "#008A05" : "#E67E22", fontWeight: 700 }}>
                    {g.local_count === 0 ? "Under-served area" : "Moderate competition"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* existing competition */}
      <div style={{ marginBottom: 32 }}>
        <SectionTitle>Current Market Mix</SectionTitle>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {Object.entries(d.existing_cuisines).sort((a, b) => b[1] - a[1]).map(([cuisine, count]) => (
            <span key={cuisine} style={{
              background: "#F7F7F7", border: "1px solid var(--border)",
              borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "var(--text-main)",
              display: "flex", alignItems: "center", gap: 8, fontWeight: 600
            }}>
              {cuisine}
              <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}>{count}</span>
            </span>
          ))}
        </div>
      </div>

      {/* top local restaurants */}
      {d.local_restaurants?.length > 0 && (
        <div>
          <SectionTitle>Top Rated Competitors</SectionTitle>
          <div style={{ border: "1px solid var(--border)", borderRadius: 16, overflow: "hidden" }}>
            {d.local_restaurants.slice(0, 8).map((r, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "16px 20px", borderBottom: i === 7 ? "none" : "1px solid var(--border)",
                background: "white"
              }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>{r.name}</div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4, fontWeight: 500 }}>
                    {r.categories?.split(",").slice(0, 2).join(", ")}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-main)" }}>
                    {r.stars}★
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                    {r.review_count} reviews
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const sel = {
  background: "#F7F7F7", border: "1px solid #EBEBEB", borderRadius: 12,
  color: "var(--text-main)", fontSize: 14, fontWeight: 600,
  padding: "12px 16px", outline: "none", cursor: "pointer", minWidth: 160,
  appearance: "none",
};

const btn = {
  background: "var(--primary)", border: "none", borderRadius: 12,
  color: "white", fontSize: 14, fontWeight: 700,
  padding: "12px 24px", cursor: "pointer",
  boxShadow: "0 2px 4px rgba(255, 56, 92, 0.2)",
  transition: "transform 0.1s ease",
};
