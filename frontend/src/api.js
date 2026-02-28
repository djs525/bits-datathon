// src/api.js  — all backend API calls in one place
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
  ).toString();
  const url = `${BASE}${path}${qs ? "?" + qs : ""}`;
  console.log(`[API] GET ${url}`);
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.text();
    console.error(`[API] ERROR ${res.status}:`, err);
    throw new Error(`API error ${res.status}: ${err}`);
  }
  const data = await res.json();
  console.log(`[API] ← ${path}`, data);
  return data;
}

async function post(path, body) {
  const url = `${BASE}${path}`;
  console.log(`[API] POST ${url}`, body);
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error(`[API] ERROR ${res.status}:`, err);
    throw new Error(`API error ${res.status}: ${err}`);
  }
  const data = await res.json();
  console.log(`[API] ← ${path}`, data);
  return data;
}

export const api = {
  getCuisines: () => get("/meta/cuisines"),
  getModelInfo: () => get("/meta/model"),
  getOpportunities: (params) => get("/opportunities", params),
  getOpportunity: (zip) => get(`/opportunity/${zip}`),
  search: (params) => get("/search", params),
  getWeakspots: (params) => get("/weakspots", params),
  predict: (body) => post("/predict", body),
  getRecommendations: () => get("/recommendations"),
};
