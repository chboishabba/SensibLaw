# GWB Public Handoff Narrative Summary

This checked handoff artifact is a bounded public-entity slice over the
George W. Bush wiki timeline lane. It is meant to show what the system
understands from public material in plain language, not just as JSON.

## What the system recovered cleanly

- George W. Bush subject of review by Supreme Court of the United States.
- George W. Bush vetoed State Children's Health Insurance Program.
- George W. Bush vetoed SCHIP.
- George W. Bush signed Genetic Information Nondiscrimination Act.
- George W. Bush vetoed Stem Cell Research Enhancement Act.
- George W. Bush was linked to court review by United States district court.
- George W. Bush was linked to court review by United States district court.
- George W. Bush was linked to court review by United States Court of Appeals for the Sixth Circuit.
- George W. Bush was linked to court review by United States district court.
- George W. Bush was linked to court review by United States Court of Appeals for the Sixth Circuit.
- George W. Bush signed Military Commissions Act of 2006.
- George W. Bush signed Military Commissions Act.
- George W. Bush signed Syria Accountability Act.
- George W. Bush nominated John Roberts.
- George W. Bush nominated John Roberts.
- John Roberts was confirmed by U.S. Senate.
- George W. Bush nominated Harriet Miers.
- George W. Bush nominated Samuel Alito.
- Samuel Alito was confirmed by U.S. Senate.

## What the system kept as review lanes

- Clear Skies legislative and Clean Air amendment lane: status=matched, support=direct, matched_events=1, candidate_events=1.
- Congressional subpoena and immunity litigation lane: status=matched, support=direct, matched_events=1, candidate_events=8.
- Department of Defense institutional review lane: status=matched, support=direct, matched_events=1, candidate_events=2.
- Genetic discrimination legislation lane: status=matched, support=direct, matched_events=1, candidate_events=2.
- Iraq war authorization and related executive decision path: status=matched, support=broad_cue, matched_events=18, candidate_events=27.
- Military commissions and detainee-review lane: status=matched, support=broad_cue, matched_events=1, candidate_events=6.
- NSA surveillance and review/litigation lane: status=matched, support=direct, matched_events=2, candidate_events=4.
- SCHIP veto and congressional funding lane: status=matched, support=broad_cue, matched_events=1, candidate_events=8.
- Stem cell veto and bioethics legislation lane: status=matched, support=broad_cue, matched_events=3, candidate_events=5.
- Supreme Court nominations and legitimacy lane: status=matched, support=broad_cue, matched_events=2, candidate_events=6.
- Syria sanctions legislation lane: status=matched, support=direct, matched_events=1, candidate_events=1.

## What the system refused to overresolve

- `White House` stayed unresolved.
- `Bush administration` stayed unresolved.
- `the President` stayed unresolved.
- `the President` stayed unresolved.
- `Bush administration` stayed unresolved.
- `White House` stayed unresolved.
- `White House` stayed unresolved.

## Why this matters for Zelph

- It is a public and relatively safe real-world handoff slice.
- It contains both positive public-law relations and explicit review items.
- It preserves the boundary that SensibLaw extracts and reviews, while
  Zelph reasons downstream over a bounded exported graph.

