import React from "react";

export default function Badge({ children, color }) {
  return (
    <span
      className="badge"
      style={{ color, borderColor: color + "55", background: color + "14" }}
    >
      {children}
    </span>
  );
}
