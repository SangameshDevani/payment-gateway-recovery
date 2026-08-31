import React, { useState, useEffect } from "react";

export default function CauseBar({ label, count, total, color, delay = 0 }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setWidth(total ? (count / total) * 100 : 0), 120 + delay);
    return () => clearTimeout(t);
  }, [count, total, delay]);

  return (
    <div className="cause-row">
      <div className="cause-label">{label}</div>
      <div className="cause-track">
        <div className="cause-fill" style={{ width: `${width}%`, background: color }} />
      </div>
      <div className="cause-count">{count}</div>
    </div>
  );
}
