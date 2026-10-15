"""Tests for scoring: renormalisation, coverage, and the no-price rule.

These encode the decisions that are easy to regress:
  * a missing metric is skipped and weights renormalise (not scored as 0)
  * coverage reports how much weight actually landed
  * an unpublished price (AA sends 0) yields no value score, never "free"
"""

import unittest

from scipick.config import Preset
from scipick.score import blended_price, efficiency, rank, science_score


def preset(**weights):
    return Preset(key="t", label="T", description="", weights=weights)


class ScienceScoreTest(unittest.TestCase):
    def test_all_metrics_present(self):
        p = preset(scicode=0.5, hle=0.5)
        s = science_score({"scicode": 0.60, "hle": 0.40}, p)
        # (60*0.5 + 40*0.5) / 1.0 = 50
        self.assertEqual(s.value, 50.0)
        self.assertEqual(s.coverage, 1.0)

    def test_missing_metric_is_skipped_not_zeroed(self):
        """A model not evaluated for HLE must not be penalised as if it scored 0."""
        p = preset(scicode=0.5, hle=0.5)
        s = science_score({"scicode": 0.60}, p)
        # Only scicode counts, renormalised to itself.
        self.assertEqual(s.value, 60.0)
        self.assertEqual(s.coverage, 0.5)

    def test_coverage_reflects_partial_data(self):
        p = preset(scicode=0.4, hle=0.3, lcr=0.3)
        s = science_score({"scicode": 0.5}, p)
        self.assertAlmostEqual(s.coverage, 0.4)

    def test_no_data_returns_none(self):
        p = preset(scicode=1.0)
        s = science_score({}, p)
        self.assertIsNone(s.value)
        self.assertEqual(s.coverage, 0.0)

    def test_index_metric_is_not_rescaled(self):
        """AA intelligence index is already 0-100; fractions are 0-1."""
        p = preset(artificial_analysis_intelligence_index=1.0)
        s = science_score({"artificial_analysis_intelligence_index": 71.0}, p)
        self.assertEqual(s.value, 71.0)

    def test_fraction_metric_is_rescaled(self):
        p = preset(scicode=1.0)
        s = science_score({"scicode": 0.53}, p)
        self.assertEqual(s.value, 53.0)

    def test_explicit_zero_is_a_real_value(self):
        """0.0 is data, not absence — coverage must count it."""
        p = preset(scicode=1.0)
        s = science_score({"scicode": 0.0}, p)
        self.assertEqual(s.value, 0.0)
        self.assertEqual(s.coverage, 1.0)


class BlendedPriceTest(unittest.TestCase):
    def test_reads_aa_field_name(self):
        self.assertEqual(blended_price({"price_1m_blended_3_to_1": 3.44}), 3.44)

    def test_zero_means_unpublished_not_free(self):
        self.assertIsNone(blended_price({"price_1m_blended_3_to_1": 0}))

    def test_missing_and_empty(self):
        self.assertIsNone(blended_price({}))
        self.assertIsNone(blended_price(None))


class EfficiencyTest(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(efficiency(56.1, 10.0), 5.61)

    def test_no_price_gives_none(self):
        self.assertIsNone(efficiency(56.1, None))

    def test_no_score_gives_none(self):
        self.assertIsNone(efficiency(None, 10.0))


class RankTest(unittest.TestCase):
    """Models here use the record shape produced by :func:`scipick.collect.collect`."""

    @staticmethod
    def model(name, score=None, eff=None, key="t"):
        return {
            "name": name,
            "science_fit_score": score,
            "scores": {key: score},
            "efficiency": {key: eff},
        }

    def test_score_ranking_is_descending(self):
        p = Preset(key="t", label="T", description="", weights={"scicode": 1.0})
        models = [self.model("a", 10.0), self.model("b", 30.0)]
        self.assertEqual([m["name"] for m in rank(models, p)], ["b", "a"])

    def test_efficiency_ranking_uses_value(self):
        p = Preset(key="v", label="V", description="", weights={"scicode": 1.0},
                   rank_by="efficiency")
        models = [
            self.model("expensive", 90.0, 2.0, key="v"),
            self.model("cheap", 60.0, 20.0, key="v"),
        ]
        self.assertEqual([m["name"] for m in rank(models, p)], ["cheap", "expensive"])

    def test_efficiency_ranking_excludes_models_without_price(self):
        """No published price means no value score, so it cannot be ranked on value."""
        p = Preset(key="v", label="V", description="", weights={"scicode": 1.0},
                   rank_by="efficiency")
        models = [
            self.model("priced", 60.0, 20.0, key="v"),
            self.model("unpriced", 90.0, None, key="v"),
        ]
        self.assertEqual([m["name"] for m in rank(models, p)], ["priced"])

    def test_unscored_models_are_excluded(self):
        p = Preset(key="t", label="T", description="", weights={"scicode": 1.0})
        models = [self.model("scored", 10.0), self.model("unscored", None)]
        self.assertEqual([m["name"] for m in rank(models, p)], ["scored"])


if __name__ == "__main__":
    unittest.main()


class MinCoverageTest(unittest.TestCase):
    """The coverage floor: renormalisation alone produces misleading rankings.

    Real case that motivated this: SciCode and Terminal-Bench cover only ~30% of
    the catalogue, so without a floor a "coding" preset ranked models by
    long-context reasoning alone (coverage 0.15) and put them at the top.
    """

    def test_default_floor_is_sane(self):
        p = preset(scicode=1.0)
        self.assertGreater(p.min_coverage, 0.0)
        self.assertLessEqual(p.min_coverage, 1.0)

    def test_floor_is_configurable(self):
        p = Preset(key="t", label="T", description="", weights={"scicode": 1.0},
                   min_coverage=0.9)
        self.assertEqual(p.min_coverage, 0.9)

    def test_single_metric_coverage_is_visible_to_the_floor(self):
        """A model with 1 of 5 weighted metrics has coverage 0.2 -> below floor."""
        p = preset(scicode=0.6, terminalbench_v4_0=0.25, lcr=0.15)
        s = science_score({"lcr": 0.83}, p)
        self.assertAlmostEqual(s.coverage, 0.15)
        self.assertLess(s.coverage, p.min_coverage)
