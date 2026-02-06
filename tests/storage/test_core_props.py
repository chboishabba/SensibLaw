import string

from hypothesis import HealthCheck, given, settings, strategies as st

from src.storage.core import Storage

json_value = st.one_of(
    st.integers(),
    st.booleans(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(alphabet=string.ascii_letters),
)

data_strategy = st.dictionaries(
    st.text(alphabet=string.ascii_letters, min_size=1),
    json_value,
    max_size=5,
)


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(type_str=st.text(alphabet=string.ascii_letters, min_size=1, max_size=10), data=data_strategy)
def test_node_round_trip(tmp_path, type_str, data):
    store = Storage(tmp_path / "test.db")
    try:
        node_id = store.insert_node(type_str, data)
        node = store.get_node(node_id)
        assert node is not None
        assert node.id == node_id
        assert node.type == type_str
        assert node.data == data
    finally:
        store.close()
