from __future__ import annotations


def test_policy_installs_bounded_typing_leaf_executor_before_durability() -> None:
    from src.policy import parallel_typing_tail as tail
    from src.policy.typing_leaf_hot_path_execution import execute_leaves_bounded

    # The durability installer wraps the executor captured after the hot-path
    # installer.  Depending on whether durable work is enabled, the public seam
    # is either the bounded implementation itself or a wrapper that names it as
    # its captured original.  The implementation must remain reachable and the
    # unbounded all-futures comprehension must not be restored.
    installed = tail._execute_leaves
    if installed is execute_leaves_bounded:
        return
    closure = getattr(installed, "__closure__", None) or ()
    captured = {
        cell.cell_contents
        for cell in closure
        if callable(getattr(cell, "cell_contents", None))
    }
    assert execute_leaves_bounded in captured
