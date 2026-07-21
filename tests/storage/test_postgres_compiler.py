from src.storage.postgres_compiler import PostgresCompilerStore


class _Cursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, values=()):
        self.calls.append((" ".join(statement.split()), values))

    def fetchone(self):
        return None


class _Connection:
    def __init__(self):
        self.calls = []
        self.committed = False

    def cursor(self):
        return _Cursor(self.calls)

    def commit(self):
        self.committed = True


def test_postgres_store_persists_declarations_builds_and_structured_pnf_rows():
    connection = _Connection()
    store = PostgresCompilerStore(connection)
    factor = {
        "factor_ref": "factor:one",
        "factor_type": "semantic.eventuality",
        "closure_state": "requires_external_resolution",
        "metadata": {},
    }
    compilation = {
        "document_ref": "document:one",
        "content_sha256": "a" * 64,
        "media_type": "text/plain",
        "artifacts": {
            "canonical_text": "A person acted.",
            "semantic_reduction_declarations": [
                {"declaration_ref": "grammar:semantic:predicate:v0_1"}
            ],
            "annotation_layer": {
                "layer_ref": "layer:base",
                "tokenizer_ref": "tokenizer:test",
                "text_sha256": "a" * 64,
                "span_annotations": [],
                "relation_annotations": [],
            },
            "semantic_annotation_layer": None,
            "pnf_graph": {"graph_ref": "graph:one", "factors": [factor]},
            "refined_pnf_graph": {"graph_ref": "graph:one", "factors": [factor]},
            "typed_meets": [],
            "factor_refinements": [],
            "resolution_demands": [
                {
                    "demand_ref": "demand:one",
                    "factor_ref": "factor:one",
                    "factor_type": "semantic.eventuality",
                    "semantic_key": {"factor_ref": "factor:one"},
                }
            ],
        },
    }
    context = {"media_normalization_ref": "media:utf8:v0_1"}

    store.persist(compilation=compilation, context=context, build_key_sha256="key")

    statements = "\n".join(statement for statement, _values in connection.calls)
    assert "INSERT INTO compiler_declaration" in statements
    assert "INSERT INTO compiler_build" in statements
    assert "INSERT INTO compiler_pnf_factor" in statements
    assert "INSERT INTO compiler_resolution_demand" in statements
    assert connection.committed is True
