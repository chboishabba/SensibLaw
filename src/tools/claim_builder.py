"""Interactive claim builder tool."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def _to_yaml(data: dict[str, object]) -> str:
    """Convert a simple dict to YAML without external deps."""
    lines: list[str] = []

    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def build_claim(claims_dir: Path | None = None) -> Path:
    """Run an interactive session to build a claim.

    Parameters
    ----------
    claims_dir:
        Directory where claim YAML files will be stored. Defaults to
        ``data/claims`` relative to the project root.

    Returns
    -------
    Path
        The path to the saved claim file.
    """

    if claims_dir is None:
        claims_dir = Path(__file__).resolve().parents[2] / "data" / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)

    claimant = input("Claimant: ").strip()
    respondent = input("Respondent: ").strip()
    description = input("Description: ").strip()
    amount = input("Amount: ").strip()
    receipt_str = input("Receipt references (comma separated): ").strip()
    receipts = [r.strip() for r in receipt_str.split(",") if r.strip()]

    claim_id = uuid4().hex
    claim = {
        "id": claim_id,
        "claimant": claimant,
        "respondent": respondent,
        "description": description,
        "amount": amount,
        "receipts": receipts,
    }

    out_path = claims_dir / f"{claim_id}.yaml"
    out_path.write_text(_to_yaml(claim))
    print(f"Saved claim {claim_id} to {out_path}")
    return out_path


__all__ = ["build_claim"]
