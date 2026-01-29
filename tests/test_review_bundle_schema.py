import json
from pathlib import Path

import jsonschema
import yaml


def test_review_bundle_example_validates():
    schema = yaml.safe_load(Path("schemas/review.bundle.v1.schema.yaml").read_text())
    payload = json.loads(Path("examples/review_bundle_minimal.json").read_text())
    jsonschema.validate(payload, schema)
