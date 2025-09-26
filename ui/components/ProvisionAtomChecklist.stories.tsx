import React from "react";
import ProvisionAtomChecklist, {
  ProvisionAtomNode,
} from "./ProvisionAtomChecklist";

const sampleAtoms: ProvisionAtomNode[] = [
  {
    id: "atom-1",
    label: "Native title holders must authorise agreements",
    role: "principle",
    notes: "Derived from subsection 223(1)(a).",
    proof: { status: "proven", confidence: 0.92, evidenceCount: 3 },
    principle: {
      id: "principle-1",
      title: "Authorisation principle",
      summary: "Agreements affecting native title require free, prior and informed consent from recognised holders.",
      citation: "#/proof-tree/statute/Provision#NTA:s223",
      tags: ["consent", "representation"],
    },
    children: [
      {
        id: "atom-1a",
        label: "Meeting convened with notice to prescribed body corporate",
        role: "fact",
        proof: { status: "proven", confidence: 0.88 },
      },
      {
        id: "atom-1b",
        label: "Resolution passed with 75% majority",
        role: "fact",
        proof: { status: "contested", evidenceCount: 1 },
        notes: "The minutes reference proxies that are under review.",
      },
    ],
  },
  {
    id: "atom-2",
    label: "Agreements must satisfy procedural fairness",
    role: "principle",
    proof: { status: "pending", evidenceCount: 0 },
    principle: {
      id: "principle-2",
      title: "Procedural fairness",
      summary: "Processes must provide affected parties an opportunity to be heard before approval.",
      tags: ["procedure"],
    },
  },
];

export default {
  title: "ProvisionAtoms/Checklist",
  component: ProvisionAtomChecklist,
};

export const DefaultChecklist = () => (
  <ProvisionAtomChecklist title="Section 223 atoms" atoms={sampleAtoms} />
);

export const DenseChecklist = () => (
  <ProvisionAtomChecklist title="Compact view" atoms={sampleAtoms} dense />
);
