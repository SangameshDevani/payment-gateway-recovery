import React, { useState, useEffect, useRef } from "react";

function useCountUp(target, duration = 1100) {
  const [value, setValue] = useState(0);
  const startRef = useRef(null);
  const reduceMotion = useRef(
    typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (reduceMotion.current) {
      setValue(target);
      return;
    }
    startRef.current = null;
    let raf;
    const step = (ts) => {
      if (!startRef.current) startRef.current = ts;
      const progress = Math.min(1, (ts - startRef.current) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(target * eased);
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return value;
}

export default function MetricCard({ label, value, prefix = "", suffix = "", accent, sub, isInt = true }) {
  const animated = useCountUp(value || 0);
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: accent }}>
        {prefix}
        {isInt ? Math.round(animated).toLocaleString("en-IN") : animated.toFixed(1)}
        {suffix}
      </div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}
