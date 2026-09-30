from src.storage.postgres.semantic_reader_projection import (
    ReaderIntent,
    compile_reader_intent,
    load_reader_source_payment,
)


class StubCursor:
    def __init__(self, row):
        self.row = row
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.row


def test_source_defers_when_exact_span_is_not_persisted():
    cursor = StubCursor(None)
    payment = load_reader_source_payment(
        cursor,
        source_revision_ref="source-revision:mabo-hca23",
        span_ref="span:mabo:radical-title-native-title",
    )

    decision = compile_reader_intent(payment, ReaderIntent.OPEN_SOURCE)

    assert decision.state == "defer"
    assert decision.residual_ref == "reader-residual:exact-authority-span"


def test_persisted_exact_span_executes_source_without_promoting_truth():
    text = "Native title survived the Crown's acquisition of sovereignty."
    start = text.index("Native title")
    end = len(text)
    cursor = StubCursor(
        (
            "source-revision:mabo-hca23",
            "document:mabo-hca23",
            "text/html",
            "abc123",
            text,
            "span:mabo:radical-title-native-title",
            start,
            end,
            "licensed_mention",
            "primary",
        )
    )

    payment = load_reader_source_payment(
        cursor,
        source_revision_ref="source-revision:mabo-hca23",
        span_ref="span:mabo:radical-title-native-title",
    )
    decision = compile_reader_intent(payment, ReaderIntent.OPEN_SOURCE)

    assert payment.exact_authority_span_paid is True
    assert payment.claim_truth_paid is False
    assert payment.literal_span == text[start:end]
    assert decision.state == "execute"
    assert decision.source_locator == (
        "source-revision:mabo-hca23",
        "span:mabo:radical-title-native-title",
    )


def test_persisted_revision_without_span_does_not_execute_source():
    cursor = StubCursor(
        (
            "source-revision:mabo-hca23",
            "document:mabo-hca23",
            "text/html",
            "abc123",
            "coarse corpus text",
            None,
            None,
            None,
            None,
            "primary",
        )
    )

    payment = load_reader_source_payment(
        cursor,
        source_revision_ref="source-revision:mabo-hca23",
        span_ref="span:mabo:radical-title-native-title",
    )

    assert payment.persisted_source_ready is True
    assert payment.exact_authority_span_paid is False
    assert compile_reader_intent(payment, ReaderIntent.OPEN_SOURCE).state == "defer"


def test_why_remains_deferred_until_a_distinct_proposition_chain_is_paid():
    cursor = StubCursor(None)
    payment = load_reader_source_payment(
        cursor,
        source_revision_ref="source-revision:mabo-hca23",
        span_ref="span:mabo:radical-title-native-title",
    )

    decision = compile_reader_intent(payment, ReaderIntent.WHY)

    assert decision.state == "defer"
    assert decision.residual_ref == "reader-residual:detailed-proposition-chain"
