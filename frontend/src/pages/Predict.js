import React, { useState, useEffect, useRef } from "react";
import { api } from "../api";
import { Loader, ErrorCard, SectionTitle, StatBox, RiskBadge } from "../components/ui";

const CUISINES_WITH_DEFAULTS = [
    "American", "Italian", "Chinese", "Japanese", "Mexican", "Thai",
    "Indian", "Korean", "Mediterranean", "Greek", "Vietnamese", "French",
    "Spanish", "Middle Eastern", "Pizza", "Burgers", "Seafood", "Sushi",
    "Barbecue", "Sandwiches", "Breakfast", "Desserts", "Vegan",
];

const NOISE_OPTIONS = ["quiet", "average", "loud", "very_loud"];

// No more fixed signal colors at top - they are calculated inside ResultPanel

// ── Toggle button helper ──────────────────────────────────────────────────────
function Toggle({ value, onChange, choices }) {
    return (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {choices.map(([v, label]) => (
                <button key={v} onClick={() => onChange(v)} style={{
                    background: value === v ? "var(--text-main)" : "white",
                    border: `1px solid ${value === v ? "var(--text-main)" : "var(--border)"}`,
                    color: value === v ? "white" : "var(--text-main)",
                    borderRadius: 10, padding: "8px 14px", cursor: "pointer",
                    fontSize: 12, transition: "all 0.2s", fontWeight: 600
                }}>
                    {label}
                </button>
            ))}
        </div>
    );
}

// ── Label row ─────────────────────────────────────────────────────────────────
function Row({ label, children, hint }) {
    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
                <div style={{
                    fontSize: 12, color: "var(--text-main)", fontWeight: 700,
                    textTransform: "uppercase", letterSpacing: "0.5px"
                }}>
                    {label}
                </div>
                {hint && <div style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 500 }}>{hint}</div>}
            </div>
            {children}
        </div>
    );
}

// ── SHAP Factor Row ───────────────────────────────────────────────────────────
function ShapFactor({ factor, maxAbs }) {
    const val = factor.shap_value ?? factor.global_importance ?? 0;
    const pct = maxAbs > 0 ? Math.abs(val / maxAbs) * 100 : 0;
    const isPos = val >= 0;
    const color = isPos ? "#008A05" : "#C13515";
    const label = factor.feature.replace(/^cuisine_/, "").replace(/_/g, " ");

    return (
        <div style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: "var(--text-main)", fontWeight: 600, textTransform: "capitalize" }}>
                    {label}
                </span>
                <span style={{ fontSize: 12, color, fontWeight: 700 }}>
                    {factor.shap_value != null
                        ? `${isPos ? "+" : ""}${val.toFixed(3)}`
                        : `imp ${val.toFixed(4)}`}
                </span>
            </div>
            <div style={{ height: 6, background: "#F1F1F1", borderRadius: 3, overflow: "hidden" }}>
                <div style={{
                    height: "100%", width: `${pct}%`, borderRadius: 3,
                    background: color, float: isPos ? "left" : "right",
                    transition: "width 0.6s cubic-bezier(0.2, 0, 0, 1)",
                }} />
            </div>
        </div>
    );
}

const sel = {
    background: "#F7F7F7", border: "1px solid #EBEBEB", borderRadius: 12,
    color: "var(--text-main)", fontSize: 14, fontWeight: 600,
    padding: "12px 16px", outline: "none", cursor: "pointer", width: "100%",
    appearance: "none",
};

// ── Main Component ────────────────────────────────────────────────────────────
export default function Predict({ cuisines, preload, onClearPreload }) {
    const [zipCode, setZipCode] = useState(preload?.zip || "");
    const [cuisine, setCuisine] = useState(preload?.cuisine || "American");
    const [priceTier, setPriceTier] = useState(preload?.price_tier ? String(preload.price_tier) : "");
    const [noiseLevel, setNoiseLevel] = useState("average");
    const [attrs, setAttrs] = useState({
        has_delivery: preload?.has_delivery != null ? String(preload.has_delivery) : "0",
        has_takeout: "0", has_outdoor_seating: preload?.has_outdoor_seating != null ? String(preload.has_outdoor_seating) : "0",
        good_for_kids: preload?.good_for_kids != null ? String(preload.good_for_kids) : "0",
        has_reservations: "0", has_wifi: "0", has_alcohol: "0", has_tv: "0", good_for_groups: "0",
    });
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [preloadBanner, setPreloadBanner] = useState(!!preload);
    const didAutoRun = useRef(false);

    const setAttr = (k, v) => setAttrs(prev => ({ ...prev, [k]: v }));

    // Auto-run prediction when arriving with preload data
    useEffect(() => {
        if (preload && preload.zip && !didAutoRun.current) {
            didAutoRun.current = true;
            // Small delay so the form visually renders first
            setTimeout(() => handlePredict(preload.zip, preload.cuisine, preload.price_tier), 300);
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const handlePredict = async (zipOverride, cuisineOverride, priceOverride) => {
        const z = zipOverride || zipCode;
        const c = cuisineOverride || cuisine;
        const p = priceOverride !== undefined ? priceOverride : priceTier;

        if (!z || String(z).length !== 5 || !/^\d+$/.test(String(z))) {
            setError("Please enter a valid 5-digit NJ zip code.");
            return;
        }
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const body = { zip_code: String(z), cuisine: c };
            if (p) body.price_tier = parseFloat(p);
            if (noiseLevel) body.noise_level = noiseLevel;
            // Only include attribute overrides that were explicitly set
            Object.entries(attrs).forEach(([k, v]) => {
                if (v !== "") body[k] = parseInt(v);
            });
            const data = await api.predict(body);
            setResult(data);
        } catch (e) {
            setError(e.message || "Prediction failed. Is the backend running?");
        } finally {
            setLoading(false);
        }
    };

    const handleRun = () => handlePredict();


    return (
        <div style={{ display: "grid", gridTemplateColumns: "450px 1fr", height: "100%", overflow: "hidden", background: "#F7F7F7" }}>

            {/* ── Left: form ── */}
            <div style={{
                background: "var(--glass-bg)", borderRight: "1px solid var(--border)", overflowY: "auto",
                display: "flex", flexDirection: "column",
                backdropFilter: "var(--glass-filter)", WebkitBackdropFilter: "var(--glass-filter)"
            }}>
                <div style={{ padding: "32px 40px", borderBottom: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 6 }}>
                        Survival Predictor
                    </div>
                    <div style={{ fontSize: 14, color: "var(--text-main)", fontWeight: 500, lineHeight: 1.5 }}>
                        AI model trained on NJ historical data. Enter your concept details below.
                    </div>
                </div>

                <div style={{ padding: "32px 40px", flex: 1 }}>

                    {/* Preload banner from Decision Flow */}
                    {preloadBanner && (
                        <div style={{
                            background: "#EFF6FF", border: "1px solid #93C5FD", borderRadius: 14,
                            padding: "12px 16px", marginBottom: 24, display: "flex",
                            justifyContent: "space-between", alignItems: "center",
                            animation: "fadeIn 0.3s ease-out",
                        }}>
                            <div style={{ fontSize: 13, fontWeight: 600, color: "#1D4ED8" }}>
                                Pre-filled from Decision Flow · Running prediction automatically…
                            </div>
                            <button onClick={() => setPreloadBanner(false)} style={{
                                background: "none", border: "none", cursor: "pointer",
                                fontSize: 16, color: "#93C5FD", lineHeight: 1,
                            }}>✕</button>
                        </div>
                    )}

                    <Row label="NJ Zip Code" hint="required">
                        <input
                            type="text"
                            maxLength={5}
                            value={zipCode}
                            onChange={e => setZipCode(e.target.value.replace(/\D/g, ""))}
                            placeholder="e.g. 08053"
                            style={{
                                ...sel, width: "100%", fontSize: 24, fontWeight: 800, letterSpacing: "-0.5px",
                                padding: "16px 20px", background: "white", border: "2px solid var(--border)"
                            }}
                        />
                    </Row>

                    <Row label="Cuisine Type" hint="required">
                        <select value={cuisine} onChange={e => setCuisine(e.target.value)} style={{ ...sel, width: "100%" }}>
                            {(cuisines.length > 0 ? cuisines : CUISINES_WITH_DEFAULTS).map(c => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </select>
                    </Row>

                    <Row label="Price Level" hint="Auto = use cuisine typicals">
                        <Toggle
                            value={priceTier}
                            onChange={setPriceTier}
                            choices={[["", "Auto"], ["1", "$"], ["2", "$$"], ["3", "$$$"], ["4", "$$$$"]]}
                        />
                    </Row>

                    {/* Advanced overrides */}
                    <button
                        onClick={() => setShowAdvanced(v => !v)}
                        style={{
                            background: "transparent", border: "1px solid var(--border)", borderRadius: 12,
                            color: "var(--text-main)", fontSize: 12, fontWeight: 700,
                            padding: "10px 20px", cursor: "pointer", marginBottom: 24, width: "100%",
                            transition: "all 0.2s"
                        }}
                    >
                        {showAdvanced ? "Hide" : "Show"} attribute overrides (optional)
                    </button>

                    {showAdvanced && (
                        <div style={{
                            background: "#F7F7F7", border: "1px solid var(--border)",
                            borderRadius: 16, padding: "24px", marginBottom: 24,
                            animation: "fadeIn 0.3s ease-out"
                        }}>
                            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 20, fontWeight: 700, textTransform: "uppercase" }}>
                                Attributes are set to 'No' by default
                            </div>

                            {[
                                ["has_delivery", "Delivery"],
                                ["has_takeout", "Takeout"],
                                ["has_outdoor_seating", "Outdoor Seating"],
                                ["good_for_kids", "Kid-Friendly"],
                                ["has_reservations", "Reservations"],
                                ["has_wifi", "Free WiFi"],
                                ["has_alcohol", "Alcohol"],
                                ["has_tv", "Has TV"],
                                ["good_for_groups", "Good for Groups"],
                            ].map(([k, label]) => (
                                <Row key={k} label={label}>
                                    <Toggle
                                        value={attrs[k]}
                                        onChange={v => setAttr(k, v)}
                                        choices={[["1", "Yes"], ["0", "No"]]}
                                    />
                                </Row>
                            ))}

                            <Row label="Noise Level">
                                <Toggle
                                    value={noiseLevel}
                                    onChange={setNoiseLevel}
                                    choices={NOISE_OPTIONS.map(n => [n, n.replace("_", " ")])}
                                />
                            </Row>
                        </div>
                    )}

                    {error && <ErrorCard message={error} />}

                    <button
                        onClick={handleRun}
                        disabled={loading}
                        style={{
                            background: loading ? "#EBEBEB" : "var(--primary)",
                            border: "none", borderRadius: 20, color: loading ? "var(--text-secondary)" : "white",
                            fontSize: 16, fontWeight: 800,
                            padding: "16px 0", cursor: loading ? "not-allowed" : "pointer",
                            width: "100%", transition: "all 0.3s cubic-bezier(0.2, 0, 0, 1)",
                            boxShadow: loading ? "none" : "0 4px 16px rgba(255, 56, 92, 0.25)"
                        }}
                        onMouseOver={e => !loading && (e.currentTarget.style.transform = "scale(0.98)")}
                        onMouseOut={e => !loading && (e.currentTarget.style.transform = "scale(1)")}
                    >
                        {loading ? "Analyzing model..." : "Predict Survival Probability"}
                    </button>

                    {!preloadBanner && (
                        <button
                            onClick={() => { setZipCode("08053"); setCuisine("Japanese"); setPriceTier("2"); }}
                            style={{
                                background: "transparent", border: "none", color: "var(--text-secondary)",
                                fontSize: 12, fontWeight: 600,
                                padding: "12px 0", cursor: "pointer", width: "100%", marginTop: 8,
                                textDecoration: "underline"
                            }}
                        >
                            Try example: Japanese · 08053
                        </button>
                    )}
                </div>
            </div>

            {/* ── Right: results ── */}
            <div style={{ overflowY: "auto", background: "var(--bg)" }}>
                {loading
                    ? <Loader text="Running XGBoost prediction + SHAP analysis…" />
                    : result
                        ? <ResultPanel result={result} />
                        : (
                            <div style={{
                                display: "flex", flexDirection: "column", alignItems: "center",
                                justifyContent: "center", height: "100%", gap: 20, color: "var(--text-secondary)",
                                animation: "fadeIn 0.6s ease-out"
                            }}>

                                <div style={{ fontSize: 18, textAlign: "center", lineHeight: 1.6, fontWeight: 500, color: "var(--text-main)" }}>
                                    Your survival prediction <br /> will appear here
                                </div>
                                <p style={{ fontSize: 14, maxWidth: 300, textAlign: "center", color: "var(--text-secondary)" }}>
                                    Fill in the form to get an AI-driven probability score and feature breakdown.
                                </p>
                            </div>
                        )
                }
            </div>
        </div>
    );
}

// ── ResultPanel ───────────────────────────────────────────────────────────────
function ResultPanel({ result }) {
    const prob = result.survival_probability;
    const signalLabel = result.survival_signal?.label || "medium";
    const sc = {
        high: { color: "#008A05", bg: "#EAFAEA" },
        medium: { color: "#E67E22", bg: "#FFF8E1" },
        low: { color: "#C13515", bg: "#FFF0F0" },
        very_low: { color: "#C13515", bg: "#FFF0F0" }
    }[signalLabel];

    const market = result.market_context;
    const factors = result.top_survival_factors || [];
    const gap = result.cuisine_gap;
    const maxAbs = factors.length > 0
        ? Math.max(...factors.map(f => Math.abs(f.shap_value ?? f.global_importance ?? 0)))
        : 1;

    return (
        <div style={{ padding: "48px 60px", animation: "fadeIn 0.5s ease-out" }}>

            {/* ── Probability gauge ── */}
            <div style={{ marginBottom: 48 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 16, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Survival Probability
                </div>

                {/* Big probability number */}
                <div style={{ display: "flex", alignItems: "flex-end", gap: 24, marginBottom: 24 }}>
                    <div style={{
                        fontSize: 96, fontWeight: 800, letterSpacing: "-6px", lineHeight: 0.8,
                        color: sc.color
                    }}>
                        {Math.round(prob * 100)}%
                    </div>
                    <div style={{ paddingBottom: 8 }}>
                        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-main)" }}>
                            likely based on model
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4, fontWeight: 600 }}>
                            {result.cuisine} in {result.zip_code}
                        </div>
                    </div>
                </div>

                {/* Probability bar */}
                <div style={{ height: 12, background: "#F1F1F1", borderRadius: 6, overflow: "hidden", marginBottom: 24 }}>
                    <div style={{
                        height: "100%", width: `${Math.round(prob * 100)}%`,
                        background: sc.color,
                        borderRadius: 6, transition: "width 0.8s cubic-bezier(0.2, 0, 0, 1)",
                    }} />
                </div>

                {/* Signal Badge */}
                <div style={{
                    background: sc.bg, border: `1px solid ${sc.color}22`,
                    borderRadius: 16, padding: "24px",
                    fontSize: 16, color: sc.color, lineHeight: 1.6, fontWeight: 600
                }}>
                    <span style={{ fontSize: 24, marginRight: 12 }}>{prob > 0.7 ? "✨" : prob > 0.4 ? "⚖️" : "⚠️"}</span>
                    {result.survival_signal?.signal}
                </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 60 }}>
                <div>
                    {/* ── Market context ── */}
                    <div style={{ marginBottom: 48 }}>
                        <SectionTitle>Market context ({market.city}, NJ)</SectionTitle>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginBottom: 20 }}>
                            <StatBox value={`${Math.round(market.closure_rate * 100)}%`} label="Closure Rate"
                                color={market.closure_rate > 0.35 ? "#C13515" : market.closure_rate > 0.2 ? "#E67E22" : "#008A05"} />
                            <StatBox value={market.opportunity_score} label="Opp Score" color="var(--primary)" />
                        </div>
                        <RiskBadge risk={market.risk} />
                    </div>

                    {/* ── Cuisine gap ── */}
                    {gap && (
                        <div style={{ marginBottom: 48 }}>
                            <SectionTitle>Market Density</SectionTitle>
                            <div style={{
                                background: "white", border: "1px solid var(--border)",
                                borderRadius: 16, padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.02)"
                            }}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                                    <span style={{ fontSize: 14, color: "var(--text-secondary)", fontWeight: 600 }}>
                                        Local competitors:
                                    </span>
                                    <span style={{ fontSize: 14, color: gap.local_count === 0 ? "#008A05" : "var(--text-main)", fontWeight: 700 }}>
                                        {gap.local_count === 0 ? "None" : `${gap.local_count} existing`}
                                    </span>
                                </div>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                                    <span style={{ fontSize: 14, color: "var(--text-secondary)", fontWeight: 600 }}>
                                        Regional demand signal:
                                    </span>
                                    <span style={{ fontSize: 14, color: "var(--text-main)", fontWeight: 700 }}>
                                        {gap.neighbor_demand} venues
                                    </span>
                                </div>
                                <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16, marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <span style={{ fontSize: 14, color: "var(--text-secondary)", fontWeight: 600 }}>
                                        Calculated Gap:
                                    </span>
                                    <span style={{
                                        fontSize: 20, color: "var(--primary)", fontWeight: 800,
                                    }}>
                                        {gap.gap_score.toFixed(1)}
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div>
                    {/* ── SHAP / survival factors ── */}
                    {factors.length > 0 && (
                        <div style={{ marginBottom: 48 }}>
                            <SectionTitle>
                                {result.shap_available ? "Top Predictive Factors" : "Global Feature Importance"}
                            </SectionTitle>
                            <div style={{ marginBottom: 24 }}>
                                {factors.map(f => (
                                    <ShapFactor key={f.feature} factor={f} maxAbs={maxAbs} />
                                ))}
                            </div>
                            <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--text-secondary)", fontWeight: 600 }}>
                                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#008A05" }} /> Positive for survival
                                </span>
                                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#C13515" }} /> Increases closure risk
                                </span>
                            </div>
                        </div>
                    )}

                    {/* ── Concept applied ── */}
                    <div>
                        <SectionTitle>Profile Details</SectionTitle>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                            {Object.entries(result.concept_applied || {}).map(([k, v]) => {
                                if (v === null || v === undefined) return null;
                                const label = k.replace(/^has_|^good_for_/, "").replace(/_/g, " ");
                                const isOn = v === 1 || v === true;
                                return (
                                    <span key={k} style={{
                                        background: isOn ? "#EAFAEA" : "#F7F7F7",
                                        border: `1px solid ${isOn ? "rgba(0,138,5,0.1)" : "var(--border)"}`,
                                        color: isOn ? "#008A05" : "var(--text-secondary)",
                                        borderRadius: 8, padding: "6px 12px",
                                        fontSize: 12, textTransform: "capitalize", fontWeight: 600
                                    }}>
                                        {isOn ? "✓ " : ""}{label}
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
