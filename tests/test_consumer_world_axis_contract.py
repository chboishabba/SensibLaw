from __future__ import annotations

import pytest

from src.policy.external_demand import ExternalNeedKind
from src.storage.postgres.external_demand_runtime_store import ConsumerWorldAxisContract


def test_contract_requires_at_least_one_numeric_selector() -> None:
    contract = ConsumerWorldAxisContract(
        contract_ref="world-type",
        need_kind=ExternalNeedKind.PROPERTY_ENRICHMENT,
        axis_kind=1,
        provider_property_numeric_id=31,
    )
    with pytest.raises(ValueError, match="numeric demand selector"):
        contract.validate()


def test_property_contract_requires_axis_and_property() -> None:
    contract = ConsumerWorldAxisContract(
        contract_ref="world-type",
        need_kind=ExternalNeedKind.PROPERTY_ENRICHMENT,
        expected_target_kind=1,
    )
    with pytest.raises(ValueError, match="requires axis and provider property"):
        contract.validate()


def test_discovery_contract_rejects_property_coordinates() -> None:
    contract = ConsumerWorldAxisContract(
        contract_ref="discover-world-candidate",
        need_kind=ExternalNeedKind.CANDIDATE_DISCOVERY,
        axis_kind=1,
        provider_property_numeric_id=31,
        expected_target_kind=1,
    )
    with pytest.raises(ValueError, match="do not accept property-axis"):
        contract.validate()


def test_sparse_numeric_property_contract_is_valid() -> None:
    ConsumerWorldAxisContract(
        contract_ref="instance-of-for-object-residual",
        need_kind=ExternalNeedKind.PROPERTY_ENRICHMENT,
        axis_kind=1,
        provider_property_numeric_id=31,
        expected_target_kind=1,
        residual_type_symbol_id=42,
        minimum_source_epoch=1_781_481_600,
    ).validate()
