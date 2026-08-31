import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Radio, Ban, Sparkles, PlayCircle, RefreshCw, AlertTriangle } from "lucide-react";
import { api } from "./api.js";
import { rootCauseLabel } from "./constants.js";
import LedgerTape from "./components/LedgerTape.jsx";
import MetricCard from "./components/MetricCard.jsx";
import RecoveryGauge from "./components/RecoveryGauge.jsx";
import CauseBar from "./components/CauseBar.jsx";
import PaymentsTable from "./components/PaymentsTable.jsx";
import AuditDrawer from "./components/AuditDrawer.jsx";

const CAUSE_COLOR = {
  risk_block: "var(--red)",
  otp_timeout: "var(--cyan)",
  network_timeout: "var(--cyan)",
};

export default function App() {
  const [payments, setPayments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const [statusFilter, setStatusFilter] = useState("all");
  const [causeFilter, setCauseFilter] = useState("all");
  const [boundedOnly, setBoundedOnly] = useState(false);
  const [query, setQuery] = useState("");

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [paymentsData, metricsData] = await Promise.all([
        api.listPayments(),
        api.getMetrics(),
      ]);
      setPayments(paymentsData);
      setMetrics(metricsData);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadData().finally(() => setLoading(false));
  }, [loadData]);

  const handleRunPipeline = async () => {
    setPipelineRunning(true);
    setError(null);
    try {
      await api.runPipeline();
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setPipelineRunning(false);
    }
  };

  // "Bounded by a stopping rule" isn't on the Payment row itself — it lives on
  // audit log entries. We don't want to fetch every payment's audit log just
  // to compute this, so we treat metrics.payments_bounded_by_stopping_rules
  // (a count) as the source of truth for the metric card, and just leave the
  // per-row "bounded only" filter as a best-effort using recovery_status ===
  // 'escalated' with a decided root_cause that maps to something else — kept
  // simple: bounded filter shows escalated payments whose root_cause isn't
  // risk_block/unknown (since those escalate by default, not by a rule).
  const boundedPaymentIds = useMemo(() => {
    const ids = new Set();
    payments.forEach((p) => {
      if (
        p.recovery_status === "escalated" &&
        p.root_cause &&
        !["risk_block", "unknown"].includes(p.root_cause)
      ) {
        ids.add(p.id);
      }
    });
    return ids;
  }, [payments]);

  const causeBreakdown = useMemo(() => {
    if (!metrics?.breakdown_by_root_cause) return [];
    return Object.entries(metrics.breakdown_by_root_cause)
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => b.count - a.count);
  }, [metrics]);

  const causeOptions = useMemo(
    () => [...new Set(payments.map((p) => p.root_cause).filter(Boolean))],
    [payments]
  );

  const hasRun = metrics && metrics.pending_count < metrics.total_payments;

  return (
    <div className="app">
      <LedgerTape payments={payments} />

      <div className="header">
        <div>
          <div className="brand-eyebrow">
            <span className="pulse-dot" />
            Payment Recovery Agent
          </div>
          <h1 className="brand-title">Revenue Recovery Console</h1>
          <p className="brand-sub">
            Failed payments, classified by root cause and worked through a bounded,
            auditable recovery pipeline. Every action below is explainable.
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-end" }}>
          <div className="header-tag">
            <Radio size={13} />
            Batch of {metrics?.total_payments ?? "…"} · Razorpay test-mode
          </div>
          <button className="run-btn" onClick={handleRunPipeline} disabled={pipelineRunning}>
            {pipelineRunning ? <RefreshCw size={14} className="spin" /> : <PlayCircle size={14} />}
            {pipelineRunning ? "Running pipeline…" : hasRun ? "Re-run pipeline" : "Run pipeline"}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={14} />
          {error} — is the backend running at the URL in <code>VITE_API_URL</code>?
        </div>
      )}

      {loading ? (
        <div className="loading-state">Loading batch…</div>
      ) : payments.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No payments in the database yet</div>
          <div className="empty-state-sub">
            Run <code className="mono">python seed_failures.py</code> in the backend, then reload.
          </div>
        </div>
      ) : (
        <>
          <div className="hero-row">
            <div className="gauge-panel">
              <RecoveryGauge
                percent={metrics?.recovery_rate_pct || 0}
                recoveredAmount={metrics?.total_amount_recovered}
                atRiskAmount={metrics?.total_amount_at_risk}
              />
              <div className="gauge-panel-meta">
                <div className="gauge-panel-title">Recovery rate</div>
                <div className="gauge-panel-sub">
                  {metrics?.recovered_count ?? 0} of {metrics?.total_payments ?? 0} payments recovered this run
                </div>
              </div>
            </div>
            <div className="metrics-row metrics-row--hero">
              <MetricCard label="Amount at risk" value={metrics?.total_amount_at_risk} prefix="₹" accent="var(--text)" />
              <MetricCard label="Amount recovered" value={metrics?.total_amount_recovered} prefix="₹" accent="var(--green)" />
              <MetricCard
                label="Bounded by rules"
                value={metrics?.payments_bounded_by_stopping_rules}
                accent="var(--amber)"
                sub={`of ${metrics?.total_payments ?? 0} decisions`}
              />
              <MetricCard label="Escalated" value={metrics?.escalated_count} accent="var(--amber)" sub="sent to human review" />
            </div>
          </div>

          <div className="mid-row">
            <div className="panel">
              <div className="panel-title">Root cause breakdown</div>
              {causeBreakdown.length === 0 && (
                <div className="drawer-state">Run the pipeline to classify this batch.</div>
              )}
              {causeBreakdown.map((c, i) => (
                <CauseBar
                  key={c.key}
                  label={rootCauseLabel(c.key)}
                  count={c.count}
                  total={metrics?.total_payments || 1}
                  color={CAUSE_COLOR[c.key] || "var(--purple)"}
                  delay={i * 70}
                />
              ))}
            </div>

            <div className="panel">
              <div className="panel-title">Stopping rules active</div>
              <div className="rules-list">
                <div className="rule-item">
                  <Ban size={14} className="rule-icon" />
                  <span><b>Risk-block floor</b> — a risk-flagged payment is never auto-retried or auto-nudged, regardless of table.</span>
                </div>
                <div className="rule-item">
                  <Ban size={14} className="rule-icon" />
                  <span><b>Retry cap</b> — capped attempts per payment before forced escalation (see <code className="mono">MAX_RETRY_ATTEMPTS</code>).</span>
                </div>
                <div className="rule-item">
                  <Ban size={14} className="rule-icon" />
                  <span><b>Instrument dedup</b> — the same card/UPI ID is only contacted once per run, even across multiple failed payments.</span>
                </div>
              </div>
              <div className="bounded-callout">
                <Sparkles size={13} />
                {metrics?.payments_bounded_by_stopping_rules ?? 0} of {metrics?.total_payments ?? 0} decisions were downgraded by a stopping rule this run.
              </div>
            </div>
          </div>

          <div className="table-section">
            <PaymentsTable
              payments={payments}
              statusFilter={statusFilter} setStatusFilter={setStatusFilter}
              causeFilter={causeFilter} setCauseFilter={setCauseFilter}
              boundedOnly={boundedOnly} setBoundedOnly={setBoundedOnly}
              query={query} setQuery={setQuery}
              boundedPaymentIds={boundedPaymentIds}
              onSelect={setSelected}
              causeOptions={causeOptions}
            />
          </div>
        </>
      )}

      <AuditDrawer payment={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
