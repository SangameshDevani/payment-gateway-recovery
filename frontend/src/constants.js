import {
  ArrowUpRight, ArrowDownRight, ShieldAlert, RotateCw, MessageSquareText,
  UserCheck, Clock, HelpCircle,
} from "lucide-react";

export const STATUS_META = {
  recovered: { label: "Recovered", color: "#34D68C", icon: ArrowUpRight },
  failed: { label: "Failed", color: "#F0625C", icon: ArrowDownRight },
  escalated: { label: "Escalated", color: "#E8A33D", icon: ShieldAlert },
  pending: { label: "Pending", color: "#7C8698", icon: Clock },
};

export const ACTION_META = {
  retry: { label: "Retry", icon: RotateCw },
  alt_method_link: { label: "Alt-method link", icon: ArrowUpRight },
  nudge: { label: "Nudge", icon: MessageSquareText },
  escalate: { label: "Escalate", icon: UserCheck },
  undecided: { label: "Not decided", icon: HelpCircle },
};

export const ACTOR_META = {
  rule_engine: { label: "Rule engine", color: "#4CC9F0" },
  gemini: { label: "Gemini", color: "#B98EFF" },
  decision_engine: { label: "Decision engine", color: "#B98EFF" },
  executor: { label: "Executor", color: "#34D68C" },
  system: { label: "System", color: "#7C8698" },
};

export const ROOT_CAUSE_LABELS = {
  insufficient_funds: "Insufficient funds",
  issuer_decline: "Issuer decline",
  otp_timeout: "OTP timeout",
  network_timeout: "Network timeout",
  expired_instrument: "Expired instrument",
  risk_block: "Risk block",
  unknown: "Unknown",
};

export const rootCauseLabel = (key) => ROOT_CAUSE_LABELS[key] || key || "Not classified";

export const fmtINR = (n) => "₹" + Math.round(n || 0).toLocaleString("en-IN");
