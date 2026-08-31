const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${options.method || "GET"} ${path} failed (${res.status}): ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  listPayments: () => request("/payments"),
  getPaymentAudit: (id) => request(`/payments/${id}/audit`),
  getMetrics: () => request("/metrics"),
  runPipeline: () => request("/pipeline/run", { method: "POST" }),
};

export { BASE_URL };
