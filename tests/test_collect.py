"""Tests for collection: name matching, de-duplication, local annotation."""

import unittest

from scipick.collect import canonical_key, collect, family_of
from scipick.config import DEFAULT_PRESETS
from scipick.fetch import build_aa_index, match_model, norm, strip_variant


def aa(name, slug, **ev):
    pricing = ev.pop("pricing", {})
    return {
        "name": name,
        "slug": slug,
        "evaluations": ev,
        "pricing": pricing,
    }


class NormTest(unittest.TestCase):
    def test_lowercases_and_unifies_separators(self):
        self.assertEqual(norm("GPT_5.Turbo"), "gpt-5-turbo")

    def test_strips_parenthetical(self):
        self.assertEqual(norm("GPT-5 (High)"), "gpt-5")

    def test_strip_variant_removes_effort_suffix(self):
        self.assertEqual(strip_variant("gpt-5-high"), "gpt-5")
        self.assertEqual(strip_variant("claude-opus-4-5-thinking"), "claude-opus-4-5")

    def test_strip_variant_keeps_real_name(self):
        self.assertEqual(strip_variant("claude-opus-4-5"), "claude-opus-4-5")


class MatchTest(unittest.TestCase):
    def setUp(self):
        self.idx = build_aa_index([
            aa("GPT-5 (High)", "gpt-5-high", scicode=0.5),
            aa("GPT-5 (Low)", "gpt-5-low", scicode=0.4),
            aa("Claude Opus 4.5", "claude-opus-4-5", scicode=0.53),
        ])

    def test_exact_slug_match(self):
        m = match_model("claude-opus-4-5", self.idx)
        self.assertIsNotNone(m)
        self.assertEqual(m["name"], "Claude Opus 4.5")

    def test_effort_suffix_still_matches(self):
        m = match_model("gpt-5-high", self.idx)
        self.assertIsNotNone(m)

    def test_unknown_returns_none(self):
        self.assertIsNone(match_model("totally-made-up-model", self.idx))


class FamilyTest(unittest.TestCase):
    def test_known_families(self):
        self.assertEqual(family_of("Claude Opus 4.5"), "Claude")
        self.assertEqual(family_of("GPT-5"), "GPT")
        self.assertEqual(family_of("Gemini 2.5 Pro"), "Gemini")

    def test_unknown_is_other(self):
        self.assertEqual(family_of("SomeRandomModel"), "Other")


class CanonicalKeyTest(unittest.TestCase):
    def test_collapses_variants(self):
        self.assertEqual(canonical_key("GPT-5 (High)"), canonical_key("gpt-5-high"))

    def test_distinct_models_stay_distinct(self):
        self.assertNotEqual(canonical_key("GPT-5"), canonical_key("GPT-6"))


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.aa = [
            aa("GPT-5 (High)", "gpt-5-high", scicode=0.5, hle=0.3,
               artificial_analysis_intelligence_index=68.0,
               pricing={"price_1m_blended_3_to_1": 3.44}),
            aa("Claude Opus 4.5", "claude-opus-4-5", scicode=0.53,
               artificial_analysis_intelligence_index=71.0,
               pricing={"price_1m_blended_3_to_1": 10.0}),
            aa("Unrankable", "unrankable", pricing={}),
        ]

    def test_unrankable_models_are_dropped(self):
        board, _, _ = collect(self.aa, {}, DEFAULT_PRESETS)
        names = [m["name"] for m in board]
        self.assertNotIn("Unrankable", names)
        self.assertEqual(len(board), 2)

    def test_board_is_sorted_by_capability(self):
        board, _, _ = collect(self.aa, {}, DEFAULT_PRESETS)
        scores = [m["scores"]["capability"] for m in board]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_local_availability_annotates_without_duplicating(self):
        board, _, meta = collect(self.aa, {"gw": ["gpt-5-high"]}, DEFAULT_PRESETS)
        gpt = [m for m in board if m["family"] == "GPT"][0]
        self.assertTrue(gpt["available_locally"])
        self.assertEqual(gpt["sources"], ["gw"])
        claude = [m for m in board if m["family"] == "Claude"][0]
        self.assertFalse(claude["available_locally"])
        self.assertEqual(meta["local_sources"], ["gw"])

    def test_no_local_gateway_is_supported(self):
        """The leaderboard must be fully useful without any local endpoint."""
        board, unmatched, meta = collect(self.aa, {}, DEFAULT_PRESETS)
        self.assertEqual(len(board), 2)
        self.assertEqual(unmatched, [])
        self.assertEqual(meta["local_sources"], [])

    def test_unmatched_routes_are_reported_not_dropped_silently(self):
        _, unmatched, meta = collect(self.aa, {"gw": ["mystery-9000"]}, DEFAULT_PRESETS)
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["route"], "gw/mystery-9000")
        self.assertEqual(meta["unmatched_count"], 1)

    def test_all_presets_are_computed(self):
        board, _, _ = collect(self.aa, {}, DEFAULT_PRESETS)
        for m in board:
            for key in DEFAULT_PRESETS:
                self.assertIn(key, m["scores"])
                self.assertIn(key, m["efficiency"])


if __name__ == "__main__":
    unittest.main()
