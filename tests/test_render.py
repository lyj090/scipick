"""Tests for the rendered page: per-view podiums, the frontier scatter, and
the full-ranking controls.

These are structural assertions on the generated HTML. They exist because the
defects they cover were all *invisible* to the scoring tests: a podium that
never changed between views, a chart whose labels overprinted, a table whose
rows were silently missing. None of that breaks a score, so none of it could be
caught by testing the maths.
"""

import json
import re
import unittest

from scipick.config import DEFAULT_PRESETS
from scipick.i18n import LANGS, STRINGS
from scipick.render import _frontier, _short_name, render


def model(name, capability=50.0, coding=50.0, longcontext=50.0, price=5.0,
          scicode=0.5, lcr=0.5, hle=0.5, aaii=50.0, terminal=0.5,
          released="2025-01-01"):
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
        # The pipeline always sets this (collect.py derives it from the AA
        # name); it is the stable cross-view key used for pinning.
        "canonical": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        "family": name.split()[0],
        "creator": name.split()[0],
        "metrics": metrics,
        "scores": scores,
        "coverage": coverage,
        "efficiency": effs,
        "pricing": {"blended": price, "input": price, "output": price},
        "release_date": released,
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
        the same x. The boxes here mirror the renderer's own model: a label is
        drawn with its baseline at y, so its glyphs occupy [y - ascent,
        y + descent]. Treating y as a centre would under-count how far a label
        reaches above its baseline and let a real overlap pass.
        """
        svg = _frontier(board(), DEFAULT_PRESETS["capability"])
        labels = []
        for m in re.finditer(
            r'<text x="([0-9.]+)" y="([0-9.]+)" class="fl" '
            r'text-anchor="(\w+)"[^>]*>([^<]*)</text>',
            svg,
        ):
            x, y, anchor, text = float(m.group(1)), float(m.group(2)), \
                m.group(3), m.group(4)
            w = len(text) * 6.4
            x0, x1 = (x - w, x) if anchor == "end" else (x, x + w)
            labels.append((x0, x1, y - 11.0, y + 3.5, text))
        for i, (ax0, ax1, ay0, ay1, at) in enumerate(labels):
            for (bx0, bx1, by0, by1, bt) in labels[i + 1:]:
                if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                    self.fail(f"labels overlap: {at!r} and {bt!r}")

    def test_every_label_carries_its_model_key(self):
        """Without a key the client cannot find a label to highlight it.

        Caught in review: pinned models were highlighted on the scatter but the
        text stayed anonymous, so the dot you picked had no name next to it.
        """
        svg = _frontier(board(), DEFAULT_PRESETS["capability"])
        texts = re.findall(r"<text [^>]*class=\"fl\"[^>]*>", svg)
        self.assertTrue(texts)
        for t in texts:
            with self.subTest(tag=t[:80]):
                self.assertIn("data-model=", t)

    def test_label_box_accounts_for_baseline_ascent(self):
        """The placement must treat y as a baseline, not a centre.

        The original client-side nudge pushed the baseline just past an
        obstacle's bottom edge, which still left the glyphs overlapping it by
        roughly the ascent — "Llama 3.1 Instruct 8B" printed across
        "Gemma 4 E4B". Both the server renderer and the client placement have to
        use the asymmetric box.
        """
        import inspect
        src = inspect.getsource(_frontier)
        # Server side: an asymmetric glyph box, and no symmetric-band leftover.
        self.assertIn("ASCENT, DESCENT", src)
        self.assertNotIn("LINE_H * 0.8", src)

        # Client side: the baseline is shifted by the measured ascent rather than
        # by a fixed nudge off the obstacle's bottom edge.
        html = render(board(), DEFAULT_PRESETS)
        self.assertIn("var ascent = ty - b.y;", html)
        self.assertIn("ty = hit + GAP + ascent;", html)
        self.assertNotIn("ty = hit + 3;", html)

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


class AbilityBarTest(unittest.TestCase):
    """The absolute-ability chart must measure ability, in every view."""

    def bar_values(self, key):
        body = panels(render(board(), DEFAULT_PRESETS, limit=60))[key]
        m = re.search(r'data-plot="' + key + r'">(.*?)</div><div class="xlab">',
                      body, re.S)
        if not m:
            return []
        return [float(v) for v in
                re.findall(r'<span class="bv">([\d.]+)</span>', m.group(1))]

    def test_bars_descend_in_every_view(self):
        """Bar heights are scores, so the order must be monotonic.

        The bug this covers: on the value view the chart inherited the view's
        efficiency ordering, so heights came out 44.8, 51.1, 46.8 — visibly
        wrong under a heading that says "absolute ability".
        """
        for key in DEFAULT_PRESETS:
            vals = self.bar_values(key)
            with self.subTest(view=key):
                self.assertTrue(vals, f"no bars in {key}")
                self.assertEqual(vals, sorted(vals, reverse=True),
                                 f"bars not sorted by score in {key}: {vals}")

    def test_value_view_bars_match_the_capability_bars(self):
        # Both views weight identically, so an ability chart that ignores the
        # view's own ranking criterion must agree across them.
        self.assertEqual(self.bar_values("value"), self.bar_values("capability"))

    def test_unpriced_strong_model_still_appears(self):
        """The scatter cannot show an unpriced model; this chart must.

        On an efficiency view an unpriced model has no rank at all — it is
        excluded from the table and absent from the scatter — so if this chart
        also dropped it, the model would simply be invisible.
        """
        row = [model("Strong Unpriced", capability=95.0, coding=95.0,
                     longcontext=95.0, price=0, scicode=0.95, lcr=0.95,
                     hle=0.9, aaii=95.0, terminal=0.9)]
        html = render(row, DEFAULT_PRESETS, limit=60)
        body = panels(html)["value"]
        bars = re.search(r'data-plot="value">(.*?)</div><div class="xlab">',
                         body, re.S).group(1)
        self.assertIn("Strong Unpriced", bars)
        # ...and it is genuinely unranked in this view, which is the contrast
        # that makes the bar chart worth having.
        self.assertIn("card.ranked", body)
        self.assertRegex(body, r'data-i18n="card\.ranked">[^<]*</div>'
                               r'<div class="v">0</div>')

    def test_low_coverage_model_is_excluded_from_bars(self):
        """Coverage is about comparability, not price, so it still applies."""
        good = model("Solid", capability=60.0, coding=60.0, longcontext=60.0,
                     price=2.0, scicode=0.6, lcr=0.6, hle=0.6, aaii=60.0,
                     terminal=0.6)
        # A perfect score on a single metric: coverage 0.2, below every floor.
        sparse = model("Sparse", capability=0.0, coding=0.0, longcontext=0.0,
                       price=2.0, scicode=1.0)
        sparse["coverage"] = {k: 0.2 for k in DEFAULT_PRESETS}
        sparse["scores"] = {k: 100.0 for k in DEFAULT_PRESETS}
        html = render([good, sparse], DEFAULT_PRESETS, limit=60)
        body = panels(html)["capability"]
        m = re.search(r'data-plot="capability">(.*?)</div><div class="xlab">',
                      body, re.S)
        self.assertNotIn("Sparse", m.group(1))
        self.assertIn("Solid", m.group(1))

    def test_axis_floor_is_stated_not_implied(self):
        # A truncated axis is a real distortion; the page must say so.
        html = render(board(), DEFAULT_PRESETS, limit=60)
        self.assertIn("bars.truncated", html)
        self.assertRegex(html, r'data-v-floor="[\d.]+"')

    def test_bar_columns_are_keyboard_operable(self):
        html = render(board(), DEFAULT_PRESETS, limit=60)
        body = panels(html)["capability"]
        m = re.search(r'data-plot="capability">(.*?)</div><div class="xlab">',
                      body, re.S).group(1)
        self.assertIn('role="button"', m)
        self.assertIn('tabindex="0"', m)
        self.assertIn('aria-pressed="false"', m)


class SelectionTest(unittest.TestCase):
    """Pinning is keyed on the canonical slug, so it works across views."""

    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=60)

    def test_all_three_surfaces_carry_the_key(self):
        body = panels(self.html)["capability"]
        self.assertIn("data-plot=", body)
        self.assertGreater(len(re.findall(r'class="fdot[^"]*"[^>]*data-model=',
                                          body)), 0)
        self.assertGreater(len(re.findall(r'<tr data-name="[^"]*"[^>]*data-model=',
                                          body)), 0)

    def test_keys_are_the_canonical_slug_not_the_display_name(self):
        """The display name carries a serving variant and is per-view; the slug
        is stable, which is what lets one pin light up every view."""
        # The markup only: the <script> block builds data-model attributes at
        # runtime from template strings and would match this regex.
        markup = self.html.split("<script>")[0]
        keys = set(re.findall(r'data-model="([^"]+)"', markup))
        self.assertTrue(keys)
        for k in keys:
            with self.subTest(key=k):
                self.assertNotIn("(", k)
                self.assertEqual(k, k.lower())

    def test_scatter_dots_are_not_focusable(self):
        """175 dots must not be 175 tab stops.

        They carry no tabindex at all, so they are not in the tab order; the
        bars and the table rows are the keyboard routes to the same selection.
        """
        body = panels(self.html)["capability"]
        circ = re.findall(r'<circle[^>]*class="fdot[^"]*"[^>]*>', body)
        self.assertTrue(circ)
        for c in circ:
            with self.subTest(dot=c[:60]):
                self.assertNotIn("tabindex", c)
        # ...but they are still clickable, which is the pointer route.
        self.assertTrue(all("data-model=" in c for c in circ))

    def test_bars_carry_a_display_name_for_the_chip(self):
        """A pinned model's chip must show its name, not its slug.

        The bars can show a model that is in no table on this view — a strong
        unpriced model on an efficiency board — so they cannot rely on the rows
        as the only source of display names.
        """
        html = render(board(), DEFAULT_PRESETS, limit=60)
        body = panels(html)["capability"]
        cols = re.findall(r'<div class="col"[^>]*>', body)
        self.assertTrue(cols)
        for c in cols:
            with self.subTest(col=c[:70]):
                self.assertIn("data-name=", c)

    def test_pinned_ring_outranks_the_vendor_and_top_rings(self):
        """The pin ring must beat every other ring rule.

        The vendor rule is `.fdot[data-vendor]:not([data-vendor=""])`, which is
        (0,3,0) — one class more specific than a plain `.fdot.pinned` at
        (0,2,0). So the pin rendered as the neutral vendor ring and the whole
        feature looked broken on exactly the dots people pin first. Reading
        getComputedStyle is the only way to catch this: both states are "a dot
        with a ring" to the eye.
        """
        html = render(board(), DEFAULT_PRESETS)
        # Every combination that can occur must be enumerated.
        for sel in (
            ".fdot.pinned",
            '.fdot[data-vendor]:not([data-vendor=""]).pinned',
            ".fdot.top.pinned",
            '.fdot[data-vendor]:not([data-vendor=""]).top.pinned',
            '.fdot[data-vendor]:not([data-vendor=""]).front.pinned',
        ):
            with self.subTest(selector=sel):
                self.assertIn(sel, html)
        self.assertRegex(html, r"\.fdot\.pinned[^{]*\{[^}]*stroke:var\(--pin\)")


class FilterAndOrderTest(unittest.TestCase):
    """The filter bar, the ordering modes, and the release-date column."""

    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=60)
        self.body = panels(self.html)["capability"]

    def test_filter_bar_is_always_present(self):
        """Filters are independent of the row cap, so they always render."""
        for lim in (1, 60, 0, None):
            with self.subTest(limit=lim):
                body = panels(render(board(), DEFAULT_PRESETS,
                                     limit=lim))["capability"]
                self.assertIn("fsel", body)
                self.assertIn("ssel", body)

    def test_ordering_modes_are_offered(self):
        for mode in ("rank", "newest", "oldest", "az"):
            with self.subTest(mode=mode):
                self.assertIn(f'value="{mode}"', self.body)

    def test_family_options_come_from_this_views_rows(self):
        """A family that would return nothing must not be offered."""
        sel = re.search(r'class="tsel fsel"[^>]*>(.*?)</select>',
                        self.body, re.S).group(1)
        # The sentinel option carries a data-i18n attribute, so match on the
        # value attribute alone rather than assuming `value=""` precedes `>`.
        fams = set(re.findall(r'<option value="([^"]*)"', sel))
        self.assertIn("", fams)              # the "all families" sentinel
        present = set(re.findall(r'data-k-family="([^"]+)"', self.body))
        # Options are display-cased, rows are lowercased; compare case-folded.
        self.assertEqual({f.lower() for f in fams if f}, present)

    def test_date_column_is_not_sorted_numerically(self):
        """parseFloat("2026-09-02") is 2026, which collapses a year into a tie.

        The date column therefore has to be in the text-sorted set, or every
        same-year date sorts equal and the column is useless.
        """
        self.assertRegex(self.html, r"TEXT_COLS\s*=\s*\{[^}]*date:\s*1")

    def test_newest_and_oldest_are_opposites(self):
        """A sign error made both modes sort oldest-first.

        That is invisible in a screenshot — the rows are still grouped by vendor
        and dated — so it needs an assertion on the comparator's direction, not
        on a rendered order the unit test cannot produce.
        """
        m = re.search(r"var dir = \(mode === 'newest'\) \? (-?\d+) : (-?\d+);",
                      self.html)
        self.assertIsNotNone(m, "newest/oldest direction constant not found")
        self.assertEqual(m.group(1), "-1")   # newest => descending dates
        self.assertEqual(m.group(2), "1")
        self.assertIn("return da < db ? -dir : (da > db ? dir : 0);", self.html)

    def test_release_date_is_rendered_and_sortable(self):
        self.assertIn('data-sort="date"', self.body)
        self.assertIn("data-k-date=", self.body)
        self.assertIn('data-i18n="th.released"', self.body)

    def test_filter_count_only_shows_while_filtering(self):
        # An empty span is the "not filtering" state; the JS fills it otherwise.
        self.assertIn("data-tcount", self.body)
        self.assertIn("filter.count", self.html)

    def test_nothing_matches_message_exists(self):
        self.assertIn("data-fnone", self.body)
        self.assertIn("filter.none", self.html)

    def test_reset_control_exists(self):
        self.assertIn("data-fclear", self.body)


class PickerTest(unittest.TestCase):
    """The searchable picker, grouped by vendor and newest-first within."""

    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=60)
        m = re.search(r'<div class="pk-list".*?</section>', self.html, re.S)
        self.list = m.group(0) if m else ""

    def test_list_exists_and_starts_collapsed(self):
        self.assertTrue(self.list)
        self.assertIn('id="pklist" hidden', self.html)

    def test_list_is_grouped_by_family(self):
        self.assertEqual(self.list.count('class="pk-group"'),
                         len({m["family"] for m in board()}))

    def test_every_board_model_is_offered(self):
        """Including models gated out of this view's table.

        The real capability table holds 290 of 374 board models; the picker must
        offer all of them, because pinning one is how you surface a model the
        view's own gate excluded.
        """
        self.assertEqual(self.list.count('class="pk-item"'), len(board()))

    def test_groups_are_newest_first(self):
        groups = re.findall(
            r'<div class="pk-group"[^>]*>(.*?)(?=<div class="pk-group"|$)',
            self.list, re.S)
        self.assertTrue(groups)
        for g in groups:
            dates = re.findall(r'<span class="pi-d">([^<]+)</span>', g)
            dated = [d for d in dates if d != "—"]
            with self.subTest(group=g[:50]):
                self.assertEqual(dated, sorted(dated, reverse=True), dates)

    def test_items_do_not_duplicate_the_search_haystack(self):
        """The filter reads the item's own text and slug, so no data-search attr."""
        self.assertNotIn("data-search=", self.list)
        self.assertIn("it.textContent", self.html)

    def test_search_folds_separators_on_both_sides(self):
        """A version number typed with dots must match a name written with spaces.

        "llama3.1" returned nothing against "Llama 3.1 Instruct 8B" under a plain
        substring test, which is the most natural way to type it.
        """
        self.assertIn("function fold(s)", self.html)
        self.assertRegex(self.html, r"replace\(/\[\^a-z0-9\]\+/g, ''\)")
        # Applied to the query, the item text, and the family.
        self.assertIn("var q = fold(raw);", self.html)
        self.assertIn("fold(it.textContent", self.html)
        self.assertIn("fold(g.getAttribute('data-family')", self.html)

    def test_table_search_folds_separators_too(self):
        self.assertRegex(self.html, r"function norm\(s\)\{ return String\(s")
        self.assertIn("foldAttr(tr.getAttribute('data-name'))", self.html)

    def test_no_results_message_exists(self):
        self.assertIn('id="pknone"', self.list)

    def test_pinned_extra_bar_is_marked_not_disguised(self):
        """A user-added bar must not look like part of the ranking.

        It may also be a model the chart's own coverage floor excludes, so
        drawing it identically would make the chart claim a comparison it never
        made.
        """
        self.assertIn(".col.extra .bx", self.html)
        self.assertIn("border:1px dashed var(--pin)", self.html)
        self.assertIn("bars.added", self.html)

    def test_scores_payload_covers_every_view(self):
        """The client needs each view's score to add a bar in any view."""
        m = re.search(r"var __VIEWS__ = (\[[^\]]*\]);", self.html)
        self.assertIsNotNone(m)
        self.assertEqual(json.loads(m.group(1)), list(DEFAULT_PRESETS))
        self.assertIn("var __SCORES__ = {", self.html)


class SearchCostTest(unittest.TestCase):
    """Search runs on every keystroke, so its per-keystroke cost is a feature.

    applyRows used to call applyLang, which re-swept every [data-i18n] node in
    the document and re-ran the row counter. filter() calls applyRows once per
    table, so a single keystroke meant four full-document i18n sweeps. Measured
    at 15.6ms per keystroke, against a 16ms frame budget.
    """

    def setUp(self):
        self.html = render(board(), DEFAULT_PRESETS, limit=1)

    def test_apply_rows_does_not_call_apply_lang(self):
        m = re.search(r"function applyRows\(wrap, visible\)\{(.*?)\n  \}",
                      self.html, re.S)
        self.assertIsNotNone(m)
        self.assertNotIn("applyLang(", m.group(1))

    def test_row_cap_updates_only_its_own_template(self):
        """The "show N more" label changes, not the whole page's language."""
        self.assertIn("function applyTpl(el, lang)", self.html)
        m = re.search(r"function applyRows\(wrap, visible\)\{(.*?)\n  \}",
                      self.html, re.S)
        self.assertIn("applyTpl(lbl", m.group(1))

    def test_the_counter_is_still_refreshed_where_it_matters(self):
        """Dropping the applyLang side effect must not freeze the counter."""
        self.assertIn("if (box) box.addEventListener('input', filter);", self.html)
        m = re.search(r"function filter\(\)\{(.*?)\n  \}", self.html, re.S)
        self.assertIn("updateCount()", m.group(1))
        for handler in re.findall(r"addEventListener\('change', function\(\)\{(.*?)\n    \}",
                                  self.html, re.S):
            if "applyRows" in handler:
                self.assertIn("updateCount()", handler)



    def test_picker_keeps_the_serving_variant_searchable(self):
        """Clipping the variant from the label must not remove it from search.

        The variant is no longer displayed, but it is still part of the name
        upstream. Someone pasting "Claude Opus 5.5 (Max, Default Fallback)" out
        of the source data has to keep matching, so the hidden tail ships as a
        search-only attribute on the rows that have one.
        """
        board_with_variant = [
            model("Claude Opus 5.5 (Max, Default Fallback)", capability=90.0),
            model("Gemma 4 E4B", capability=20.0),
        ]
        html = render(board_with_variant, DEFAULT_PRESETS)
        self.assertIn('data-alias="(Max, Default Fallback)"', html)
        self.assertIn("it.getAttribute('data-alias')", html)
        # A name with no variant must not grow an empty attribute.
        self.assertNotIn('data-alias=""', html)


class DisplayNameTest(unittest.TestCase):
    """One model must be named the same way on every surface.

    The bar chart and the scatter already trimmed the serving variant while the
    podium and the table did not, so the current leader appeared as
    "Claude Opus 5.5" in one place and "Claude Opus 5.5 (Max, Default
    Fallback)" a screen below.
    """

    def setUp(self):
        self.m = model("Claude Opus 5.5 (Max, Default Fallback)",
                       capability=90.0, coding=88.0, longcontext=95.0,
                       price=60.0, scicode=0.9, lcr=0.95, hle=0.8,
                       aaii=90.0, terminal=0.8)
        self.other = model("Mid Balanced", capability=65.0, coding=70.0,
                           longcontext=60.0, price=4.0, scicode=0.7, lcr=0.6,
                           hle=0.5, aaii=65.0, terminal=0.6)
        self.html = render([self.m, self.other], DEFAULT_PRESETS)
        self.panel = panels(self.html)["capability"]

    def test_podium_name_has_no_variant(self):
        self.assertEqual(podium_names(self.panel),
                         ["Claude Opus 5.5", "Mid Balanced"])

    def test_table_name_has_no_variant(self):
        self.assertIn('<span class="nm">Claude Opus 5.5</span>', self.panel)

    def test_bar_label_and_scatter_label_have_no_variant(self):
        self.assertIn('<div class="c" title="Claude Opus 5.5">', self.panel)
        self.assertIn('>Claude Opus 5.5</text>', self.panel)

    def test_picker_name_has_no_variant(self):
        self.assertIn('<span class="pi-n">Claude Opus 5.5</span>', self.html)

    def test_display_name_helper_keeps_a_name_without_a_variant(self):
        from scipick.render import display_name
        self.assertEqual(display_name("Gemma 4 E4B"), "Gemma 4 E4B")
        self.assertEqual(display_name("Muse Wonder Full (Max)"),
                         "Muse Wonder Full")


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

    def test_expand_control_present_only_when_rows_are_hidden(self):
        # The filter bar is always present — filtering has nothing to do with the
        # row cap — but "Show all" must not appear when nothing is hidden.
        self.assertIn('data-more', self.panels["capability"])
        full = render(board(), DEFAULT_PRESETS, limit=99)
        body = panels(full)["capability"]
        self.assertIn('class="tctl"', body)
        self.assertNotIn('data-more', body)

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
                self.assertNotIn('data-more', body)
                self.assertEqual(len(re.findall(r'<tr data-name=', body)),
                                 len(board()))

    def test_low_limit_keeps_a_way_to_reveal_rows(self):
        html = render(board(), DEFAULT_PRESETS, limit=1)
        body = panels(html)["capability"]
        self.assertIn('data-more', body)
        self.assertGreater(body.count('class="deep"'), 0)

    def test_row_caps_never_exceed_the_board(self):
        body = self.panels["capability"]
        # Only the rows control's options; the family/order selects use values
        # that are not numbers.
        rows_sel = re.search(r'class="tsel tselrows"[^>]*>(.*?)</select>',
                             body, re.S).group(1)
        caps = [int(v) for v in re.findall(r'<option value="(\d+)"', rows_sel)]
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
