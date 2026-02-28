// src/api.js  — all backend API calls in one place
const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
  ).toString();
  const url = `${BASE}${path}${qs ? "?" + qs : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  getCuisines: () => get("/meta/cuisines"),
  getModelInfo: () => get("/meta/model"),
  getOpportunities: (params) => get("/opportunities", params),
  getOpportunity: (zip) => get(`/opportunity/${zip}`),
  getRecommendations: (params) => get("/recommendations", params),
  predict: (body) => post("/predict", body),
};
