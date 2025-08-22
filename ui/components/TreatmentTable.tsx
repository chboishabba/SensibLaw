import React, { useEffect, useState } from "react";

interface TreatmentRecord {
  id: string;
  caseName: string;
  treatment: string;
  citationId?: string;
  provisionId?: string;
}

interface TreatmentTableProps {
  caseId: string;
}

const TreatmentTable: React.FC<TreatmentTableProps> = ({ caseId }) => {
  const [records, setRecords] = useState<TreatmentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/cases/${caseId}/treatments`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load treatments");
        return r.json();
      })
      .then((data) => setRecords(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (loading) return <div>Loading treatments…</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <table className="treatment-table">
      <thead>
        <tr>
          <th>Case</th>
          <th>Treatment</th>
          <th>Proof Tree</th>
        </tr>
      </thead>
      <tbody>
        {records.map((rec) => {
          const link = rec.citationId
            ? `#/proof-tree/case/${rec.citationId}`
            : rec.provisionId
            ? `#/proof-tree/statute/${rec.provisionId}`
            : undefined;
          return (
            <tr key={rec.id}>
              <td>{rec.caseName}</td>
              <td>{rec.treatment}</td>
              <td>{link ? <a href={link}>View</a> : null}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default TreatmentTable;
