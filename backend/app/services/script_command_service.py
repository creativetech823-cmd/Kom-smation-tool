import json

from app.config import settings
from app.models.product import (
    GeneratedScript,
    ScriptCommandInput,
    ScriptCommandResult,
    ScriptRegenerateScope,
    ScriptSectionRegenerateInput,
)
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.script_service import regenerate_script_section

_COMMAND_SYSTEM_PROMPT = """You are a professional short-form video ad script editor executing a
user's natural-language instruction on a finished script. The user might ask for something broad
("make the hook more emotional", "mention Ayush Wellness naturally", "rewrite the second line",
"make the CTA stronger", "make this less salesy", "remove repetition", "make it more Gen Z") or
occasionally an explicit full-script rewrite ("rewrite the entire script", "regenerate everything").

Default to a TARGETED edit — touch exactly ONE existing line (hook, body_N, or cta) and leave
everything else completely unchanged. Only set is_full_rewrite=true when the user unambiguously
asks to rewrite/regenerate the whole script, or the instruction genuinely cannot be satisfied by
changing one line (e.g. "make it 30 seconds" on a script that's currently 60 seconds).

If the instruction refers to a line by position ("the second line", "the opening", "the line before
the CTA"), resolve it against the actual script order given below (hook is first, then body lines
in order, then cta is last) and pick that exact line_id.

If targeted: identify the single best line_id for this instruction and write out the COMPLETE
replacement text for that line (not just the changed part) — grounded in the script's actual
content and the product info given below, in the exact same language/register as the original line
(see script language below), never inventing a claim, statistic, or promise that wasn't already in
the script or product info. If the instruction asks to mention the brand/product, weave it in
naturally into the most fitting existing line rather than bolting on a raw brand name.

If a full rewrite is genuinely required, do not write the new script yourself here — just confirm
is_full_rewrite=true and explain why in "why"; the rewrite happens in a separate pass.

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{"is_full_rewrite": boolean, "title": string, "why": string, "line_id": string|null, "suggested_text": string|null}

"title" is a short (2-4 word) label for this change, e.g. "Brand Integration", "Stronger Hook",
"Line Improvement", "Full Rewrite"."""

_SELECTION_SYSTEM_PROMPT = """You are a professional short-form video ad script editor. The user has
selected a specific span of text within one script line and given an instruction for how to improve
JUST that span — everything else in the line, and the rest of the script, must stay untouched.
Rewrite ONLY the selected span according to the instruction (default to a general clarity/impact
improvement pass if the instruction is empty or just "improve this"), in the exact same language/
register as the original, grounded in the actual product/script context below, never inventing a
claim, statistic, or promise that wasn't already there.

Return ONLY the replacement text for the selected span — no prose, no quotes, no markdown fences,
no explanation, nothing else."""


def _flatten(script: GeneratedScript) -> list[dict]:
    lines = [{"id": "hook", "role": "hook", **script.hook.model_dump()}]
    lines += [{"id": f"body_{i}", "role": "body", **line.model_dump()} for i, line in enumerate(script.body)]
    lines.append({"id": "cta", "role": "cta", **script.cta.model_dump()})
    return lines


def _context_block(payload: ScriptCommandInput) -> str:
    p = payload.structured_product
    return (
        f"Product / brand: {p.product_name}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Key benefits: {', '.join(p.key_benefits) or 'unknown'}\n"
        f"Target audience: {p.target_audience}\n"
        f"Creative angle: {payload.creative_angle or 'none specified'}\n"
        f"Script language: {payload.script.script_language.value}\n"
    )


def _line_by_id(script: GeneratedScript, line_id: str):
    for line in _flatten(script):
        if line["id"] == line_id:
            return line
    return None


def _run_selection_command(payload: ScriptCommandInput) -> ScriptCommandResult:
    selection = payload.selection
    assert selection is not None
    line = _line_by_id(payload.script, selection.line_id)
    if not line or selection.selected_text not in line["text"]:
        raise ValueError("That selection no longer matches the current script — try selecting it again.")

    instruction = payload.instruction.strip() or "Improve this — sharper, clearer, more natural."
    user_message = (
        f"{_context_block(payload)}\n"
        f"Full line (for context only — do not return this, only the replacement span):\n{line['text']}\n\n"
        f"Selected span to rewrite:\n{selection.selected_text}\n\n"
        f"Instruction: {instruction}"
    )
    replacement = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_SELECTION_SYSTEM_PROMPT,
            contents=[user_message],
            model=settings.openrouter_text_model,
            max_output_tokens=1536,
        ),
        label="script_command_selection",
    ).strip().strip('"')

    suggested_text = line["text"].replace(selection.selected_text, replacement, 1)
    return ScriptCommandResult(
        is_full_rewrite=False,
        title="Improve Selection",
        why=f'Rewrote the selected text per: "{instruction}"',
        line_id=selection.line_id,
        current_text=line["text"],
        suggested_text=suggested_text,
    )


def _classify(payload: ScriptCommandInput) -> dict:
    lines = _flatten(payload.script)
    lines_block = "\n".join(f"- id={l['id']}: {l['text']}" for l in lines)
    user_message = f"{_context_block(payload)}\nScript lines:\n{lines_block}\n\nUser instruction: {payload.instruction}"

    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_COMMAND_SYSTEM_PROMPT,
            contents=[user_message],
            model=settings.openrouter_text_model,
            max_output_tokens=2048,
            json_mode=True,
        ),
        label="script_command_classify",
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("The AI returned malformed JSON while interpreting that instruction.") from e


def run_script_command(payload: ScriptCommandInput) -> ScriptCommandResult:
    """Interprets a free-form "Tell AI what you want to change" instruction
    (or an explicit "Improve selection") and returns a previewable patch —
    never writes to the script directly. A targeted edit resolves to exactly
    one line's before/after; a genuine full-rewrite request delegates to the
    existing regenerate_script_section full-scope machinery."""

    if payload.selection:
        return _run_selection_command(payload)

    classification = _classify(payload)

    if classification.get("is_full_rewrite"):
        situation = payload.script.situation
        if situation is None:
            raise ValueError("This script has no linked story situation, so a full rewrite isn't available here.")
        after = regenerate_script_section(
            ScriptSectionRegenerateInput(
                structured_product=payload.structured_product,
                selected_situation=situation,
                product_category=payload.product_category or situation.category or "general",
                creative_angle=payload.creative_angle or payload.script.creative_angle,
                script_language=payload.script.script_language,
                target_duration=payload.script.target_duration,
                current_script=payload.script,
                scope=ScriptRegenerateScope.full,
                custom_instruction=payload.instruction,
            )
        )
        return ScriptCommandResult(
            is_full_rewrite=True,
            title=classification.get("title") or "Full Rewrite",
            why=classification.get("why") or "This instruction needed changes across the whole script.",
            full_script_after=after,
        )

    line_id = classification.get("line_id")
    suggested_text = classification.get("suggested_text")
    line = _line_by_id(payload.script, line_id) if line_id else None
    if not line or not suggested_text:
        raise ValueError("Couldn't find a specific line to apply that instruction to — try being more specific.")

    return ScriptCommandResult(
        is_full_rewrite=False,
        title=classification.get("title") or "Line Improvement",
        why=classification.get("why") or "",
        line_id=line_id,
        current_text=line["text"],
        suggested_text=suggested_text,
    )
