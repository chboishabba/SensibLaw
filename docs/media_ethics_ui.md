Media Ethics Guidelines (UI-Enforced)
=====================================

These are interaction-shaping constraints designed to make unethical use hard
and obvious. They are not “terms of service.” The UI must actively resist
interpretation and protect epistemic boundaries.

Core principle
--------------
**Media users are observers, not interpreters.** SB never helps media decide
what something means—only what exists, what does not, and what is verifiable.

1. Default Media Mode: Evidence-First, Meaning-Later
----------------------------------------------------
### 1.1 No narrative surface by default
- No summaries
- No timelines with implied causality
- No “story” views

Default view is ledger-style:
- timestamps
- event hashes
- source types
- absence markers

UI copy:
> “This view shows what is recorded, not what it means.”

2. Interpretation Friction (Deliberate Slowness)
------------------------------------------------
Any attempt to interpret requires explicit escalation.

Example flow:

User clicks “Explain this sequence”

UI responds:
> “You are requesting interpretation.
> This action may introduce bias or error.
> Choose justification:
> ☐ Editorial hypothesis
> ☐ Investigative lead
> ☐ Legal inquiry
> ☐ Academic analysis”

Each choice:
- is logged
- is watermarked
- is visible to downstream readers

3. Absence Is Always Visible (and Loud)
---------------------------------------
Media UI must foreground what is not known.

For every view:
- “No data from X”
- “No corroboration for Y”
- “This source was unavailable”

Visual rule:
- Absence rendered as white space with labels
- Not greyed-out text (grey implies minimization)

4. Hypothesis vs Commitment Locking
-----------------------------------
Media often collapses hypothesis → claim. SB forbids this silently.

UI rule:
- Hypotheses are:
  - orange
  - dashed borders
  - time-expiring
- Commitments are:
  - black
  - solid
  - immutable

Attempting to export a hypothesis as fact triggers:
> “This item is not a commitment.
> Exporting it as such would be misleading.”

5. Provenance Watermarking (Non-removable)
------------------------------------------
Every export includes:
- source class (sensor, human, system)
- chain completeness indicator
- confidence of presence (not truth)

Media cannot:
- crop provenance
- hide uncertainty
- reformat without markers

This prevents “clean screenshots” used for manipulation.

6. No Pattern Surfacing for Media Accounts
------------------------------------------
SB never:
- surfaces correlations
- highlights trends
- suggests motifs

Media must do that outside SB, and SB records that boundary.

7. “Right to Opacity” UI Signal
-------------------------------
Some data is intentionally opaque.

Instead of “restricted” or “redacted”, SB shows:
> “This information exists but is not interpretable here.”

This trains ethical restraint instead of suspicion.

8. Ethical Exhaustion Guard
---------------------------
If a media user repeatedly:
- escalates hypotheses
- exports partial views
- ignores absence warnings

SB slows down:
- rate limits
- adds more friction text
- requires rationale re-entry

Not punitive—cooling.

Hostile Cross-Examination Simulation (Line by Line)
===================================================
Context: SB records were used by a journalist. Defense counsel attempts to
 discredit SB in court.

Q1: “Isn’t your system just another surveillance database?”
A: “No. It does not infer intent, behavior, or meaning. It records events and
    absences with explicit limits.”

Q2: “But it remembers everything, doesn’t it?”
A: “No. It records only what was explicitly ingested. Absence is recorded as
    absence, not filled.”

Q3: “Who decides what gets recorded?”
A: “The operator selects sources. Each source is marked as authoritative or
    observational.”

Q4: “So if something isn’t there, the system just ignores it?”
A: “No. The system explicitly marks missing data as missing.”

Q5: “Does SB tell journalists what happened?”
A: “No. It prevents the system from asserting narratives.”

Q6: “But patterns can still be inferred by the user, correct?”
A: “Yes. SB does not prevent human interpretation. It prevents the system from
    asserting one.”

Q7: “Can SB be manipulated to support a false story?”
A: “Any tool can be misused. SB logs interpretation steps and preserves
    provenance so misuse is detectable.”

Q8: “Isn’t that just post-hoc accountability?”
A: “No. The UI enforces friction before interpretation, not after.”

Q9: “Who benefits from this system?”
A: “People who need to show what they did not know, not what they claim to
    know.”

Q10: “Could this system have prevented misinformation in past cases?”
A: “It cannot prevent belief. It can prevent systems from asserting belief as
    fact.”

Final framing sentence (court-ready)
------------------------------------
> “SB does not decide what happened.
> It preserves the conditions under which a human may responsibly decide.”
