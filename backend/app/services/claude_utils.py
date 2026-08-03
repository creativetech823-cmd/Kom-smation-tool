def extract_json_text(content_blocks) -> str:
    """Pull the text block out of a Claude response (skipping thinking blocks)
    and strip markdown code fences if the model wrapped its JSON in one."""

    text_block = next(b for b in content_blocks if b.type == "text")
    raw = text_block.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw
