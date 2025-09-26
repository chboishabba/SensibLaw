import React from "react";

export type ProofStatus = "proven" | "contested" | "pending";

export interface ProofState {
  status: ProofStatus;
  confidence?: number;
  evidenceCount?: number;
}

interface ProofStateBadgeProps {
  proof: ProofState;
}

const STATUS_LABELS: Record<ProofStatus, string> = {
  proven: "Proven",
  contested: "Contested",
  pending: "Pending",
};

const STATUS_COLORS: Record<ProofStatus, string> = {
  proven: "#2e7d32",
  contested: "#f9a825",
  pending: "#546e7a",
};

const ProofStateBadge: React.FC<ProofStateBadgeProps> = ({ proof }) => {
  const { status, confidence, evidenceCount } = proof;
  const label = STATUS_LABELS[status];
  const color = STATUS_COLORS[status];
  const extra: string[] = [];

  if (typeof confidence === "number") {
    extra.push(`${Math.round(confidence * 100)}% confidence`);
  }

  if (typeof evidenceCount === "number") {
    const noun = evidenceCount === 1 ? "source" : "sources";
    extra.push(`${evidenceCount} ${noun}`);
  }

  return (
    <span
      style={{
        alignItems: "center",
        borderRadius: "9999px",
        border: `1px solid ${color}`,
        color,
        display: "inline-flex",
        fontSize: "0.75rem",
        fontWeight: 600,
        gap: "0.4rem",
        padding: "0.1rem 0.6rem",
      }}
      aria-label={extra.length ? `${label} (${extra.join(", ")})` : label}
      data-status={status}
    >
      <span
        aria-hidden="true"
        style={{
          backgroundColor: color,
          borderRadius: "50%",
          display: "inline-block",
          height: "0.55rem",
          width: "0.55rem",
        }}
      />
      <span>{label}</span>
      {extra.length ? <span style={{ color: "inherit" }}>· {extra.join(", ")}</span> : null}
    </span>
  );
};

export default ProofStateBadge;
