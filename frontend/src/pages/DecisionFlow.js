import React, { useState } from "react";

const NJ_ZIPS = [
    "08002", "08003", "08004", "08007", "08009", "08010", "08012", "08016", "08018", "08020",
    "08021", "08022", "08026", "08027", "08028", "08029", "08030", "08031", "08033", "08034",
    "08035", "08036", "08045", "08046", "08048", "08049", "08051", "08052", "08053", "08054",
    "08055", "08057", "08059", "08060", "08062", "08063", "08065", "08066", "08068", "08069",
    "08070", "08071", "08075", "08077", "08078", "08079", "08080", "08081", "08083", "08084",
    "08085", "08086", "08088", "08089", "08090", "08091", "08093", "08094", "08096", "08097",
    "08098", "08102", "08103", "08104", "08105", "08106", "08107", "08108", "08109", "08110",
    "08312", "08318", "08322", "08328", "08344", "08505", "08518", "08530", "08554", "08608",
    "08609", "08610", "08611", "08618", "08619", "08628", "08629", "08638", "08648",
];

export default function DecisionFlow({ cuisines, onNavigate }) {
    const [path, setPath] = useState(null); // "cuisine" | "location"
    const [cuisine, setCuisine] = useState("");
    const [zip, setZip] = useState("");

    const goToCuisine = () => {
        onNavigate("recommendations", { cuisine: cuisine || undefined });
    };

    const goToLocation = () => {
        if (!zip) return;
        onNavigate("opportunities", { zip });
    };

    return (
        <div style={{
            minHeight: "100%", display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            padding: "64px 40px", animation: "fadeIn 0.4s ease-out",
        }}>
            {/* Header */}
            <div style={{ textAlign: "center", marginBottom: 56, maxWidth: 560 }}>
                <h1 style={{
                    fontSize: 36, fontWeight: 800, letterSpacing: "-1.5px",
                    color: "var(--text-main)", marginBottom: 14,
                }}>
                    Where do you want to start?
                </h1>
                <p style={{ fontSize: 17, color: "var(--text-secondary)", fontWeight: 500, lineHeight: 1.6 }}>
                    Tell us what you already know and we'll take you straight to the right analysis.
                </p>
            </div>

            {/* Step 1 — Two path tiles */}
            {!path && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, width: "100%", maxWidth: 720 }}>
                    <PathTile
                        icon=""
                        title="I have a cuisine in mind"
                        subtitle="Recommendations"
                        desc="Find the best NJ markets for your specific restaurant concept."
                        onClick={() => setPath("cuisine")}
                    />
                    <PathTile
                        icon=""
                        title="I have a location in mind"
                        subtitle="Market Gaps"
                        desc="See which cuisines are most underserved in a specific zip code."
                        onClick={() => setPath("location")}
                    />
                </div>
            )}

            {/* Step 2A — Cuisine picker */}
            {path === "cuisine" && (
                <div style={{
                    background: "white", border: "1px solid var(--border)",
                    borderRadius: 28, padding: "48px 40px", maxWidth: 520, width: "100%",
                    boxShadow: "var(--shadow)", animation: "fadeIn 0.3s ease-out",
                }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 6 }}>
                        Cuisine → Recommendations
                    </div>
                    <h2 style={{ fontSize: 24, fontWeight: 800, color: "var(--text-main)", marginBottom: 28, letterSpacing: "-0.5px" }}>
                        What type of restaurant?
                    </h2>

                    <select
                        value={cuisine}
                        onChange={e => setCuisine(e.target.value)}
                        style={sel}
                        autoFocus
                    >
                        <option value="">General / Any cuisine</option>
                        {cuisines.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>

                    <div style={{ display: "flex", gap: 12, marginTop: 28 }}>
                        <button onClick={() => setPath(null)} style={ghostBtn}>← Back</button>
                        <button onClick={goToCuisine} style={primaryBtn}>
                            Find Best Markets →
                        </button>
                    </div>
                </div>
            )}

            {/* Step 2B — Zip picker */}
            {path === "location" && (
                <div style={{
                    background: "white", border: "1px solid var(--border)",
                    borderRadius: 28, padding: "48px 40px", maxWidth: 520, width: "100%",
                    boxShadow: "var(--shadow)", animation: "fadeIn 0.3s ease-out",
                }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 6 }}>
                        Location → Market Gaps
                    </div>
                    <h2 style={{ fontSize: 24, fontWeight: 800, color: "var(--text-main)", marginBottom: 28, letterSpacing: "-0.5px" }}>
                        Which NJ zip code?
                    </h2>

                    <select
                        value={zip}
                        onChange={e => setZip(e.target.value)}
                        style={sel}
                        autoFocus
                    >
                        <option value="">Select a zip code…</option>
                        {NJ_ZIPS.map(z => <option key={z} value={z}>{z}</option>)}
                    </select>

                    <div style={{ display: "flex", gap: 12, marginTop: 28 }}>
                        <button onClick={() => setPath(null)} style={ghostBtn}>← Back</button>
                        <button onClick={goToLocation} disabled={!zip} style={{
                            ...primaryBtn,
                            opacity: zip ? 1 : 0.5,
                            cursor: zip ? "pointer" : "not-allowed",
                        }}>
                            View Market Gaps →
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Path tile ──────────────────────────────────────────────────────────────────

function PathTile({ icon, title, subtitle, desc, onClick }) {
    const [hovered, setHovered] = useState(false);
    return (
        <button
            onClick={onClick}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                background: "white",
                border: `2px solid ${hovered ? "var(--primary)" : "var(--border)"}`,
                borderRadius: 24, padding: "40px 32px",
                cursor: "pointer", textAlign: "left",
                boxShadow: hovered ? "0 8px 28px rgba(255,56,92,0.12)" : "0 2px 8px rgba(0,0,0,0.06)",
                transform: hovered ? "translateY(-4px)" : "none",
                transition: "all 0.25s cubic-bezier(0.2, 0, 0, 1)",
            }}
        >
            <div style={{ fontSize: 40, marginBottom: 16 }}>{icon}</div>
            <div style={{
                fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.5px",
                color: "var(--primary)", marginBottom: 8,
            }}>
                → {subtitle}
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-main)", marginBottom: 10 }}>
                {title}
            </div>
            <div style={{ fontSize: 14, color: "var(--text-secondary)", fontWeight: 500, lineHeight: 1.6 }}>
                {desc}
            </div>
            <div style={{
                marginTop: 24, fontSize: 13, fontWeight: 700, color: "var(--primary)",
                display: "flex", alignItems: "center", gap: 4,
                opacity: hovered ? 1 : 0, transition: "opacity 0.2s",
            }}>
                Get started →
            </div>
        </button>
    );
}

const sel = {
    background: "#F7F7F7", border: "1px solid #EBEBEB", borderRadius: 14,
    color: "var(--text-main)", fontSize: 15, fontWeight: 600,
    padding: "16px 18px", outline: "none", cursor: "pointer", width: "100%",
    appearance: "none",
};

const primaryBtn = {
    flex: 1, background: "var(--primary)", border: "none", borderRadius: 14,
    color: "white", fontSize: 15, fontWeight: 700, padding: "16px 0",
    cursor: "pointer", boxShadow: "0 4px 12px rgba(255,56,92,0.25)",
    transition: "all 0.2s",
};

const ghostBtn = {
    background: "white", border: "1px solid var(--border)", borderRadius: 14,
    color: "var(--text-secondary)", fontSize: 14, fontWeight: 700, padding: "16px 20px",
    cursor: "pointer", transition: "all 0.2s",
};
