import React, { useEffect, useState } from "react";
import { X, Ban, CheckCircle2, ArrowDownRight, CircleDot } from "lucide-react";
import Badge from "./Badge.jsx";
import { api } from "../api.js";
import { STATUS_META, ACTOR_META, rootCauseLabel, fmtINR } from "../constants.js";

export default function AuditDrawer({ payment, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!payment) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getPaymentAudit(payment.id)
      .then((data) => { if (!cancelled) setLogs(data); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [payment]);

  if (!payment) return null;
  const statusMeta = STATUS_META[payment.recovery_status] || STATUS_META.pending;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label={`Audit trail for ${payment.razorpay_payment_id}`}>
        <div className="drawer-head">
          <div>
            <div className="drawer-eyebrow">Audit trail</div>
            <div className="drawer-title">{payment.razorpay_payment_id}</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-summary">
          <div className="drawer-summary-row">
            <span className="drawer-summary-key">Amount</span>
            <span className="drawer-summary-val mono">{fmtINR(payment.amount)}</span>
          </div>
          <div className="drawer-summary-row">
            <span className="drawer-summary-key">Customer</span>
            <span className="drawer-summary-val mono">{payment.customer_email || "—"}</span>
          </div>
          <div className="drawer-summary-row">
            <span className="drawer-summary-key">Instrument</span>
            <span className="drawer-summary-val mono">{payment.instrument_fingerprint || "—"}</span>
          </div>
          <div className="drawer-summary-row">
            <span className="drawer-summary-key">Root cause</span>
            <span className="drawer-summary-val">{rootCauseLabel(payment.root_cause)}</span>
          </div>
          <div className="drawer-summary-row">
            <span className="drawer-summary-key">Status</span>
            <Badge color={statusMeta.color}>{statusMeta.label}</Badge>
          </div>
        </div>

        <div className="drawer-timeline-label">Timeline</div>

        {loading && <div className="drawer-state">Loading audit log…</div>}
        {error && <div className="drawer-state drawer-state-error">Couldn't load audit log: {error}</div>}
        {!loading && !error && logs.length === 0 && (
          <div className="drawer-state">No audit entries yet — this payment hasn't been processed by the pipeline.</div>
        )}

        <div className="timeline">
          {logs.map((entry, idx) => {
            const actorMeta = ACTOR_META[entry.actor] || ACTOR_META.system;
            return (
              <div className="timeline-entry" key={entry.id ?? idx}>
                <div className="timeline-rail">
                  <span className="timeline-node" style={{ background: actorMeta.color }} />
                  {idx < logs.length - 1 && <span className="timeline-line" />}
                </div>
                <div className="timeline-body">
                  <div className="timeline-top">
                    <span className="timeline-actor" style={{ color: actorMeta.color }}>
                      {actorMeta.label}
                    </span>
                    <span className="timeline-action mono">{entry.action}</span>
                    {entry.was_bounded_by_rule && (
                      <span className="timeline-bounded">
                        <Ban size={11} /> bounded
                      </span>
                    )}
                  </div>
                  <div className="timeline-detail">{entry.detail}</div>
                  <div className={`timeline-outcome outcome-${entry.outcome}`}>
                    {entry.outcome === "success" && <CheckCircle2 size={12} />}
                    {entry.outcome === "failure" && <ArrowDownRight size={12} />}
                    {entry.outcome === "skipped" && <CircleDot size={12} />}
                    {entry.outcome}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
