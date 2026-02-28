import React from "react";

// ── ZipCard ──────────────────────────────────────────────────────────────────
export const ZipCard = ({ z, selected, onClick }) => (
    <div
        onClick={onClick}
        style={{
            padding: "16px 20px",
            background: selected ? "rgba(0, 229, 160, 0.1)" : "#1a1a26",
            border: `1px solid ${selected ? "#00e5a0" : "#2a2a3a"}`,
            borderRadius: 12,
            cursor: "pointer",
            transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
        }}
    >
        <div>
            <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: -0.5 }}>{z.zip}</div>
            <div style={{ fontSize: 13, color: "#6b6b8a", marginTop: 2 }}>{z.city}</div>
        </div>
        <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#00e5a0" }}>{z.opportunity_score}</div>
            <div style={{ fontSize: 10, color: "#6b6b8a", textTransform: "uppercase", letterSpacing: 0.5 }}>Score</div>
        </div>
    </div>
);

// ── Loader ────────────────────────────────────────────────────────────────────
export const Loader = ({ text }) => (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 16 }}>
        <div className="spinner" style={{
            width: 40, height: 40, border: "3px solid rgba(0,229,160,0.1)", borderTopColor: "#00e5a0",
            borderRadius: "50%", animation: "spin 1s linear infinite"
        }} />
        <div style={{ fontSize: 14, color: "#6b6b8a", fontWeight: 600 }}>{text}</div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
);

// ── EmptyState ────────────────────────────────────────────────────────────────
export const EmptyState = ({ icon = "🔍", text }) => (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", opacity: 0.5 }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>{icon}</div>
        <div style={{ fontSize: 14, textAlign: "center", whiteSpace: "pre-line", lineHeight: 1.6 }}>{text}</div>
    </div>
);

// ── SectionTitle ──────────────────────────────────────────────────────────────
export const SectionTitle = ({ children }) => (
    <div style={{
        fontSize: 11, fontWeight: 800, color: "#6b6b8a",
        textTransform: "uppercase", letterSpacing: 1.5,
        marginBottom: 12, display: "flex", alignItems: "center", gap: 12
    }}>
        {children}
        <div style={{ flex: 1, height: 1, background: "#1a1a26" }} />
    </div>
);

// ── StatBox ───────────────────────────────────────────────────────────────────
export const StatBox = ({ value, label, color = "#e8e8f0" }) => (
    <div style={{ background: "#0a0a0f", border: "1px solid #1a1a26", borderRadius: 10, padding: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 800, color, letterSpacing: -0.5 }}>{value}</div>
        <div style={{ fontSize: 9, color: "#6b6b8a", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 4 }}>{label}</div>
    </div>
);

// ── RiskBadge ─────────────────────────────────────────────────────────────────
export const RiskBadge = ({ risk }) => {
    const colors = {
        low: { bg: "rgba(0, 229, 160, 0.1)", text: "#00e5a0", border: "rgba(0, 229, 160, 0.3)" },
        medium: { bg: "rgba(255, 209, 102, 0.1)", text: "#ffd166", border: "rgba(255, 209, 102, 0.3)" },
        high: { bg: "rgba(255, 108, 108, 0.1)", text: "#ff6c6c", border: "rgba(255, 108, 108, 0.3)" },
    };
    const c = colors[risk] || colors.medium;
    return (
        <div style={{
            padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 800,
            textTransform: "uppercase", letterSpacing: 1,
            background: c.bg, color: c.text, border: `1px solid ${c.border}`
        }}>
            {risk} risk
        </div>
    );
};

// ── GapBar ────────────────────────────────────────────────────────────────────
export const GapBar = ({ value, max }) => (
    <div style={{ height: 6, background: "#1a1a26", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${(value / max) * 100}%`, background: "linear-gradient(90deg, #7c6cff, #00e5a0)", borderRadius: 3 }} />
    </div>
);
