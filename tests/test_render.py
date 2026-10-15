"""Tests for the rendered page: per-view podiums, the frontier scatter, and
the full-ranking controls.

These are structural assertions on the generated HTML. They exist because the
defects they cover were all *invisible* to the scoring tests: a podium that
never changed between views, a chart whose labels overprinted, a table whose
rows were silently missing. None of that breaks a score, so none of it could be
caught by testing the maths.
"""

import re
import unittest

from scipick.config import DEFAULT_PRESETS
from scipick.i18n import LANGS, STRINGS
from scipick.render import _frontier, _short_name, render


def model(name, capability=50.0, coding=50.0, longcontext=50.0, price=5.0,
          scicode=0.5, lcr=0.5, hle=0.5, aaii=50.0, terminal=0.5):
    """Build one collected model in the shape ``collect()`` produces.

    Scores and efficiencies are derived from the metrics the way the pipeline
    derives them, so the fixture cannot drift from the real contract as the
    presets change.
    """
    from scipick.score import efficiency as eff_of, science_score

    metrics = {
        "scicode": scicode,
        "hle": hle,
        "artificial_analysis_intelligence_index": aaii,
        "lcr": lcr,
        "terminalbench_v4_0": terminal,
    }
    scores, coverage, effs = {}, {}, {}
    for key, preset in DEFAULT_PRESETS.items():
        s = science_score(metrics, preset)
        scores[key] = s.value
        coverage[key] = s.coverage
        if price:
            effs[key] = eff_of(s.value, price)
    return {
        "name": name,
        "family": name.split()[0],
        "creator": name.split()[0],
        "metrics": metrics,
        "scores": scores,
        "coverage": coverage,
        "efficiency": effs,
        "pricing": {"blended": price, "input": price, "output": price},
        "available_locally": False,
        "sources": [],
        "variants": [],
    }


def board():
    """A small board with distinct winners per view.

    Chosen so the capability and value leaders differ, and so the Pareto
    frontier has more than one step — otherwise the assertions below could pass
    on a degenerate board.
    """
    return [
        model("Strong Expensive", capability=90.0, coding=88.0,
              longcontext=95.0, price=60.0, scicode=0.9, lcr=0.95,
              hle=0.8, aaii=90.0, terminal=0.8),
        model("Weak Cheap", capability=40.0, coding=35.0,
              longcontext=30.0, price=0.05, scicode=0.3, lcr=0.3,
              hle=0.2, aaii=35.0, terminal=0.3),
        model("Mid Balanced", capability=65.0, coding=70.0,
              longcontext=60.0, price=4.0, scicode=0.7, lcr=0.6,
              hle=0.5, aaii=65.0, terminal=0.6),
    ]


def panels(html):
    """Split the page into {preset_key: panel_html}.

    Matches attributes in any order, so adding ARIA wiring to the panel tag
    does not silently empty this helper.
    """
    out = {}
    for m in re.finditer(
        r'<section\b[^>]*\bclass="panel[^"]*"[^>]*\bdata-key="([^"]+)"[^>]*>'
        r"(.*?)</section>",
        html, re.S,
    ):
        out[m.group(1)] = m.group(2)
    return out


def podium_names(panel_html):
    block = panel_html[: panel_html.find('<div class="cards"')]
    return [
        re.sub(r"<[^>]+>", "", n).strip()
        for n in re.findall(r'<div class="pname">(.*?)</div>', block, re.S)
    ]


class PodiumPerViewTest(unittest.TestCase):
    """The podium must describe the view it sits in.

    The original bug: the podium was rendered once above the tab strip, so every
    view showed the same six names — and for views whose tables differ, the
    podium contradicted the table directly beneath it.
    """

    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=60)
        self.panels = panels(self.html)

    def test_one_podium_per_panel(self):
        self.assertEqual(len(self.panels), len(DEFAULT_PRESETS))
        for key, body in self.panels.items():
            with self.subTest(view=key):
                self.assertEqual(body.count('class="podium"'), 1)

    def test_no_podium_outside_the_panels(self):
        # Strip the panels; a podium outside them is the original defect.
        outside = self.html
        for body in self.panels.values():
            outside = outside.replace(body, "")
        self.assertNotIn('class="podium"', outside)

    def test_value_view_leads_with_its_own_winner(self):
        val = podium_names(self.panels["value"])
        # "Weak Cheap" has the best points-per-dollar, but the value floor
        # should admit it only if it is within reach of the frontier.
        self.assertTrue(val)
        cap = podium_names(self.panels["capability"])
        self.assertEqual(cap[0], "Strong Expensive")
        # The two views must not be identical, or the podium is still static.
        self.assertNotEqual(val, cap)

    def test_podium_heading_matches_ranking_criterion(self):
        self.assertIn('data-i18n="podium.by.value"', self.panels["value"])
        self.assertIn('data-i18n="podium.by.score"', self.panels["capability"])

    def test_secondary_leader_names_the_other_axis(self):
        # Capability leads on score, so it names the best value, and vice versa.
        self.assertIn('data-i18n="podium.leader.value"',
                      self.panels["capability"])
        self.assertIn('data-i18n="podium.leader.score"', self.panels["value"])

    def test_podium_agrees_with_its_own_table(self):
        """The first podium row must be the table's first row.

        This is the assertion that would have caught the original bug: the
        hoisted podium named the capability leaders even in the coding view.
        """
        from scipick.render import _ranked_for
        for key, preset in DEFAULT_PRESETS.items():
            want = _ranked_for(board(), preset)[0]["name"]
            got = podium_names(self.panels[key])[0]
            with self.subTest(view=key):
                self.assertEqual(got, want)


class FrontierChartTest(unittest.TestCase):
    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=60)
        self.panels = panels(self.html)

    def test_scatter_rendered_once_per_view(self):
        for key, body in self.panels.items():
            with self.subTest(view=key):
                self.assertIn("<svg", body)
                self.assertIn('class="fline"', body)

    def test_frontier_is_not_empty(self):
        svg = _frontier(board(), DEFAULT_PRESETS["capability"])
        self.assertIn('class="fline"', svg)
        self.assertIn('class="fdot', svg)

    def test_draw_animation_length_is_a_number(self):
        # The draw-in needs a real stroke length; a missing value would make
        # the line render permanently invisible.
        m = re.search(r'class="fline" style="--len:([0-9.]+)"', self.html)
        self.assertIsNotNone(m)
        self.assertGreater(float(m.group(1)), 0)

    def test_labels_do_not_overprint(self):
        """No two labels may occupy the same row in an overlapping column band.

        The frontier is a staircase, so several models routinely share almost
        the same x. Estimating each label's box from its glyph count is enough
        to catch a return of the stacked-label smear seen in review.
        """
        svg = _frontier(board(), DEFAULT_PRESETS["capability"])
        labels = []
        for m in re.finditer(
            r'<text x="([0-9.]+)" y="([0-9.]+)" class="fl" '
            r'text-anchor="(\w+)">([^<]*)</text>',
            svg,
        ):
            x, y, anchor, text = float(m.group(1)), float(m.group(2)), \
                m.group(3), m.group(4)
            w = len(text) * 6.4
            x0, x1 = (x - w, x) if anchor == "end" else (x, x + w)
            labels.append((x0, x1, y, text))
        for i, (ax0, ax1, ay, at) in enumerate(labels):
            for (bx0, bx1, by, bt) in labels[i + 1:]:
                overlap_x = ax0 < bx1 and bx0 < ax1
                overlap_y = abs(ay - by) < 12.5 * 0.8
                if overlap_x and overlap_y:
                    self.fail(f"labels overlap: {at!r} and {bt!r}")

    def test_only_frontier_and_top_are_labelled(self):
        # Needs a board larger than the top-3 set, otherwise every point is a
        # "top" point and the assertion is vacuous.
        big = board() + [
            model(f"Filler {i}", capability=20.0 + i, coding=20.0,
                  longcontext=20.0, price=0.5 + i, scicode=0.2, lcr=0.2,
                  hle=0.1, aaii=20.0, terminal=0.2)
            for i in range(12)
        ]
        svg = _frontier(big, DEFAULT_PRESETS["capability"])
        n_dots = len(re.findall(r'class="fdot', svg))
        n_labels = len(re.findall(r'class="fl"', svg))
        self.assertGreater(n_dots, 3)
        self.assertLess(n_labels, n_dots)

    def test_top_three_ring_outranks_the_vendor_ring(self):
        """The gold ring must not be overridden by the vendor-colour ring.

        The vendor rule carries an attribute selector and a :not(), so a plain
        `.fdot.top` loses to it and the top-three marker silently reverts to the
        neutral ring. Caught by reading getComputedStyle in a real browser.
        """
        html = render(board(), DEFAULT_PRESETS)
        # The qualified selector has to be present, not just the bare one.
        self.assertIn('.fdot[data-vendor]:not([data-vendor=""]).top', html)
        self.assertIn("stroke:var(--gold)", html)

    def test_vendor_colours_only_cover_contenders(self):
        """Colouring all 33 creators would need an indistinguishable palette."""
        from scipick.render import VENDOR_COLORS
        html = render(board(), DEFAULT_PRESETS)
        used = set(re.findall(r'style="fill:(#[0-9a-f]{6})"', html))
        self.assertTrue(used)
        # A board of three models must not consume the whole palette.
        self.assertLessEqual(len(used), len(VENDOR_COLORS))
        self.assertLessEqual(len(used), len(board()))

    def test_every_coloured_dot_has_a_legend_entry(self):
        """A colour with no legend entry is unreadable, so the two must agree."""
        big = board() + [
            model(f"Filler {i}", capability=20.0, coding=20.0, longcontext=20.0,
                  price=0.5 + i, scicode=0.2, lcr=0.2, hle=0.1, aaii=20.0,
                  terminal=0.2)
            for i in range(12)
        ]
        html = render(big, DEFAULT_PRESETS, limit=60)
        body = panels(html)["capability"]
        dotted = set(re.findall(r'class="fdot[^"]*"\s*style="fill:(#[0-9a-f]{6})"',
                                body))
        f = body.find('<figure class="fig"')
        fig = body[f:body.find("</figure>", f)]
        legend = set(re.findall(r'class="sw" style="background:(#[0-9a-f]{6})"', fig))
        self.assertTrue(dotted)
        self.assertEqual(dotted - legend, set(),
                         "a dot colour has no legend swatch")

    def test_short_name_drops_serving_variant(self):
        self.assertEqual(_short_name("Claude Opus 5.5 (Max, Default Fallback)"),
                         "Claude Opus 5.5")

    def test_no_priced_models_says_so(self):
        # price=0 is how the pipeline records "no published price".
        unpriced = [model("Free Model", capability=50.0, price=0,
                          scicode=0.5, lcr=0.5, hle=0.5, aaii=50.0,
                          terminal=0.5)]
        svg = _frontier(unpriced, DEFAULT_PRESETS["capability"])
        self.assertIn("frontier.nopriced", svg)

    def test_narrow_score_range_still_labels_the_axis(self):
        """A board whose scores are nearly equal must not print duplicate ticks.

        With a tight range, integer tick labels all round to the same value and
        the axis reads "50 50 50 50" — worse than useless.
        """
        flat = [model(f"Flat {i}", capability=50.0, coding=50.0,
                      longcontext=50.0, price=1.0 + i, scicode=0.5, lcr=0.5,
                      hle=0.5, aaii=50.0 + i * 0.01, terminal=0.5)
                for i in range(4)]
        svg = _frontier(flat, DEFAULT_PRESETS["capability"])
        ticks = re.findall(r'class="ft" text-anchor="end">([^<]+)</text>', svg)
        self.assertGreater(len(set(ticks)), 1, f"duplicate y ticks: {ticks}")


class SummaryCardTest(unittest.TestCase):
    """The three summary cards must each say something the others do not."""

    def card_values(self, key):
        html = render(board(), DEFAULT_PRESETS, limit=60)
        body = panels(html)[key]
        cards = re.findall(
            r'<div class="k"[^>]*>(card\.[\w.]+)</div>\s*'
            r'<div class="v[^"]*">([^<]*)</div>',
            body,
        )
        return dict(cards)

    def test_value_view_does_not_repeat_the_ranked_count(self):
        """On an efficiency board every ranked model is priced by definition.

        A "models with a published price" card would therefore print the same
        number as "models ranked" directly beside it, which reads as a bug. The
        value view reports the unpriced exclusions instead.
        """
        cards = self.card_values("value")
        self.assertIn("card.unpriced", cards)
        self.assertNotIn("card.priced", cards)
        self.assertNotEqual(cards["card.unpriced"], cards["card.ranked"])

    def test_score_views_report_the_priced_count(self):
        for key in ("capability", "coding", "longcontext"):
            with self.subTest(view=key):
                self.assertIn("card.priced", self.card_values(key))

    def test_every_card_value_is_populated(self):
        for key in DEFAULT_PRESETS:
            cards = self.card_values(key)
            with self.subTest(view=key):
                self.assertEqual(len(cards), 3)
                for name, value in cards.items():
                    self.assertTrue(value.strip(), f"{name} is empty")


class ExclusionNoteTest(unittest.TestCase):
    """Exclusion notes must state the reason that is actually true.

    A leaderboard's whole claim is that its rules are stated rather than
    hidden, so a note naming the wrong reason is worse than no note. The
    original bug: models whose coverage was 1.00 were reported as "below the
    50% coverage floor" because they had no price.
    """

    def view(self, key):
        return panels(render(board(), DEFAULT_PRESETS, limit=60))[key]

    def test_unpriced_model_is_reported_as_unpriced_not_low_coverage(self):
        # Full coverage, but no price: the only reason it cannot be ranked by
        # ability per dollar is the missing price.
        row = [model("No Price Model", capability=80.0, coding=80.0,
                     longcontext=80.0, price=0, scicode=0.9, lcr=0.9,
                     hle=0.8, aaii=80.0, terminal=0.8)]
        html = render(row, DEFAULT_PRESETS, limit=60)
        val = panels(html)["value"]
        self.assertIn("data-noprice-n=", val)
        self.assertNotIn("data-floor-n=", val)

    def test_low_coverage_model_is_reported_as_low_coverage(self):
        # A single metric present: coverage is below every preset's floor.
        row = [model("Sparse Model", capability=90.0,
                     price=1.0)]
        row[0]["coverage"] = {k: 0.1 for k in DEFAULT_PRESETS}
        html = render(row, DEFAULT_PRESETS, limit=60)
        self.assertIn("data-floor-n=", panels(html)["capability"])

    def test_notes_carry_a_count_that_matches_the_fixture(self):
        html = render(board(), DEFAULT_PRESETS, limit=60)
        body = panels(html)["capability"]
        m = re.search(r'data-floor-n="(\d+)"', body)
        if m:
            self.assertGreater(int(m.group(1)), 0)

    def test_note_wording_matches_the_note_kind(self):
        """The unpriced sentence must not claim the models are still listed.

        They are excluded from the table, so a note saying "listed here" would
        be false. This guards the wording, not just the key.
        """
        for lang in LANGS:
            with self.subTest(lang=lang):
                text = STRINGS[lang]["panel.noprice"].lower()
                self.assertNotIn("listed here", text)
                self.assertIn("{n}", STRINGS[lang]["panel.noprice"])


class FullRankingTest(unittest.TestCase):
    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=2)
        self.panels = panels(self.html)

    def test_every_row_is_in_the_dom(self):
        """Truncation must be presentational, not a data loss.

        Search and sort run client-side over the whole set, so every row has to
        be shipped even when most of them start collapsed.
        """
        body = self.panels["capability"]
        total = len(re.findall(r'<tr data-name=', body))
        self.assertEqual(total, len(board()))

    def test_rows_past_the_limit_start_collapsed(self):
        body = self.panels["capability"]
        self.assertEqual(len(re.findall(r'<tr data-name="[^"]*" class="deep"',
                                       body)), len(board()) - 2)

    def test_controls_present_only_when_rows_are_hidden(self):
        self.assertIn('data-more', self.panels["capability"])
        # A limit at or above the board size hides nothing, so no control.
        full = render(board(), DEFAULT_PRESETS, limit=99)
        self.assertNotIn('class="tctl"', panels(full)["capability"])

    def test_no_cap_shows_every_row(self):
        """limit=0 and limit=None both mean "no cap".

        A 0 must not mark every row collapsed while also suppressing the control
        that reveals them — that combination renders an empty table.
        """
        for lim in (0, None):
            with self.subTest(limit=lim):
                html = render(board(), DEFAULT_PRESETS, limit=lim)
                body = panels(html)["capability"]
                self.assertEqual(body.count('class="deep"'), 0)
                self.assertNotIn('class="tctl"', body)
                self.assertEqual(len(re.findall(r'<tr data-name=', body)),
                                 len(board()))

    def test_low_limit_keeps_a_way_to_reveal_rows(self):
        html = render(board(), DEFAULT_PRESETS, limit=1)
        body = panels(html)["capability"]
        self.assertIn('class="tctl"', body)
        self.assertGreater(body.count('class="deep"'), 0)

    def test_row_caps_never_exceed_the_board(self):
        body = self.panels["capability"]
        caps = [int(v) for v in re.findall(r'<option value="(\d+)"', body)]
        # 0 is the "All" sentinel.
        for c in caps:
            if c:
                self.assertLess(c, len(board()))

    def test_sort_keys_are_machine_readable(self):
        # Sorting parses data-k-* rather than cell text, so "$1.20" and an em
        # dash never reach parseFloat.
        body = self.panels["capability"]
        self.assertIn("data-k-score=", body)
        self.assertIn("data-k-price=", body)
        self.assertIn("data-k-eff=", body)
        self.assertIn("data-k-cov=", body)
        self.assertIn("data-k-model=", body)

    def test_missing_values_have_empty_sort_key(self):
        """An unpriced model must not sort as if it cost zero."""
        row = [m for m in board() if m["pricing"].get("blended") is None]
        if not row:
            self.skipTest("no unpriced model in the fixture")
        html = render(row, DEFAULT_PRESETS, limit=60)
        self.assertRegex(html, r'data-k-price=""')

    def test_sortable_headers_are_keyboard_reachable(self):
        body = self.panels["capability"]
        for col in ("model", "score", "price", "eff", "cov"):
            self.assertIn(f'data-sort="{col}"', body)


class I18nTest(unittest.TestCase):
    def test_both_languages_have_identical_keys(self):
        en, zh = set(STRINGS["en"]), set(STRINGS["zh"])
        self.assertEqual(en - zh, set())
        self.assertEqual(zh - en, set())

    def test_page_ships_every_language(self):
        html = render(board(), DEFAULT_PRESETS)
        for lang in LANGS:
            self.assertIn(f'"{lang}"', html)

    def test_interpolated_strings_keep_their_placeholders(self):
        for key in ("search.count", "table.showall", "panel.floor",
                    "panel.noprice"):
            for lang in LANGS:
                with self.subTest(key=key, lang=lang):
                    tpl = STRINGS[lang][key]
                    self.assertIn("{", tpl)
                    self.assertIn("}", tpl)

    def test_every_referenced_key_exists_in_every_language(self):
        """A data-i18n hook with no matching string renders as the raw key.

        That is the kind of defect that only shows up after switching language,
        so it is worth asserting directly rather than trusting the templates.
        """
        html = render(board(), DEFAULT_PRESETS, limit=60)
        keys = set()
        for pat in (r'data-i18n="([^"]+)"', r"data-i18n='([^']+)'",
                    r'data-i18n-html="([^"]+)"', r'data-i18n-ph="([^"]+)"',
                    r'data-i18n-title="([^"]+)"', r'data-tpl="([^"]+)"',
                    r"data-tpl='([^']+)'"):
            keys |= set(re.findall(pat, html))
        self.assertTrue(keys)
        for lang in LANGS:
            missing = sorted(k for k in keys if k not in STRINGS[lang])
            with self.subTest(lang=lang):
                self.assertEqual(missing, [])

    def test_preset_labels_are_translated(self):
        for key in DEFAULT_PRESETS:
            for lang in LANGS:
                with self.subTest(key=key, lang=lang):
                    self.assertIn(f"preset.{key}.label", STRINGS[lang])

    def test_builtin_preset_labels_carry_a_translation_hook(self):
        html = render(board(), DEFAULT_PRESETS)
        self.assertIn('data-i18n="preset.capability.label"', html)


class LayoutTest(unittest.TestCase):
    """CSS invariants that are easy to break and invisible in a unit test.

    Each of these corresponds to a defect found by measuring the rendered page
    in a real browser, which is the only way to catch them.
    """

    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=60)

    def test_ranking_table_is_not_a_scroll_container_when_wide(self):
        """An overflow-x wrapper silently disables sticky table headers.

        The ranking table must therefore not have one by default; only the
        sub-860px override may introduce it, because below that the columns
        genuinely do not fit.
        """
        self.assertIn(".panel .tw{overflow-x:visible}", self.html)
        self.assertIn("@media(max-width:860px)", self.html)
        # The override must come after the base rule or it cannot win.
        self.assertLess(self.html.index(".panel .tw{overflow-x:visible}"),
                        self.html.index("@media(max-width:860px)"))

    def test_sticky_header_offset_clears_the_page_bar(self):
        """top:0 would tuck the header behind the sticky page bar."""
        self.assertIn("top:var(--topbar,67px)", self.html)
        self.assertIn("--topbar:67px", self.html)
        # The bar wraps on narrow screens, so the offset must change with it.
        self.assertIn("--topbar:106px", self.html)

    def test_sticky_header_has_a_background_and_z_index(self):
        # A transparent sticky header lets rows show through as they scroll.
        self.assertRegex(self.html, r"position:sticky;top:var\(--topbar[^}]*"
                                    r"background:var\(--bg\);z-index:1")

    def test_collapsed_rows_lose_to_the_filter_rule(self):
        """tr.hide must still win over the row-cap rule.

        If the cap rule were a bare `tr.deep`, a row that is both collapsed and
        filtered out would be resurrected by the filter.
        """
        self.assertIn("tr.deep:not(.shown){display:none}", self.html)

    def test_frontier_labels_have_a_halo(self):
        # Labels cross the frontier line; without a halo they become unreadable.
        self.assertRegex(self.html, r"\.fl\{[^}]*paint-order:stroke")

    def test_mobile_frontier_pans_rather_than_shrinking(self):
        # A fixed viewBox scaled to 390px would render 11px labels at ~4px.
        self.assertIn(".fig svg{min-width:660px}", self.html)


class ShellTest(unittest.TestCase):
    def test_single_self_contained_document(self):
        html = render(board(), DEFAULT_PRESETS)
        self.assertTrue(html.lstrip().startswith("<!DOCTYPE html>"))
        # No external requests: the page must work offline and from file://.
        self.assertNotIn("<link rel=\"stylesheet\"", html)
        self.assertNotIn("src=\"http", html)

    def test_no_unrendered_placeholders(self):
        html = render(board(), DEFAULT_PRESETS)
        for token in ("{n}", "{shown}", "{total}", "{col}", "{dir}"):
            self.assertNotIn(f">{token}<", html)

    def test_reduced_motion_disables_the_draw_in(self):
        # A half-drawn frontier would misstate the data, so it must land whole.
        html = render(board(), DEFAULT_PRESETS)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("stroke-dasharray:none", html)


if __name__ == "__main__":
    unittest.main()
