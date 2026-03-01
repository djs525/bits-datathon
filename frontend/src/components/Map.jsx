import React, { useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";

const NJ_ZIP_COORDS = {
    "07836": [40.84, -74.71],
    "08001": [39.55, -75.33], "08002": [39.93, -75.03], "08003": [39.90, -74.99],
    "08004": [39.78, -74.88], "08005": [39.81, -74.83], "08007": [39.87, -75.05],
    "08009": [39.79, -74.93], "08010": [40.05, -74.88], "08012": [39.76, -75.05],
    "08016": [40.07, -74.85], "08018": [39.80, -74.95], "08020": [39.80, -75.10],
    "08021": [39.80, -74.96], "08022": [40.03, -74.72], "08026": [39.88, -75.03],
    "08027": [39.83, -75.19], "08028": [39.79, -75.13], "08029": [39.84, -75.07],
    "08030": [39.88, -75.11], "08031": [39.87, -75.07], "08033": [39.90, -75.04],
    "08034": [39.91, -74.99], "08035": [39.88, -75.10], "08036": [39.93, -74.79],
    "08037": [39.63, -74.83], "08041": [39.72, -74.95], "08043": [39.87, -74.96],
    "08045": [39.87, -75.02], "08046": [40.06, -74.87], "08048": [39.96, -74.80],
    "08049": [39.84, -75.02], "08051": [39.77, -75.18], "08052": [40.01, -74.95],
    "08053": [39.88, -74.93], "08054": [39.94, -74.91], "08055": [39.86, -74.82],
    "08056": [39.79, -75.20], "08057": [39.95, -74.91], "08059": [39.82, -75.14],
    "08060": [39.99, -74.79], "08061": [39.74, -75.20], "08062": [39.67, -75.23],
    "08063": [39.87, -75.07], "08065": [40.00, -75.01], "08066": [39.78, -75.22],
    "08067": [39.70, -75.23], "08068": [39.97, -74.73], "08069": [39.73, -75.30],
    "08070": [39.67, -75.30], "08071": [39.73, -75.11], "08072": [39.71, -75.16],
    "08074": [39.71, -75.20], "08075": [40.02, -74.95], "08077": [40.00, -75.01],
    "08078": [39.86, -75.10], "08079": [39.63, -75.38], "08080": [39.75, -75.05],
    "08081": [39.75, -74.98], "08083": [39.84, -75.04], "08084": [39.83, -75.02],
    "08085": [39.79, -75.15], "08086": [39.82, -75.14], "08088": [39.87, -74.78],
    "08089": [39.69, -74.85], "08090": [39.80, -75.18], "08091": [39.80, -74.95],
    "08093": [39.86, -75.13], "08094": [39.68, -75.07], "08096": [39.84, -75.13],
    "08097": [39.84, -75.05], "08098": [39.73, -75.16], "08100": [39.94, -75.12],
    "08102": [39.95, -75.12], "08103": [39.93, -75.12], "08104": [39.92, -75.10],
    "08105": [39.95, -75.09], "08106": [39.89, -75.05], "08107": [39.87, -75.05],
    "08108": [39.90, -75.06], "08109": [39.92, -75.02], "08110": [39.97, -75.06],
    "08302": [39.48, -75.23], "08312": [39.65, -75.08], "08318": [39.55, -75.15],
    "08322": [39.60, -75.13], "08328": [39.55, -75.08], "08343": [39.60, -75.30],
    "08344": [39.58, -74.98], "08501": [40.22, -74.53], "08505": [40.10, -74.72],
    "08518": [40.12, -74.78], "08530": [40.38, -74.70], "08534": [40.35, -74.74],
    "08554": [40.12, -74.72], "08560": [40.33, -74.87], "08601": [40.22, -74.76],
    "08608": [40.22, -74.76], "08609": [40.22, -74.72], "08610": [40.19, -74.70],
    "08611": [40.19, -74.74], "08618": [40.25, -74.79], "08619": [40.22, -74.68],
    "08620": [40.16, -74.63], "08628": [40.26, -74.82], "08629": [40.21, -74.73],
    "08638": [40.26, -74.78], "08648": [40.28, -74.72], "08690": [40.23, -74.63],
    "08691": [40.22, -74.60], "08825": [40.53, -74.86],
};

const RISK_COLORS = {
    low: { fill: "#00A699", stroke: "#009688" },
    medium: { fill: "#FC642D", stroke: "#E5572A" },
    high: { fill: "#FF385C", stroke: "#E02D50" },
};

function ChangeView({ center, zoom }) {
    const map = useMap();
    if (center) map.setView(center, zoom, { animate: true, duration: 0.5 });
    return null;
}

const OpportunityMap = ({ results, selectedZip, onZipSelect }) => {
    const NJ_CENTER = [39.95, -74.95];

    const center = useMemo(() => {
        if (selectedZip && NJ_ZIP_COORDS[selectedZip]) return NJ_ZIP_COORDS[selectedZip];
        return NJ_CENTER;
    }, [selectedZip]);

    const zoom = selectedZip ? 12 : 9;

    const maxScore = useMemo(() => {
        if (!results.length) return 1;
        return Math.max(...results.map(z => z.opportunity_score), 1);
    }, [results]);

    return (
        <div style={{
            height: "100%", width: "100%", borderRadius: 14,
            overflow: "hidden", border: "1px solid #DDDDDD",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        }}>
            <MapContainer
                center={NJ_CENTER}
                zoom={9}
                style={{ height: "100%", width: "100%" }}
                zoomControl={false}
            >
                <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
                />
                <ChangeView center={center} zoom={zoom} />
                {results.map(z => {
                    const coords = NJ_ZIP_COORDS[z.zip];
                    if (!coords) return null;
                    const isSelected = z.zip === selectedZip;
                    const riskColor = RISK_COLORS[z.risk] || RISK_COLORS.medium;
                    const radius = 5 + (z.opportunity_score / maxScore) * 14;
                    return (
                        <CircleMarker
                            key={z.zip}
                            center={coords}
                            pathOptions={{
                                color: isSelected ? "#222222" : riskColor.stroke,
                                fillColor: riskColor.fill,
                                fillOpacity: isSelected ? 0.9 : 0.65,
                                weight: isSelected ? 3 : 1.5,
                            }}
                            radius={isSelected ? radius + 3 : radius}
                            eventHandlers={{ click: () => onZipSelect(z.zip) }}
                        >
                            <Tooltip direction="top" offset={[0, -8]} opacity={0.97}>
                                <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                                    <strong>{z.zip}</strong> — {z.city}<br />
                                    Score: <b>{z.opportunity_score}</b> · Risk: <b style={{ color: riskColor.fill }}>{z.risk}</b>
                                </div>
                            </Tooltip>
                        </CircleMarker>
                    );
                })}
            </MapContainer>
        </div>
    );
};

export default OpportunityMap;
