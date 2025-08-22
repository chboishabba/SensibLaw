def evaluate(checklist, story_tags: set[str]):
    """Evaluate a checklist against a set of story tags.

    Args:
        checklist: Mapping containing ``id``, ``factors`` and ``logic``.
        story_tags: Set of tags derived from the story.

    Returns:
        dict with ``id`` of the checklist, ``factors`` results and ``passed`` flag.
    """
    factor_results = []
    context = {}
    for factor in checklist.get("factors", []):
        tags = set(factor.get("tags", []))
        matched = bool(tags & story_tags)
        factor_results.append(
            {
                "id": factor.get("id"),
                "title": factor.get("title", ""),
                "passed": matched,
            }
        )
        context[factor.get("id")] = matched

    logic = checklist.get("logic", "")
    try:
        passed = bool(eval(logic, {"__builtins__": {}}, context)) if logic else all(context.values())
    except Exception:
        passed = False

    return {"id": checklist.get("id"), "factors": factor_results, "passed": passed}
