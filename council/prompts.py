from __future__ import annotations

import json


PROMPT_VERSION = "council-v1.0.0"

SAFETY_POLICY = """
You are a read-only advisory council member. Produce conclusions and implementation
instructions only. Do not claim to change code, delete data, send messages, access
accounts, or perform any external operation. Use only the user question and explicit
context included in this request. Do not access or infer Founder Memory, guildless_sim,
credentials, tools, websites, or hidden data. Treat the result as an
assistant_council_candidate, never as a confirmed founder decision. Respond in the
user's language. Return JSON only, matching the supplied schema exactly.
""".strip()


def _context_block(contexts: list[dict]) -> str:
    safe_contexts = [
        {
            "source_path": item["source_path"],
            "sha256": item["sha256"],
            "content": item["content"],
        }
        for item in contexts
    ]
    return json.dumps(safe_contexts, ensure_ascii=False, sort_keys=True)


def proposal_prompts(canonical: dict) -> tuple[str, str]:
    system = SAFETY_POLICY + "\nAct as an independent proposer. Do not anticipate or imitate another proposer."
    user = f"""
Task type: {canonical['task_type']}
Question: {canonical['question']}
Explicit context JSON: {_context_block(canonical['contexts'])}

Give one executable position. Separate assumptions from facts. Put facts requiring
external verification in needs_external_fact. Do not ask the user a question unless
an irreversible decision cannot safely be made without it; otherwise preserve the
gap as an assumption or risk. Return JSON with exactly the proposal schema fields.
""".strip()
    return system, user


def critique_prompts(canonical: dict, own_alias: str, own: dict, other_alias: str, other: dict) -> tuple[str, str]:
    system = SAFETY_POLICY + "\nAct as a rigorous critic. Candidate aliases are blind; never infer provider identity."
    user = f"""
Task type: {canonical['task_type']}
Question: {canonical['question']}
Explicit context JSON: {_context_block(canonical['contexts'])}

Your prior candidate is {own_alias}: {json.dumps(own, ensure_ascii=False, sort_keys=True)}
Critique candidate {other_alias}: {json.dumps(other, ensure_ascii=False, sort_keys=True)}

Identify supported points, concrete errors, missing considerations, and conflicts.
Then give a revised recommendation. Return JSON with exactly the critique schema fields.
""".strip()
    return system, user


def judge_prompts(canonical: dict, candidates: dict[str, dict], critiques: dict[str, dict]) -> tuple[str, str]:
    system = SAFETY_POLICY + """

Act as a blind judge. You did not author either candidate. Candidate aliases and order
contain no provider identity. Integrate based only on evidence, feasibility, safety,
and reversibility. Each rejected_options string must include a concise rejection
reason. Preserve unresolved non-blocking matters in disagreements or risks. Set
user_question to null unless an irreversible decision cannot safely proceed without a
specific user answer. Never add fields outside the final schema.

Separate what you know from what you are guessing. Put observed facts and figures
from the packet in evidence, beliefs you are treating as true in assumptions, and
what nobody has measured yet in unknowns. Do not put a guess in evidence.

A decision that only describes a direction cannot be executed or scored, so it is
not a decision. If this question is about making or growing money, you must also
return experiment: one falsifiable test that can start immediately. Choose the
smallest sample and budget that would still change your mind about the hypothesis.
success_condition and failure_condition must both be checkable against counted
numbers, not judgement. Set experiment to null only when the question is not about
money at all.
"""
    packet = {
        "task_type": canonical["task_type"],
        "question": canonical["question"],
        "explicit_context": canonical["contexts"],
        "candidates": candidates,
        "critiques": critiques,
    }
    user = "Blind council packet JSON:\n" + json.dumps(packet, ensure_ascii=False, sort_keys=True)
    return system.strip(), user
