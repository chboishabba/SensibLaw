import React from "react";

export interface PrincipleCardProps {
  id: string;
  title: string;
  summary: string;
  citation?: string;
  tags?: string[];
}

const cardStyle: React.CSSProperties = {
  border: "1px solid #d0d7de",
  borderRadius: "0.75rem",
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
  padding: "1rem",
  backgroundColor: "#fff",
};

const titleStyle: React.CSSProperties = {
  fontSize: "0.95rem",
  fontWeight: 600,
  margin: "0 0 0.4rem 0",
};

const summaryStyle: React.CSSProperties = {
  fontSize: "0.85rem",
  margin: "0 0 0.6rem 0",
  lineHeight: 1.4,
};

const badgeStyle: React.CSSProperties = {
  backgroundColor: "#f1f5f9",
  borderRadius: "999px",
  color: "#334155",
  display: "inline-flex",
  fontSize: "0.7rem",
  fontWeight: 600,
  marginRight: "0.4rem",
  padding: "0.2rem 0.6rem",
};

const PrincipleCard: React.FC<PrincipleCardProps> = ({
  id,
  title,
  summary,
  citation,
  tags = [],
}) => {
  return (
    <article style={cardStyle} data-principle-id={id}>
      <header style={{ marginBottom: "0.5rem" }}>
        <h4 style={titleStyle}>{title}</h4>
        {citation ? (
          <a
            href={citation}
            style={{ color: "#2563eb", fontSize: "0.75rem", textDecoration: "none" }}
          >
            View source
          </a>
        ) : null}
      </header>
      <p style={summaryStyle}>{summary}</p>
      {tags.length ? (
        <div aria-label="principle tags">
          {tags.map((tag) => (
            <span key={tag} style={badgeStyle}>
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
};

export default PrincipleCard;
