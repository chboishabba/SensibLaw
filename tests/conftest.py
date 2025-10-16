from __future__ import annotations

from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile("ci")
