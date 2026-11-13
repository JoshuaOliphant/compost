# ABOUTME: Live evals for the skill-drift mod's Jev questions on labeled real skill-turns in compost-evals (COMPOST_EVALS).
# ABOUTME: Asks each question as hooks/skill-drift.ts does, prints a threshold sweep, and asserts the floors measured.
import asyncio
import json

import pytest
from conftest import TENTHS, evals_dir, rates, skill_drift_judgments, skill_drift_step_questions, sweep
from jevtools import core
from typesafe_sdk import Noul

pytestmark = pytest.mark.jev


def scored_by_question() -> dict[str, list[tuple[float, bool]]]:
    judgments = skill_drift_judgments()
    turn_questions = {name: Noul(instructions=text) for name, text in judgments["turn"].items()}
    next_questions = {name: Noul(instructions=text) for name, text in judgments["next_message"].items()}
    path = evals_dir() / "skill-drift.json"
    if not path.exists():
        pytest.skip("compost-evals has no skill-drift.json (the 60 whole-skill cases of 6 Oct 2026)")
    cases = json.loads(path.read_text())

    async def judge(jev: core.Jev, case: dict) -> dict:
        state = case["state"]
        turn = {"skill": state["skill"], "turn": state["turn"]}
        on_turn, on_next = await asyncio.gather(
            jev.ask("skill-drift", turn, turn_questions),
            jev.ask("skill-drift", {**turn, "next_user_message": state["next_user_message"]}, next_questions),
        )
        return {name: on_turn.noul(name) for name in turn_questions} | {
            name: on_next.noul(name) for name in next_questions
        }

    async def run() -> list[dict]:
        async with core.open_client() as client:
            jev = core.Jev(client, core.Cache())
            results = await asyncio.gather(*(judge(jev, case) for case in cases))
        print(f"\n{jev.input_tokens} input tokens over {len(cases)} cases")
        return results

    results = asyncio.run(run())
    return {
        name: [(result[name], case["expected"][name]) for case, result in zip(cases, results, strict=True)]
        for name in judgments["thresholds"]
    }


def test_each_question_flags_its_labeled_drift_at_the_mods_threshold():
    thresholds = skill_drift_judgments()["thresholds"]
    scored = scored_by_question()
    measured = {}
    for name, rows in scored.items():
        print(f"\n{name}: {sum(label for _, label in rows)} positives of {len(rows)}")
        sweep(rows, TENTHS)
        measured[name] = rates(rows, thresholds[name])
    for name, (accuracy, precision, recall) in measured.items():
        print(f"{name} at {thresholds[name]}: accuracy {accuracy:.2f} precision {precision:.2f} recall {recall:.2f}")
    deviated_precision, deviated_recall = measured["deviated"][1:]
    assert deviated_precision >= 0.75 and deviated_recall >= 0.9
    assert measured["missing_guidance"][2] == measured["corrected"][2] == 1.0


def test_a_stepped_skill_deviates_only_when_a_step_was_really_skipped():
    """23 hand-labeled compost:build turns (8 that did every step, 15 that skipped one or more), 13 Nov 2026.

    The whole-skill `deviated` question scored all 23 between 0.75 and 0.95, clean or not; the likeliest skipped
    step, as the hook now scores it, put every clean turn under 0.75 and 11 of the 15 drifting ones over it.
    """
    threshold = skill_drift_judgments()["thresholds"]["deviated"]
    root = evals_dir()
    cases = json.loads((root / "skill-drift-steps.json").read_text())

    async def judge(jev: core.Jev, case: dict) -> float:
        text = (root / case["skill"]["file"]).read_text()
        body = text.split("---", 2)[2].lstrip("\n") if text.startswith("---") else text
        skill = f"Base directory for this skill: /plugin/skills/build\n\n{body}"
        questions = {name: Noul(instructions=q) for name, q in skill_drift_step_questions(skill).items()}
        answer = await jev.ask(
            "skill-drift", {"skill": {"name": case["skill"]["name"], "text": skill}, "turn": case["turn"]}, questions
        )
        return max(answer.noul(name) for name in questions if name.startswith("step "))

    async def run() -> list[float]:
        async with core.open_client() as client:
            jev = core.Jev(client, core.Cache())
            return await asyncio.gather(*(judge(jev, case) for case in cases))

    rows = [(p, case["expected"]["deviated"]) for p, case in zip(asyncio.run(run()), cases, strict=True)]
    sweep(rows, TENTHS)
    accuracy, precision, recall = rates(rows, threshold)
    print(f"deviated by step at {threshold}: accuracy {accuracy:.2f} precision {precision:.2f} recall {recall:.2f}")
    assert precision == 1.0 and recall >= 0.7
