"""Typed evidence status. No invented model accuracy or confidence probability."""
def assess(route, facts=None, sources=()):
    facts = facts or {}
    unclear = bool(facts.get("needs_clarification") or facts.get("needs_grid"))
    verified_tool = route == "skill" and not unclear and not facts.get("error")
    return {"status": "needs_clarification" if unclear else "tool_error" if facts.get("error") else "tool_result" if verified_tool else
            ("model_summary" if facts.get("summary") else "source_excerpt") if route == "web" and sources else "needs_review",
            "probability_correct": None, "calibrated": False,
            "basis": "user_working_context" if route == "context" else "deterministic_tool" if route == "skill" else "retrieved_text" if sources else "no_web_evidence" if route == "web" else "local_language_model",
            "requires_review": not verified_tool}
