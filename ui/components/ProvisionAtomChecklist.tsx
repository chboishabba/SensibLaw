import React from "react";
import PrincipleCard, { PrincipleCardProps } from "./PrincipleCard";
import ProofStateBadge, { ProofState } from "./ProofStateBadge";

export interface ProvisionAtomNode {
  id: string;
  label: string;
  role?: string;
  proof: ProofState;
  principle?: PrincipleCardProps;
  notes?: string;
  children?: ProvisionAtomNode[];
}

export interface ProvisionAtomChecklistProps {
  atoms: ProvisionAtomNode[];
  title?: string;
  dense?: boolean;
}

const listStyle: React.CSSProperties = {
  display: "grid",
  gap: "0.9rem",
  margin: 0,
  padding: 0,
};

const itemStyle: React.CSSProperties = {
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "0.9rem",
  listStyle: "none",
  padding: "0.9rem",
};

const ProvisionAtomChecklist: React.FC<ProvisionAtomChecklistProps> = ({
  atoms,
  title,
  dense = false,
}) => {
  const renderNode = (node: ProvisionAtomNode, depth = 0) => {
    const hasChildren = Boolean(node.children?.length);
    return (
      <li key={node.id} style={{ ...itemStyle, paddingLeft: `${0.9 + depth * 0.6}rem` }}>
        <div
          style={{
            alignItems: "flex-start",
            display: "flex",
            flexDirection: "column",
            gap: dense ? "0.4rem" : "0.6rem",
          }}
        >
          <div
            style={{
              alignItems: "flex-start",
              display: "flex",
              gap: "0.8rem",
              width: "100%",
            }}
          >
            <ProofStateBadge proof={node.proof} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>{node.label}</div>
              {node.role ? (
                <div style={{ color: "#475569", fontSize: "0.75rem" }}>{node.role}</div>
              ) : null}
              {node.notes ? (
                <p style={{ color: "#1e293b", fontSize: "0.8rem", margin: "0.4rem 0 0" }}>
                  {node.notes}
                </p>
              ) : null}
            </div>
          </div>
          {node.principle ? (
            <PrincipleCard {...node.principle} />
          ) : null}
        </div>
        {hasChildren ? (
          <ul style={{ ...listStyle, marginTop: dense ? "0.6rem" : "0.9rem", paddingLeft: "0.6rem" }}>
            {node.children!.map((child) => renderNode(child, depth + 1))}
          </ul>
        ) : null}
      </li>
    );
  };

  return (
    <section aria-label={title ?? "Provision atom checklist"}>
      {title ? (
        <header style={{ marginBottom: "1rem" }}>
          <h3 style={{ fontSize: "1.1rem", margin: 0 }}>{title}</h3>
        </header>
      ) : null}
      <ul style={listStyle}>{atoms.map((atom) => renderNode(atom))}</ul>
    </section>
  );
};

export default ProvisionAtomChecklist;
