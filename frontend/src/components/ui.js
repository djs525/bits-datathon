// src/components/ui.js — shared UI primitives for all pages

import React from "react";

// ── ZipCard ─────────────────────────────────────────────────────────────────

export function ZipCard({ z, selected, onClick }) {
    const topGap = z.top_cuisine_gaps?.[0];

    return (
        <div
            onClick={onClick}
            style={{
                background: "var(--bg)",
                border: `1px solid ${selected ? "var(--primary)" : "var(--border)"}`,
                borderRadius: 16, padding: "20px 24px", cursor: onClick ? "pointer" : "default",
                transition: "all 0.25s cubic-bezier(0.2, 0, 0, 1)",
                boxShadow: selected ? "0 6px 20px rgba(255,56,92,0.15)" : "0 2px 8px rgba(0,0,0,0.04)",
                position: "relative",
            }}
            onMouseOver={e => !selected && (e.currentTarget.style.boxShadow = "0 6px 16px rgba(0,0,0,0.08)")}
            onMouseOut={e => !selected && (e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.04)")}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                    <div style={{ fontWeight: 700, fontSize: 18, color: "var(--text-main)" }}>
                        {z.zip}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2, fontWeight: 500 }}>
                        {z.city}, NJ
                    </div>
                </div>
                <div style={{ textAlign: "right" }}>
                    <div style={{
                        fontSize: 20, color: "var(--primary)", fontWeight: 800,
                        lineHeight: 1
                    }}>
                        {z.opportunity_score}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", marginTop: 4 }}>
                        Score
                    </div>
                </div>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap", alignItems: "center" }}>
                <RiskBadge risk={z.risk} />
                {topGap && (
                    <span style={{
                        background: "#F7F7F7", border: "1px solid #EBEBEB",
                        color: "var(--text-main)", borderRadius: 6, padding: "4px 10px",
                        fontSize: 11, fontWeight: 600
                    }}>
                        {topGap.cuisine} gap {topGap.gap_score.toFixed(1)}
                    </span>
                )}
                <span style={{
                    color: "var(--text-secondary)", fontSize: 12, fontWeight: 500, marginLeft: "auto"
                }}>
                    {z.total_restaurants} venues · {z.avg_stars}★
                </span>
            </div>
        </div>
    );
}

// ── RiskBadge ────────────────────────────────────────────────────────────────

export function RiskBadge({ risk }) {
    const cfg = {
        low: { bg: "#EAFAEA", color: "#008A05", label: "Low Risk" },
        medium: { bg: "#FFF8E1", color: "#E67E22", label: "Med Risk" },
        high: { bg: "#FFF0F0", color: "#C13515", label: "High Risk" },
    };
    const c = cfg[risk] || cfg.high;
    return (
        <span style={{
            background: c.bg, color: c.color,
            borderRadius: 6, padding: "4px 10px",
            fontSize: 11, fontWeight: 700,
            display: "inline-flex", alignItems: "center"
        }}>
            {c.label}
        </span>
    );
}

// ── GapBar ───────────────────────────────────────────────────────────────────

export function GapBar({ value, max }) {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    return (
        <div style={{ height: 6, background: "#F1F1F1", borderRadius: 3, overflow: "hidden" }}>
            <div style={{
                height: "100%", width: `${pct}%`,
                background: "var(--primary)",
                borderRadius: 3, transition: "width 0.6s cubic-bezier(0.2, 0, 0, 1)",
            }} />
        </div>
    );
}

// ── StatBox ───────────────────────────────────────────────────────────────────

export function StatBox({ value, label, color = "var(--text-main)" }) {
    return (
        <div style={{
            background: "#FFFFFF", border: "1px solid var(--border)",
            borderRadius: 12, padding: "16px", textAlign: "left",
            boxShadow: "0 2px 4px rgba(0,0,0,0.02)"
        }}>
            <div style={{
                fontSize: 22, fontWeight: 800, color, lineHeight: 1.2,
            }}>
                {value}
            </div>
            <div style={{
                fontSize: 11, color: "var(--text-secondary)",
                marginTop: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.4px"
            }}>
                {label}
            </div>
        </div>
    );
}

// ── SectionTitle ─────────────────────────────────────────────────────────────

export function SectionTitle({ children }) {
    return (
        <div style={{
            fontSize: 16, color: "var(--text-main)",
            marginBottom: 16, fontWeight: 700, letterSpacing: "-0.2px"
        }}>
            {children}
        </div>
    );
}

// ── Loader ───────────────────────────────────────────────────────────────────

export function Loader({ text = "Loading…" }) {
    return (
        <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", padding: 60, gap: 20,
        }}>
            <div className="spinner" style={{
                width: 40, height: 40, border: "3px solid #F1F1F1",
                borderTop: "3px solid var(--primary)", borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
            }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            <div style={{ fontSize: 14, color: "var(--text-secondary)", fontWeight: 500 }}>
                {text}
            </div>
        </div>
    );
}

// ── EmptyState ────────────────────────────────────────────────────────────────

export function EmptyState({ text, icon = "🔍" }) {
    return (
        <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", height: "100%", minHeight: 300,
            color: "var(--text-secondary)", gap: 16, padding: 40,
        }}>
            <div style={{ fontSize: 48 }}>{icon}</div>
            <div style={{
                fontSize: 16, textAlign: "center", whiteSpace: "pre-line",
                lineHeight: 1.6, fontWeight: 500
            }}>
                {text}
            </div>
        </div>
    );
}

// ── ErrorCard ─────────────────────────────────────────────────────────────────

export function ErrorCard({ message }) {
    return (
        <div style={{
            background: "#FFF0F0", border: "1px solid rgba(193, 53, 21, 0.1)",
            borderRadius: 12, padding: "16px 20px", margin: "16px 0",
            fontSize: 14, color: "#C13515", fontWeight: 500,
            display: "flex", gap: 12, alignItems: "center"
        }}>
            <span style={{ fontSize: 18 }}>⚠️</span>
            {message || "An error occurred. Is the backend running?"}
        </div>
    );
}
