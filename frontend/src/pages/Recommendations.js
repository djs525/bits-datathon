import React, { useState, useEffect } from "react";
import { api } from "../api";
import { ZipCard, Loader, EmptyState, ErrorCard } from "../components/ui";

const ATTRS = ["BYOB", "Delivery", "Outdoor Seating", "Kid-Friendly"];

export default function Recommendations({ cuisines }) {
    const [cuisine, setCuisine] = useState("");
    const [attrs, setAttrs] = useState({});
    const [maxPrice, setMaxPrice] = useState("");
    const [minMarket, setMinMarket] = useState("0");
    const [maxRisk, setMaxRisk] = useState("");
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const toggleAttr = (a) => setAttrs(prev => ({ ...prev, [a]: !prev[a] }));

    const run = async (overrides = {}) => {
        setLoading(true);
        setError(null);

        const apiParams = {
            cuisine: cuisine || undefined,
            max_risk: maxRisk || undefined,
            max_price_tier: maxPrice ? parseFloat(maxPrice) : undefined,
            byob: attrs["BYOB"] || undefined,
            delivery: attrs["Delivery"] || undefined,
            outdoor: attrs["Outdoor Seating"] || undefined,
            kid_friendly: attrs["Kid-Friendly"] || undefined,
            min_market_size: parseInt(minMarket, 10),
            limit: 10,
            ...overrides,
        };

        try {
            const data = await api.getRecommendations(apiParams);
            setResults(data);
        } catch (e) {
            setError(e.message || "Recommendation engine failed. Is the backend running?");
        } finally { setLoading(false); }
    };

    // Auto-fetch on first load with default params
    useEffect(() => { run({ limit: 10 }); }, []); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div style={{ padding: "48px 40px", maxWidth: 1200, margin: "0 auto", animation: "fadeIn 0.4s ease-out" }}>
            <div style={{ marginBottom: 40, textAlign: "left" }}>
                <h1 style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-1px", marginBottom: 12, color: "var(--text-main)" }}>
                    Smart Recommendations
                </h1>
                <p style={{ fontSize: 16, color: "var(--text-secondary)", fontWeight: 500, maxWidth: 600 }}>
                    Our real-time engine scores and re-ranks every New Jersey market based on your unique restaurant concept and risk profile.
                </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "350px 1fr", gap: 48, alignItems: "start" }}>
                {/* Filter Panel */}
                <div style={{
                    background: "white", border: "1px solid var(--border)", borderRadius: 24,
                    padding: "32px", boxShadow: "var(--shadow)", position: "sticky", top: 24
                }}>
                    <h2 style={{ fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--text-main)", marginBottom: 24 }}>
                        Your Concept
                    </h2>

                    <Row label="Cuisine Type">
                        <select value={cuisine} onChange={e => setCuisine(e.target.value)} style={sel}>
                            <option value="">General / Any</option>
                            {cuisines.map(c => <option key={c}>{c}</option>)}
                        </select>
                    </Row>

                    <Row label="Service Attributes">
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                            {ATTRS.map(a => (
                                <div key={a} onClick={() => toggleAttr(a)} style={{
                                    display: "flex", alignItems: "center", gap: 12, cursor: "pointer",
                                    padding: "8px 0", transition: "all 0.2s"
                                }}>
                                    <div style={{
                                        width: 20, height: 20, borderRadius: 6,
                                        border: `2px solid ${attrs[a] ? "var(--primary)" : "var(--border)"}`,
                                        background: attrs[a] ? "var(--primary)" : "transparent",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        color: "white", fontSize: 12
                                    }}>
                                        {attrs[a] && "✓"}
                                    </div>
                                    <span style={{ fontSize: 14, fontWeight: 600, color: attrs[a] ? "var(--text-main)" : "var(--text-secondary)" }}>{a}</span>
                                </div>
                            ))}
                        </div>
                    </Row>

                    <Row label="Target Price Level">
                        <div style={{ display: "flex", gap: 8 }}>
                            {[["", "Any"], ["1", "$"], ["2", "$$"], ["3", "$$$"], ["4", "$$$$"]].map(([v, label]) => (
                                <button key={v} onClick={() => setMaxPrice(v)} style={{
                                    background: maxPrice === v ? "var(--text-main)" : "white",
                                    border: `1px solid ${maxPrice === v ? "var(--text-main)" : "var(--border)"}`,
                                    color: maxPrice === v ? "white" : "var(--text-main)",
                                    borderRadius: 12, padding: "10px 0", cursor: "pointer",
                                    fontSize: 13, transition: "all 0.2s", fontWeight: 700, flex: 1
                                }}>
                                    {label}
                                </button>
                            ))}
                        </div>
                    </Row>

                    <Row label="Risk Tolerance">
                        <div style={{ display: "flex", gap: 8 }}>
                            {[["", "Any"], ["low", "Low"], ["medium", "Med"]].map(([v, label]) => (
                                <button key={v} onClick={() => setMaxRisk(v)} style={{
                                    background: maxRisk === v ? "var(--text-main)" : "white",
                                    border: `1px solid ${maxRisk === v ? "var(--text-main)" : "var(--border)"}`,
                                    color: maxRisk === v ? "white" : "var(--text-main)",
                                    borderRadius: 12, padding: "10px 0", cursor: "pointer",
                                    fontSize: 13, transition: "all 0.2s", fontWeight: 700, flex: 1
                                }}>
                                    {label}
                                </button>
                            ))}
                        </div>
                    </Row>

                    <Row label="Market Traffic (Min Reviews)">
                        <select value={minMarket} onChange={e => setMinMarket(e.target.value)} style={sel}>
                            <option value="0">Global Search (All NJ)</option>
                            <option value="500">Established (500+)</option>
                            <option value="1000">Major Hubs (1k+)</option>
                            <option value="3000">High Traffic (3k+)</option>
                        </select>
                    </Row>

                    <button onClick={run} disabled={loading} style={{
                        background: "var(--primary)", border: "none", borderRadius: 16,
                        color: "white", fontSize: 16, fontWeight: 700,
                        padding: "18px", cursor: "pointer", marginTop: 12, width: "100%",
                        boxShadow: "0 8px 16px rgba(255, 56, 92, 0.2)",
                        transition: "all 0.2s",
                        opacity: loading ? 0.7 : 1,
                        transform: loading ? "scale(0.98)" : "scale(1)",
                    }}>
                        {loading ? "Re-scoring..." : "Generate Insights"}
                    </button>
                </div>

                {/* Results Area */}
                <div style={{ minHeight: 600 }}>
                    {loading ? (
                        <Loader text="Analyzing NJ market gaps & running real-time simulations..." />
                    ) : error ? (
                        <ErrorCard message={error} />
                    ) : results ? (
                        <div style={{ animation: "fadeIn 0.5s ease-out" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
                                <div>
                                    <div style={{ fontSize: 14, color: "var(--text-secondary)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "1px" }}>
                                        Recommendation Engine
                                    </div>
                                    <div style={{ fontSize: 24, fontWeight: 800, color: "var(--text-main)" }}>
                                        Top {results.recommendations.length} Market Matches
                                    </div>
                                </div>
                                <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>
                                    NJ State · {results.total_analyzed || 91} Zip Codes Analyzed
                                </div>
                            </div>

                            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                                {results.recommendations.length === 0 ? (
                                    <EmptyState icon="🔭" text="No high-confidence markets found with these exact filters.\nTry reducing price tier or increasing risk tolerance." />
                                ) : (
                                    results.recommendations.map((z, idx) => (
                                        <RecommendationCard key={z.city} z={z} rank={idx + 1} />
                                    ))
                                )}
                            </div>
                        </div>
                    ) : (
                        <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <EmptyState icon="🎯" text="Configure your restaurant concept to reveal\nthe most underserved markets in New Jersey." />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function RecommendationCard({ z, rank }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div style={{
            background: "white", border: "1px solid var(--border)", borderRadius: 24,
            padding: "24px 32px", cursor: "pointer", transition: "all 0.3s cubic-bezier(0.2, 0, 0, 1)",
            boxShadow: expanded ? "0 12px 32px rgba(0,0,0,0.08)" : "0 2px 8px rgba(0,0,0,0.02)",
            transform: expanded ? "translateY(-2px)" : "none",
        }} onClick={() => setExpanded(!expanded)}>
            <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
                <div style={{
                    width: 48, height: 48, borderRadius: "50%", background: rank <= 3 ? "var(--primary)" : "#F7F7F7",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: rank <= 3 ? "white" : "var(--text-secondary)", fontWeight: 800, fontSize: 18, flexShrink: 0
                }}>
                    {rank}
                </div>

                <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <div>
                            <h3 style={{ fontSize: 20, fontWeight: 800, color: "var(--text-main)", marginBottom: 6 }}>{z.city}</h3>
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                {(z.zips || [{ zip: z.zip, match_type: z.match_type }]).map(zd => (
                                    <span key={zd.zip} style={{
                                        fontSize: 11, fontWeight: 700,
                                        background: zd.match_type === "relaxed" ? "#FEF3C7" : "#F0FDF4",
                                        color: zd.match_type === "relaxed" ? "#92400E" : "#166534",
                                        border: `1px solid ${zd.match_type === "relaxed" ? "#FCD34D" : "#86EFAC"}`,
                                        borderRadius: 6, padding: "2px 8px",
                                    }}>{zd.zip}</span>
                                ))}
                            </div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                            <div style={{ fontSize: 24, fontWeight: 900, color: "var(--primary)", lineHeight: 1 }}>{z.opportunity_score}</div>
                            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", marginTop: 4 }}>Match Score</div>
                        </div>
                    </div>

                    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                        {z.match_type === "relaxed" && (
                            <Badge color="#F59E0B">
                                RELAXED MATCH
                            </Badge>
                        )}
                        <Badge color={z.risk === "low" ? "#008A05" : z.risk === "medium" ? "#E67E22" : "#C13515"}>
                            {z.risk.toUpperCase()} RISK
                        </Badge>
                        <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>
                            {z.total_reviews.toLocaleString()} reviews · {z.avg_stars}★ · {z.primary_concept} Priority
                        </span>
                    </div>
                </div>
            </div>

            {expanded && (
                <div style={{ marginTop: 24, paddingTop: 24, borderTop: "1px solid var(--border)", animation: "fadeIn 0.3s ease-out" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 32 }}>
                        <div>
                            <Label>Scoring Evidence</Label>
                            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                                <EvidenceRow label="Cuisine Gap Score" value={z.evidence.cuisine_gap_score} />
                                <EvidenceRow label="Neighbor Demand" value={z.evidence.neighbor_demand} />
                                <EvidenceRow label="Closure Rate" value={(z.closure_rate * 100).toFixed(1) + "%"} />
                                {z.evidence.survival_probability && (
                                    <EvidenceRow label="Survival Forecast" value={(z.evidence.survival_probability * 100).toFixed(0) + "%"} highlight />
                                )}
                            </div>

                            {/* Per-zip breakdown if multiple zips grouped */}
                            {z.zips && z.zips.length > 1 && (
                                <div style={{ marginTop: 20 }}>
                                    <Label>Zip Code Breakdown</Label>
                                    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
                                        {z.zips.map(zd => (
                                            <div key={zd.zip} style={{
                                                display: "flex", justifyContent: "space-between",
                                                background: "#F7F7F7", borderRadius: 10, padding: "10px 14px",
                                                fontSize: 12, alignItems: "center"
                                            }}>
                                                <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{zd.zip}</span>
                                                <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{zd.total_reviews.toLocaleString()} reviews</span>
                                                <span style={{ fontWeight: 800, color: "var(--primary)" }}>{zd.opportunity_score}</span>
                                                <span style={{
                                                    fontSize: 10, fontWeight: 700,
                                                    background: zd.match_type === "relaxed" ? "#FEF3C7" : "#F0FDF4",
                                                    color: zd.match_type === "relaxed" ? "#92400E" : "#166534",
                                                    border: `1px solid ${zd.match_type === "relaxed" ? "#FCD34D" : "#86EFAC"}`,
                                                    borderRadius: 6, padding: "2px 6px"
                                                }}>{zd.match_type === "relaxed" ? "Relaxed" : "Exact"}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div>
                            <Label>Opportunity Signals</Label>
                            <div style={{ marginTop: 12, background: "#F7F7F7", borderRadius: 16, padding: "16px" }}>
                                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-main)", marginBottom: 8 }}>
                                    {z.evidence.competition_signal}
                                </div>
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                                    {z.evidence.attribute_opportunities.map(a => (
                                        <span key={a} style={{
                                            background: "white", border: "1px solid #EBEBEB", borderRadius: 8,
                                            padding: "6px 12px", fontSize: 11, fontWeight: 700, color: "var(--primary)"
                                        }}>
                                            +{a} GAP
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {z.match_type === "relaxed" && z.match_issues && z.match_issues.length > 0 && (
                                <div style={{ marginTop: 24 }}>
                                    <Label>Relaxed Criteria</Label>
                                    <div style={{ marginTop: 12, background: "#FFFBEB", border: "1px solid #FCD34D", borderRadius: 16, padding: "16px" }}>
                                        <ul style={{ margin: 0, paddingLeft: 20, color: "#92400E", fontSize: 13, fontWeight: 500 }}>
                                            {z.match_issues.map((issue, i) => (
                                                <li key={i} style={{ marginBottom: 4 }}>{issue}</li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function EvidenceRow({ label, value, highlight }) {
    return (
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
            <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{label}</span>
            <span style={{ fontWeight: 700, color: highlight ? "var(--primary)" : "var(--text-main)" }}>{value}</span>
        </div>
    );
}

function Badge({ children, color }) {
    return (
        <span style={{
            background: color + "10", color: color,
            padding: "4px 10px", borderRadius: 8, fontSize: 10, fontWeight: 800,
            letterSpacing: "0.5px"
        }}>
            {children}
        </span>
    );
}

function Label({ children }) {
    return (
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-main)", textTransform: "uppercase", letterSpacing: "1px" }}>
            {children}
        </div>
    );
}

function Row({ label, children }) {
    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 11, color: "var(--text-main)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 12 }}>
                {label}
            </div>
            {children}
        </div>
    );
}

const sel = {
    background: "#F7F7F7", border: "1px solid #EBEBEB", borderRadius: 14,
    color: "var(--text-main)", fontSize: 14, fontWeight: 600,
    padding: "14px 16px", outline: "none", cursor: "pointer", width: "100%",
    appearance: "none",
};
