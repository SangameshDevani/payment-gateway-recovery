import React, { useState, useEffect, useRef } from "react";

export default function RecoveryGauge({ percent = 0, recoveredAmount = 0, atRiskAmount = 0 }) {
  const [animated, setAnimated] = useState(0);
  const reduceMotion = useRef(
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (reduceMotion.current) {
      setAnimated(percent);
      return;
    }
    let raf;
    let start = null;
    const duration = 1400;
    const step = (ts) => {
      if (!start) start = ts;
      const progress = Math.min(1, (ts - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimated(percent * eased);
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [percent]);

  const radius = 72;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(animated, 100) / 100) * circumference;

  return (
    <div className="gauge-wrap">
      <svg width="176" height="176" viewBox="0 0 176 176" className="gauge-svg">
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4CC9F0" />
            <stop offset="100%" stopColor="#34D68C" />
          </linearGradient>
          <filter id="gaugeGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <circle cx="88" cy="88" r={radius} fill="none" stroke="#1B212B" strokeWidth="11" />
        <circle
          cx="88" cy="88" r={radius} fill="none"
          stroke="url(#gaugeGradient)" strokeWidth="11" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          transform="rotate(-90 88 88)" filter="url(#gaugeGlow)"
          style={{ transition: reduceMotion.current ? "none" : "stroke-dashoffset 0.3s linear" }}
        />
      </svg>
      <div className="gauge-center">
        <div className="gauge-percent">{animated.toFixed(1)}%</div>
        <div className="gauge-label">recovered</div>
      </div>
    </div>
  );
}
