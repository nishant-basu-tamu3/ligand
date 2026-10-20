"""The one tool an agent sees. Shared by the benchmark (token accounting) and the real MCP server."""

EMIT_DESC = (
    "Get information or perform a lookup across all connected systems without choosing tools. "
    "Describe the goal in one sentence; give what you already know in `have` (name->value: ids, names, dates, filters); "
    "list the field names you need in `want`. Returns {t, rows} with only the wanted fields. "
    "If the reply has `ask`, call again with pick={t,k} choosing a candidate by index. "
    "If it has `need`, call again using one of the listed `fields` names. "
    "Pass prev=[t, true|false] to report whether the previous rows were correct."
)

EMIT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "description": "one sentence: what you want"},
        "have": {"type": "object", "description": "known facts, name->value"},
        "want": {"type": "array", "items": {"type": "string"}, "description": "field names to return"},
        "prev": {"type": "array", "description": "[ticket, was_correct] for the previous result"},
        "pick": {"type": "object", "description": "{t, k}: answer to an `ask`"},
    },
    "required": ["goal", "want"],
}

EMIT_DEF = {"name": "emit", "description": EMIT_DESC, "inputSchema": EMIT_INPUT_SCHEMA}
