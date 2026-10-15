"""Tests for curation: generation filtering and the frontier gate.

Both rules exist because a leaderboard over every model ever released is
dominated by tiny, cheap, superseded entries. These tests pin the behaviour
that keeps the value board meaningful.
"""

import unittest

from scipick.config import Preset
from scipick.collect import family_of
from scipick.curate import (
    base_name,
    filter_vendors,
    frontier_threshold,
    gate,
    is_mainstream,
    latest_only,
    passes_frontier,
    product_line,
    version_of,
)


def model(name, score, **kw):
    return {
        "name": name,
        "science_fit_score": score,
        "scores": kw.pop("scores", {"v": score}),
        "coverage": kw.pop("coverage", {"v": 1.0}),
        "efficiency": kw.pop("efficiency", {"v": None if score is None else score / 10}),
        "release_date": kw.pop("release_date", None),
        **kw,
    }


class NameParseTest(unittest.TestCase):
    def test_base_name_drops_tier_qualifiers(self):
        self.assertEqual(
            base_name("Claude Opus 5.5 (Max, Default Fallback)"), "Claude Opus 5.5"
        )

    def test_version_of_extracts_dotted_numbers(self):
        self.assertEqual(version_of("Claude Opus 5.5 (Max)"), (5.5,))

    def test_version_ordering(self):
        self.assertGreater(version_of("Claude Opus 5.5"), version_of("Claude Opus 4.8"))

    def test_version_of_name_without_numbers(self):
        self.assertEqual(version_of("Grok"), (0.0,))

    def test_product_line_collapses_versions(self):
        self.assertEqual(product_line("Claude Opus 5.5 (Max)"), "claude opus")
        self.assertEqual(product_line("Claude Opus 4.5 (Reasoning)"), "claude opus")

    def test_product_line_strips_release_date_stamp(self):
        self.assertEqual(product_line("DeepSeek V4 Pro 0813 (Max)"), "deepseek v4 pro")

    def test_distinct_lines_stay_distinct(self):
        self.assertNotEqual(product_line("Claude Opus 5.5"), product_line("Claude Sonnet 5.5"))


class LatestOnlyTest(unittest.TestCase):
    def test_keeps_newest_generation(self):
        models = [
            model("Claude Opus 4.5 (Reasoning)", 50),
            model("Claude Opus 5.5 (Max)", 65),
            model("Claude Opus 5 (Max)", 60),
        ]
        kept, dropped = latest_only(models)
        self.assertEqual([m["name"] for m in kept], ["Claude Opus 5.5 (Max)"])
        self.assertEqual(dropped, 2)

    def test_keeps_one_row_per_line(self):
        models = [
            model("GPT-5 (High)", 55),
            model("GPT-5.5 (Xhigh)", 58),
            model("Claude Opus 5.5 (Max)", 65),
        ]
        kept, dropped = latest_only(models)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, 1)
        self.assertIn("Claude Opus 5.5 (Max)", [m["name"] for m in kept])

    def test_same_version_prefers_more_recent_date(self):
        models = [
            model("GPT-5 (High)", 55, release_date="2026-01-01"),
            model("GPT-5 (Max)", 55, release_date="2026-06-01"),
        ]
        kept, _ = latest_only(models)
        self.assertEqual(kept[0]["name"], "GPT-5 (Max)")

    def test_distinct_lines_all_survive(self):
        models = [
            model("Claude Opus 5.5 (Max)", 65),
            model("Gemini 4 Argon (High)", 60),
            model("GPT-6 Astra (Max)", 58),
        ]
        kept, dropped = latest_only(models)
        self.assertEqual(len(kept), 3)
        self.assertEqual(dropped, 0)

    def test_empty_input(self):
        self.assertEqual(latest_only([]), ([], 0))


class FrontierGateTest(unittest.TestCase):
    def preset(self, rel=0.65, rank_by="efficiency"):
        return Preset(key="v", label="V", description="", weights={"scicode": 1.0},
                      rank_by=rank_by, min_relative_score=rel)

    def test_threshold_is_fraction_of_best(self):
        models = [model("best", 100), model("weak", 10)]
        self.assertEqual(frontier_threshold(models, self.preset(0.65)), 65.0)

    def test_zero_relative_disables_gate(self):
        models = [model("best", 100), model("weak", 10)]
        self.assertIsNone(frontier_threshold(models, self.preset(0.0)))
        kept, below, thr = gate(models, self.preset(0.0))
        self.assertEqual(len(kept), 2)
        self.assertEqual(below, [])
        self.assertIsNone(thr)

    def test_weak_models_are_gated_out(self):
        models = [model("best", 100), model("mid", 70), model("weak", 20)]
        kept, below, thr = gate(models, self.preset(0.65))
        names = [m["name"] for m in kept]
        self.assertIn("mid", names)
        self.assertNotIn("weak", names)
        self.assertEqual(len(below), 1)
        self.assertEqual(thr, 65.0)

    def test_the_real_regression(self):
        """A cheap 4B model must not top a value board over a frontier model.

        Before the gate, Gemma 4 E4B (score 15.5 at $0.04) outranked
        Claude Haiku 5.5 (score 51.1 at $0.20) on points-per-dollar alone.
        """
        cheap_toy = model("Gemma 4 E4B", 15.5,
                          efficiency={"v": 388.0})
        cheap_useful = model("Claude Haiku 5.5", 51.1,
                             efficiency={"v": 256.0})
        strong = model("Claude Opus 5.5", 65.0, efficiency={"v": 8.0})
        kept, below, _ = gate([strong, cheap_useful, cheap_toy], self.preset(0.65))
        names = [m["name"] for m in kept]
        self.assertIn("Claude Haiku 5.5", names)
        self.assertNotIn("Gemma 4 E4B", names)
        self.assertEqual(len(below), 1)

    def test_models_without_a_score_are_dropped_not_gated(self):
        """No score at all is not "below the frontier" — it is unrankable."""
        m = model("unscored", None, scores={"v": None})
        kept, below, _ = gate([m, model("ok", 100)], self.preset(0.65))
        self.assertEqual([x["name"] for x in kept], ["ok"])
        self.assertEqual(below, [])

    def test_passes_frontier_helper(self):
        p = self.preset(0.5)
        models = [model("best", 100), model("weak", 10)]
        thr = frontier_threshold(models, p)
        self.assertTrue(passes_frontier(models[0], p, thr))
        self.assertFalse(passes_frontier(models[1], p, thr))
        self.assertTrue(passes_frontier(models[1], p, None))


if __name__ == "__main__":
    unittest.main()


class VendorFilterTest(unittest.TestCase):
    """The vendor allowlist keeps the board to companies worth considering.

    Without it the catalogue carries ~60 creators, most contributing a single
    entry, and the "Other" bucket grows larger than any named family.
    """

    def rec(self, creator):
        return {"name": "x", "creator": creator, "scores": {"v": 1.0},
                "coverage": {"v": 1.0}, "efficiency": {"v": 1.0}}

    def test_major_vendors_are_kept(self):
        for c in ("OpenAI", "Anthropic", "Google", "Meta", "Alibaba",
                  "DeepSeek", "Z AI", "Xiaomi", "Moonshot", "Mistral"):
            self.assertTrue(is_mainstream(c), f"{c} should be mainstream")

    def test_obscure_vendor_is_dropped(self):
        self.assertFalse(is_mainstream("Some Tiny Startup"))

    def test_matching_is_case_insensitive(self):
        self.assertTrue(is_mainstream("openai"))
        self.assertTrue(is_mainstream("OPENAI"))

    def test_muse_alias_maps_to_meta(self):
        """Meta ships its flagship as "Muse", with no vendor in the name."""
        self.assertTrue(is_mainstream("Muse"))
        self.assertTrue(is_mainstream("muse"))

    def test_filter_keeps_and_counts(self):
        models = [self.rec("OpenAI"), self.rec("Obscure Labs"), self.rec("Meta")]
        kept, dropped = filter_vendors(models)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, 1)
        self.assertEqual([m["creator"] for m in kept], ["OpenAI", "Meta"])

    def test_missing_creator_is_kept(self):
        """A missing field should not hide a real model."""
        models = [{"name": "x", "creator": "", "scores": {"v": 1.0},
                   "coverage": {"v": 1.0}, "efficiency": {"v": 1.0}}]
        kept, dropped = filter_vendors(models)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, 0)

    def test_empty_allowlist_keeps_everything(self):
        models = [self.rec("OpenAI"), self.rec("Obscure Labs")]
        kept, dropped = filter_vendors(models, allow=())
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, 0)


class FamilyResolutionTest(unittest.TestCase):
    """Family must come from the authoritative creator field where possible."""

    def test_creator_beats_name_heuristic(self):
        """Meta's Muse line has no vendor in its name, so name matching fails."""
        self.assertEqual(family_of("Muse Wonder Full (Max)", "", "Meta"), "Meta")

    def test_kimi_is_mapped_to_its_vendor(self):
        self.assertEqual(family_of("Kimi K3 (Max)", "", "Kimi"), "Moonshot")

    def test_grok_maps_to_xai(self):
        self.assertEqual(family_of("Grok 4.7 (Xhigh)", "", "SpaceXAI"), "xAI")

    def test_falls_back_to_name_when_creator_absent(self):
        self.assertEqual(family_of("Claude Opus 5.5", "claude-opus-5-5", ""), "Claude")

    def test_unknown_creator_becomes_its_own_family(self):
        """Not "Other": a named vendor is more informative than a bucket."""
        self.assertEqual(family_of("Mystery 1", "", "Mystery Corp"), "Mystery Corp")

    def test_no_creator_and_no_match_is_other(self):
        self.assertEqual(family_of("Anonymous Model", "", ""), "Other")
