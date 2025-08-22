import React, { useEffect, useState } from "react";

interface Silhouette {
  fact_tags: Record<string, number>;
  holding_hints: Record<string, number>;
  paragraphs: string[];
}

interface CitationInfo {
  index: number;
  paragraph: string;
  citationId?: string;
  provisionId?: string;
}

interface ComparisonItem {
  type: "fact" | "holding";
  text: string;
  base: CitationInfo;
  candidate?: CitationInfo;
}

interface Comparison {
  base: Silhouette;
  candidate: Silhouette;
  overlaps: ComparisonItem[];
  missing: ComparisonItem[];
}

interface DistinguishPanelProps {
  baseId: string;
  candidateId: string;
}

const DistinguishPanel: React.FC<DistinguishPanelProps> = ({
  baseId,
  candidateId,
}) => {
  const [data, setData] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/distinguish?base=${baseId}&candidate=${candidateId}`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load comparison");
        return r.json();
      })
      .then((d) => setData(d))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [baseId, candidateId]);

  if (loading) return <div>Loading comparison…</div>;
  if (error) return <div>Error: {error}</div>;
  if (!data) return null;

  const renderItem = (
    fact: string,
    side: "base" | "candidate",
    idx: number
  ) => {
    const overlap = data.overlaps.find(
      (o) => o.text === fact && o.type === "fact"
    );
    const missing = data.missing.find(
      (o) => o.text === fact && o.type === "fact"
    );
    const className = overlap
      ? "overlap"
      : missing && side === "base"
      ? "missing"
      : "";
    const info =
      side === "base"
        ? data.base.paragraphs[idx]
        : data.candidate.paragraphs[idx];

    const linkSource = overlap
      ? side === "base"
        ? overlap.base
        : overlap.candidate
      : missing && side === "base"
      ? missing.base
      : undefined;
    const link = linkSource
      ? linkSource.citationId
        ? `#/proof-tree/case/${linkSource.citationId}`
        : linkSource.provisionId
        ? `#/proof-tree/statute/${linkSource.provisionId}`
        : undefined
      : undefined;

    return (
      <div key={`${side}-${fact}`} className={`silhouette-item ${className}`}>
        {link ? <a href={link}>{info}</a> : info}
      </div>
    );
  };

  const baseFacts = Object.keys(data.base.fact_tags);
  const candidateFacts = Object.keys(data.candidate.fact_tags);

  return (
    <div className="distinguish-panel">
      <div className="silhouettes">
        <div className="silhouette-base">
          <h3>Base Case</h3>
          {baseFacts.map((fact) =>
            renderItem(fact, "base", data.base.fact_tags[fact])
          )}
        </div>
        <div className="silhouette-candidate">
          <h3>Candidate Case</h3>
          {candidateFacts.map((fact) =>
            renderItem(fact, "candidate", data.candidate.fact_tags[fact])
          )}
        </div>
      </div>
      <div className="legend">
        <span className="overlap">Overlap</span>
        <span className="missing">Missing</span>
      </div>
    </div>
  );
};

export default DistinguishPanel;
