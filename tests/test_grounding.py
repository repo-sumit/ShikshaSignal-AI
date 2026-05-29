"""Number-grounding tests — the load-bearing trust eval (Milestone 3).

Premise: the LLM never invents numbers. Every numeric token in the rendered memo
must trace to a value present in `review_facts.json`. These tests verify both
directions:

  * Real run grounds cleanly (zero ungrounded tokens).
  * A deliberately injected fake number is caught by the same check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import FOCUS_DISTRICT
from app.eval.grounding import check_grounding, grounded_numbers, memo_numbers
from app.review import run_review


@pytest.fixture(scope="module")
def review_outputs(tmp_path_factory, gen_dir):
    out = tmp_path_factory.mktemp("grounding")
    return run_review(
        district=FOCUS_DISTRICT,
        period="2026-05",
        top_n_schools=10,
        top_n_blocks=5,
        top_n_actions=10,
        llm_provider="mock",
        outputs_dir=out,
        synthetic_dir=gen_dir,
        timestamp="2026-05-29T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Happy path: every memo number is grounded in review_facts.json
# ---------------------------------------------------------------------------


def test_real_run_is_fully_grounded(review_outputs):
    memo = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(review_outputs.review_facts_json).read_text(encoding="utf-8"))
    ungrounded = check_grounding(memo, facts)
    assert ungrounded == [], (
        f"Memo contains {len(ungrounded)} ungrounded numeric token(s): {ungrounded[:10]}"
    )


def test_memo_actually_contains_numbers(review_outputs):
    """Sanity check: a memo with zero numbers would pass grounding vacuously."""
    memo = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    nums = memo_numbers(memo)
    # The memo should have dozens of numeric tokens (KPIs, scores, rankings, ...).
    assert len(nums) >= 30, f"Memo unexpectedly low on numbers ({len(nums)})"


def test_facts_provide_grounding_coverage(review_outputs):
    facts = json.loads(Path(review_outputs.review_facts_json).read_text(encoding="utf-8"))
    grounded = grounded_numbers(facts)
    # Facts should expose many numeric tokens (one per KPI row, per school, etc.).
    assert len(grounded) >= 50


# ---------------------------------------------------------------------------
# Adversarial: injecting a fake number must be caught
# ---------------------------------------------------------------------------


def test_injected_hallucinated_number_is_caught(review_outputs):
    """If the LLM ever writes a number not in facts, the eval must flag it."""
    memo = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(review_outputs.review_facts_json).read_text(encoding="utf-8"))

    # The number 987654 will not exist anywhere in our facts or allowlist.
    poisoned = memo + "\n\nFabricated stat: students reached 987654."
    ungrounded = check_grounding(poisoned, facts)
    assert "987654" in ungrounded, (
        "Grounding check failed to detect a clearly fabricated number."
    )


def test_injected_fraction_is_caught_too(review_outputs):
    memo = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(review_outputs.review_facts_json).read_text(encoding="utf-8"))
    poisoned = memo + "\n\nFLN went up by 42.42% this period."
    ungrounded = check_grounding(poisoned, facts)
    assert "42.42" in ungrounded


def test_runtime_injection_via_monkeypatched_provider(tmp_path, gen_dir, monkeypatch):
    """Inject a fake number through the LLM provider and re-run the compiler.

    This is the realistic failure mode: a future real LLM hallucinates a number into
    one of its sections. The grounding eval must catch it from the rendered memo.
    """
    from app.llm.mock_llm import MockLLM

    real_generate = MockLLM.generate_section

    def poisoned_generate(self, section_name, facts):
        text = real_generate(self, section_name, facts)
        if section_name == "executive_summary":
            return text + " Independent estimate: 7777 students at risk."
        return text

    monkeypatch.setattr(MockLLM, "generate_section", poisoned_generate)

    arts = run_review(
        district=FOCUS_DISTRICT,
        period="2026-05",
        outputs_dir=tmp_path,
        synthetic_dir=gen_dir,
        timestamp="2026-05-29T00:00:00+00:00",
    )
    memo = arts.monthly_district_review_md.read_text(encoding="utf-8")
    facts = json.loads(arts.review_facts_json.read_text(encoding="utf-8"))
    ungrounded = check_grounding(memo, facts)
    assert "7777" in ungrounded
