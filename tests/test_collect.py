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

    def test_reported_counts_reconcile_with_the_board(self):
        """The "Data" line subtracts four counts and must land on the board size.

        It used to name only the superseded and vendor drops, so the stated
        arithmetic came out 225 rows short on the live board: two stages (models
        with no usable benchmark, and entries that collapse to the same
        canonical model) dropped rows without being counted. A page whose
        selling point is that its rules are stated cannot have a visible sum
        that does not add up.
        """
        aa_rows = self.aa + [
            # Same model at another reasoning effort: collapses to one row.
            aa("GPT-5 (Low)", "gpt-5-low", scicode=0.5,
               artificial_analysis_intelligence_index=68.0),
            # Nothing to rank on.
            aa("Also Unrankable", "also-unrankable", pricing={}),
        ]
        board, _, meta = collect(aa_rows, {}, DEFAULT_PRESETS)
        total = (meta["board_size"] + meta["unrankable_removed"]
                 + meta["duplicate_removed"] + meta["superseded_removed"]
                 + meta["vendors_removed"])
        self.assertEqual(total, meta["aa_total"],
                         f"counts do not add up: {meta}")
        self.assertEqual(meta["unrankable_removed"], 2)
        self.assertEqual(meta["duplicate_removed"], 1)
        self.assertEqual(meta["board_size"], len(board))

    def test_counts_stay_consistent_with_the_global_filters_off(self):
        """With both global filters disabled, only the two silent stages drop."""
        aa_rows = self.aa + [
            aa("GPT-5 (Low)", "gpt-5-low", scicode=0.5,
               artificial_analysis_intelligence_index=68.0),
        ]
        board, _, meta = collect(aa_rows, {}, DEFAULT_PRESETS,
                                 latest=False, mainstream_only=False)
        self.assertEqual(meta["superseded_removed"], 0)
        self.assertEqual(meta["vendors_removed"], 0)
        self.assertEqual(meta["board_size"] + meta["unrankable_removed"]
                         + meta["duplicate_removed"], meta["aa_total"])
        self.assertEqual(meta["board_size"], len(board))


if __name__ == "__main__":
    unittest.main()
