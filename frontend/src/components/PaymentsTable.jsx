import React from "react";
import { Search, Ban, ChevronRight } from "lucide-react";
import Badge from "./Badge.jsx";
import { STATUS_META, ACTION_META, rootCauseLabel, fmtINR } from "../constants.js";

export default function PaymentsTable({
  payments,
  statusFilter, setStatusFilter,
  causeFilter, setCauseFilter,
  boundedOnly, setBoundedOnly,
  query, setQuery,
  boundedPaymentIds,
  onSelect,
  causeOptions,
}) {
  const filtered = payments.filter((p) => {
    if (statusFilter !== "all" && p.recovery_status !== statusFilter) return false;
    if (causeFilter !== "all" && p.root_cause !== causeFilter) return false;
    if (boundedOnly && !boundedPaymentIds.has(p.id)) return false;
    if (query) {
      const q = query.toLowerCase();
      const inId = p.razorpay_payment_id?.toLowerCase().includes(q);
      const inInstrument = p.instrument_fingerprint?.toLowerCase().includes(q);
      if (!inId && !inInstrument) return false;
    }
    return true;
  });

  return (
    <div className="table-panel">
      <div className="table-toolbar">
        <div className="search-box">
          <Search size={14} color="var(--text-faint)" />
          <input
            placeholder="Search payment ID or instrument…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All statuses</option>
          <option value="recovered">Recovered</option>
          <option value="failed">Failed</option>
          <option value="escalated">Escalated</option>
          <option value="pending">Pending</option>
        </select>
        <select value={causeFilter} onChange={(e) => setCauseFilter(e.target.value)}>
          <option value="all">All root causes</option>
          {causeOptions.map((c) => (
            <option key={c} value={c}>{rootCauseLabel(c)}</option>
          ))}
        </select>
        <button
          className={`toggle-btn ${boundedOnly ? "active" : ""}`}
          onClick={() => setBoundedOnly((v) => !v)}
        >
          <Ban size={13} /> Bounded only
        </button>
        <span className="result-count">{filtered.length} of {payments.length}</span>
      </div>

      <table>
        <thead>
          <tr>
            <th>Payment</th>
            <th>Amount</th>
            <th>Root cause</th>
            <th>Action</th>
            <th>Status</th>
            <th>Instrument</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 && (
            <tr className="empty-row"><td colSpan={7}>No payments match these filters.</td></tr>
          )}
          {filtered.map((p, idx) => {
            const statusMeta = STATUS_META[p.recovery_status] || STATUS_META.pending;
            const actionMeta = ACTION_META[p.recovery_action || "undecided"];
            const ActionIcon = actionMeta.icon;
            return (
              <tr
                key={p.id}
                className="row-enter"
                style={{ animationDelay: `${Math.min(idx, 14) * 22}ms` }}
                onClick={() => onSelect(p)}
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") onSelect(p); }}
              >
                <td className="cell-id">{p.razorpay_payment_id}</td>
                <td className="cell-amount">{fmtINR(p.amount)}</td>
                <td>{rootCauseLabel(p.root_cause)}</td>
                <td>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--text-dim)" }}>
                    <ActionIcon size={13} /> {actionMeta.label}
                  </span>
                </td>
                <td><Badge color={statusMeta.color}>{statusMeta.label}</Badge></td>
                <td className="cell-id">{p.instrument_fingerprint || "—"}</td>
                <td><ChevronRight size={15} className="row-chevron" /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
