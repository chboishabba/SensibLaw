import json
from pathlib import Path

import pytest

from sensiblaw.api import routes


TEXT = (
    "The operator must keep records within 7 days.\n"
    "A person must not enter the area on the premises.\n"
    "The licence holder must notify on commencement and ceases upon revocation."
)

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "snapshots" / "s7"


def _load_snapshot(name: str) -> dict:
    path = SNAPSHOT_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _extract_obligations():
    return routes.ObligationRequest(text=TEXT, source_id="doc")


@pytest.mark.parametrize(
    "name, payload_fn",
    [
        ("query", lambda: routes.obligations_query(_extract_obligations())),
        ("explanation", lambda: routes.obligations_explain(_extract_obligations())),
        (
            "alignment",
            lambda: routes.obligations_alignment(
                routes.AlignmentRequest(old_text=TEXT.split("\n")[0], new_text=TEXT, source_id="doc")
            ),
        ),
        ("projections_actor", lambda: routes.obligations_projections("actor", _extract_obligations())),
        ("projections_action", lambda: routes.obligations_projections("action", _extract_obligations())),
        ("projections_clause", lambda: routes.obligations_projections("clause", _extract_obligations())),
        ("projections_timeline", lambda: routes.obligations_projections("timeline", _extract_obligations())),
        (
            "activation",
            lambda: routes.obligations_activate(
                routes.ActivationRequest(
                    text=TEXT,
                    source_id="doc",
                    facts=routes.FactEnvelopeModel.model_validate(
                        {"facts": [{"key": "upon commencement", "value": True}]}
                    ),
                )
            ),
        ),
    ],
)
def test_obligation_payload_snapshots(name: str, payload_fn):
    expected = _load_snapshot(name)
    actual = json.loads(json.dumps(payload_fn(), ensure_ascii=False))
    assert actual == expected, f"{name} payload deviated from snapshot"
import pytest

pytestmark = pytest.mark.redflag
