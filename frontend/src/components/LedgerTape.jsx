import React from "react";
import { STATUS_META, rootCauseLabel, fmtINR } from "../constants.js";

export default function LedgerTape({ payments }) {
  const executed = payments.filter((p) => p.recovery_status !== "pending");

  if (executed.length === 0) {
    return (
      <div className="tape-outer">
        <div className="tape-track tape-track--static">
          <span className="tape-item">
            <span className="tape-id">No executed payments yet</span>
            <span className="tape-sep">▸</span>
            <span className="tape-cause">Run the pipeline to populate the ledger</span>
          </span>
        </div>
      </div>
    );
  }

  const items = [...executed, ...executed]; // duplicate for seamless loop

  return (
    <div className="tape-outer">
      <div className="tape-track">
        {items.map((p, idx) => {
          const meta = STATUS_META[p.recovery_status] || STATUS_META.pending;
          return (
            <span className="tape-item" key={`${p.id}-${idx}`}>
              <span className="tape-dot" style={{ background: meta.color }} />
              <span className="tape-id">{p.razorpay_payment_id}</span>
              <span className="tape-sep">▸</span>
              <span className="tape-cause">{rootCauseLabel(p.root_cause)}</span>
              <span className="tape-sep">▸</span>
              <span style={{ color: meta.color }}>{meta.label}</span>
              <span className="tape-sep">▸</span>
              <span className="tape-amt">
                {p.recovery_status === "recovered" ? fmtINR(p.recovered_amount) : fmtINR(p.amount)}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
