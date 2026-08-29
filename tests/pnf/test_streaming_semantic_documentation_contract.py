from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


FORMAL_OWNERS = (
    "StreamingSemanticPacmanKernelExact.agda",
    "StreamingPhysicalOverlapReceiptExact.agda",
    "DeltaNativePNFDreamFlowExact.agda",
    "FibreSolverDeltaStreamExact.agda",
    "DirectDeltaCompilerArchitectureExact.agda",
    "DirectDeltaCompilerActivationExact.agda",
    "DirectStreamingRoadmapSynthesisExact.agda",
)


def test_agents_requires_streaming_agda_owners() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/architecture/STREAMING_SEMANTIC_PACMAN.md" in agents
    assert "state(prefix ++ suffix) = continue(state(prefix), suffix)" in agents
    for owner in FORMAL_OWNERS:
        assert owner in agents


def test_streaming_architecture_names_formal_and_runtime_owners() -> None:
    architecture = (
        ROOT / "docs" / "architecture" / "STREAMING_SEMANTIC_PACMAN.md"
    ).read_text(encoding="utf-8")
    assert "src/pnf/streaming_semantic_pacman.py" in architecture
    assert "src/runtime/overlapped_parser_semantic_stream.py" in architecture
    assert "End-of-stream must **not** mean \"start semantic compilation now\"" in architecture
    for owner in FORMAL_OWNERS:
        assert owner in architecture


def test_roadmap_keeps_streaming_before_deeper_persistence_micro_optimization() -> None:
    roadmap = (
        ROOT / "docs" / "architecture" / "DIRECT_STREAMING_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "bounded G3 direct/reference parity" in roadmap
    assert "validate/expand implemented parser-semantic overlap" in roadmap
    assert "revisit partition-keyed graph/provenance persistence only if still dominant" in roadmap
