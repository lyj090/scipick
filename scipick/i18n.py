"""Interface strings, English and Chinese.

Model names, family names and metric names come from the data and are not
translated. Everything the interface itself says lives here.

The page ships both languages and switches client-side, so one static file
serves either audience. Tables render once — they are language-neutral — and
only labelled elements are swapped, which keeps the payload small enough to
stay a single self-contained document.
"""

from __future__ import annotations

LANGS = ("en", "zh")
DEFAULT_LANG = "en"

#: BCP-47 tags for the <html lang> attribute.
HTML_LANG = {"en": "en", "zh": "zh-CN"}

#: Label shown on the language switch.
LANG_LABEL = {"en": "中文", "zh": "EN"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "page.title": "scipick — LLM selection leaderboard",
        "page.desc": (
            "A weighted LLM leaderboard for research and engineering work. "
            "Rank models by what you actually care about, with editable weights."
        ),
        "brand": "scipick",
        "tagline": (
            "A weighted LLM leaderboard for research and engineering work. "
            "Benchmark data from Artificial Analysis; the weighting is ours and adjustable."
        ),
        "generated": "Generated",
        "search.placeholder": "Filter models…",
        "search.count": "{shown} of {total}",
        "theme.toggle": "Toggle dark mode",
        "tab.aria": "Leaderboard view",

        # Summary cards
        "card.ranked": "Models ranked",
        "card.ranked.note": "coverage ≥ {pct}",
        "card.median": "Median score",
        "card.median.note": "median score in this view",
        "card.priced": "Priced models",
        "card.priced.note": "models with a published price",
        "card.unpriced": "No price",
        "card.unpriced.note": "excluded: no published price",
        "card.noprice": "no published price",

        # Panels
        "panel.full": "Full ranking",
        "panel.empty": "No models matched this view.",
        "panel.sorted.score": "Sorted by weighted score.",
        "panel.sorted.eff": "Sorted by ability per dollar.",
        "panel.cov_note": "Cov. is the share of this view's weight that had data.",
        "panel.floor": (
            "{n} further model(s) have a partial score here but fall below the "
            "{pct} coverage floor and are not ranked. Their data covers too few of "
            "the weighted benchmarks to place them meaningfully against the rest."
        ),
        "panel.noprice": (
            "{n} model(s) score in this view but publish no price, so they cannot "
            "be ranked by ability per dollar and are excluded from the table. "
            "They are counted here so the gap in the ranking is visible."
        ),

        # Table
        "th.model": "Model",
        "th.family": "Family",
        "th.score": "Score",
        "th.price": "$/1M",
        "th.eff": "Eff.",
        "th.cov": "Cov.",
        "row.local": "local",

        # Full-ranking controls
        "table.showall": "Show all {n}",
        "table.rows": "Rows",
        "table.all": "All",
        "table.hint": "Click any column heading to sort. Use Rows to change how many are shown.",

        # Methodology
        "method.title": "Weighting",
        "method.desc": (
            "Every view is the same metric set under different weights. "
            "Edit <code>config/presets.yaml</code> to define your own."
        ),
        "method.preset": "View",
        "method.weights": "Weights",
        "method.rankby": "Rank by",
        "method.floor": "Coverage floor",

        "howto.title": "How to read this",
        "howto.body": (
            "<b>Not an official ranking.</b> Scores are weighted benchmarks rescaled "
            "to 0–100. A benchmark a model was never run on is skipped and the "
            "remaining weights are renormalised — so <b>Cov.</b> tells you how much of "
            "the weighting actually had data. A score at 0.4 coverage rests on "
            "fewer benchmarks than one at 1.0. Value is score per blended dollar "
            "(3:1 input:output); models without a published price have no value score."
        ),

        "meta.title": "Data",
        "meta.aa": "Artificial Analysis data API",
        "meta.fetched": "{n} models fetched",
        "meta.rankable": "{n} rankable",
        "meta.localgateway": "Local gateway",
        "meta.byline": "Scoring and presentation by scipick.",
        "meta.license": "MIT licensed",
        "bench.title": "Benchmarks",
        "bench.desc": (
            "What the weighted metrics actually measure, and how much of the "
            "board reports each one. Coverage matters: a benchmark present for "
            "every model is stronger evidence than one present for a third."
        ),
        "bench.metric": "Benchmark",
        "bench.measures": "What it measures",
        "bench.scale": "Scale",
        "bench.coverage": "Coverage",
        "bench.scicode": "Scientific code generation — solving research-level programming problems.",
        "bench.hle": "Humanity's Last Exam — broad expert-level reasoning across disciplines.",
        "bench.index": "Aggregate reasoning index across many evaluations.",
        "bench.lcr": "Retrieving and reasoning over long inputs, such as whole repositories.",
        "bench.terminal": "Agentic execution in a real shell — multi-step command-line tasks.",
        "method.note": (
            "Weights are relative and renormalised per model, so a missing "
            "benchmark never counts as a zero score."
        ),
        # Each view's podium names its own leaders, so switching tabs changes
        # what you see. The secondary line names the leader on the *other*
        # axis, which keeps both questions answered per view without repeating
        # the same three names under a different heading.
        "podium.by.score": "Top 3 by weighted score",
        "podium.by.value": "Top 3 by ability per dollar",
        "podium.leader.value": "Best value here",
        "podium.leader.score": "Highest score here",
        "podium.per_dollar": "pts/$",

        # Frontier chart
        "frontier.title": "Score vs price",
        "frontier.desc": (
            "Every priced model in this view. The line is the efficient frontier: "
            "the best score available at or below each price. Points on it are "
            "the ones that are not dominated on both axes at once."
        ),
        "frontier.axis.price": "Blended price, $/1M tokens (log scale)",
        "frontier.axis.score": "Weighted score",
        "frontier.legend.frontier": "efficient frontier",
        "frontier.legend.other": "other models",
        "frontier.legend.top": "top 3",
        "frontier.nopriced": "No model in this view has a published price.",
        "meta.source_code": "Source",
        "meta.selection": (
            "Selected from {aa} models: latest generation per product line, "
            "mainstream vendors only ({superseded} superseded and {vendors} "
            "non-allowlisted rows excluded)."
        ),

        # Preset descriptions (built-in presets only; custom presets from the
        # config file are shown as written by their author).
        "preset.capability.label": "Capability",
        "preset.value.label": "Value",
        "preset.coding.label": "Coding",
        "preset.longcontext.label": "Long context",
        "preset.capability.desc": "Absolute ability, price ignored.",
        "preset.value.desc": "Ability per dollar, among models within reach of the frontier.",
        "preset.coding.desc": "Weighted toward code generation and terminal execution.",
        "preset.longcontext.desc": "For whole-repository or long-document reasoning.",
    },
    "zh": {
        "page.title": "scipick — 科研选型榜单",
        "page.desc": (
            "面向科研与工程工作的加权大模型榜单。"
            "按你真正关心的目标排序，权重可改。"
        ),
        "brand": "scipick",
        "tagline": (
            "面向科研与工程工作的加权大模型榜单。"
            "基准数据来自 Artificial Analysis，权重由本工具定义且可调。"
        ),
        "generated": "生成于",
        "search.placeholder": "筛选模型…",
        "search.count": "{shown} / {total}",
        "theme.toggle": "切换深色模式",
        "tab.aria": "榜单视图",

        "card.ranked": "入榜模型",
        "card.ranked.note": "覆盖率 ≥ {pct}",
        "card.median": "中位得分",
        "card.median.note": "该视图下的得分中位数",
        "card.priced": "有定价模型",
        "card.priced.note": "公布了价格的模型数",
        "card.unpriced": "无价格",
        "card.unpriced.note": "因未公布价格而排除",
        "card.noprice": "未公布价格",

        "panel.full": "完整排名",
        "panel.empty": "该视图下没有符合条件的模型。",
        "panel.sorted.score": "按加权得分排序。",
        "panel.sorted.eff": "按每美元能力排序。",
        "panel.cov_note": "Cov. 表示该视图权重中真正有数据的比例。",
        "panel.floor": (
            "另有 {n} 个模型在该视图下有部分得分，但低于 {pct} 的覆盖率下限，"
            "未参与排名。它们的数据覆盖的加权基准过少，与其他模型不具可比性。"
        ),
        "panel.noprice": (
            "另有 {n} 个模型在该视图下有得分，但没有公布价格，无法按每美元"
            "能力排名，因此未列入表格。此处给出数量，让排名的缺口是可见的。"
        ),

        "th.model": "模型",
        "th.family": "家族",
        "th.score": "得分",
        "th.price": "$/1M",
        "th.eff": "效率",
        "th.cov": "覆盖",
        "row.local": "本地",

        "table.showall": "显示全部 {n} 个",
        "table.rows": "行数",
        "table.all": "全部",
        "table.hint": "点击任意列标题即可排序；用「行数」调整显示条数。",
        "row.local": "本地可调",

        "method.title": "权重",
        "method.desc": (
            "所有视图共用同一组指标，只是权重不同。"
            "编辑 <code>config/presets.yaml</code> 即可自定义。"
        ),
        "method.preset": "视图",
        "method.weights": "权重",
        "method.rankby": "排序依据",
        "method.floor": "覆盖率下限",

        "howto.title": "怎么读这份榜单",
        "howto.body": (
            "<b>这不是官方排名。</b>得分是加权后的基准分，归一化到 0–100。"
            "模型未参加过的基准会被跳过，剩余权重重新归一化——"
            "因此 <b>Cov.</b> 告诉你这套权重里真正有数据的比例。"
            "覆盖率 0.4 的得分依据的基准比 1.0 的少。"
            "性价比 = 得分 ÷ 混合价格（输入:输出 = 3:1）；"
            "未公布价格的模型没有性价比得分。"
        ),

        "meta.title": "数据",
        "meta.aa": "Artificial Analysis 数据 API",
        "meta.fetched": "拉取 {n} 个模型",
        "meta.rankable": "可排名 {n} 个",
        "meta.localgateway": "本地网关",
        "meta.byline": "评分与呈现由 scipick 完成。",
        "meta.license": "MIT 许可",
        "bench.title": "基准说明",
        "bench.desc": (
            "这里说明各加权指标究竟衡量什么，以及榜单中有多少模型报告了该指标。"
            "覆盖率很重要：全体模型都有的基准，比只有三分之一模型有的基准更有说服力。"
        ),
        "bench.metric": "基准",
        "bench.measures": "衡量内容",
        "bench.scale": "量纲",
        "bench.coverage": "覆盖率",
        "bench.scicode": "科学代码生成——求解研究级编程问题。",
        "bench.hle": "Humanity's Last Exam——跨学科的专家级推理。",
        "bench.index": "综合多项评测的推理指数。",
        "bench.lcr": "对长输入（如整个代码仓库）的检索与推理能力。",
        "bench.terminal": "真实 shell 中的智能体执行——多步命令行任务。",
        "method.note": "权重是相对的，并按模型逐一重归一化，因此缺失的基准不会被当作 0 分。",
        "podium.by.score": "加权得分前三",
        "podium.by.value": "每美元能力前三",
        "podium.leader.value": "本视图最值",
        "podium.leader.score": "本视图最高分",
        "podium.per_dollar": "分/美元",

        "frontier.title": "得分与价格",
        "frontier.desc": (
            "本视图下所有已公布价格的模型。折线是效率前沿：在每个价格点上"
            "能达到的最好得分。落在折线上的模型，不会被别的模型在得分和价格上同时超越。"
        ),
        "frontier.axis.price": "混合价格，美元/百万 token（对数刻度）",
        "frontier.axis.score": "加权得分",
        "frontier.legend.frontier": "效率前沿",
        "frontier.legend.other": "其他模型",
        "frontier.legend.top": "前三名",
        "frontier.nopriced": "本视图没有公布价格的模型。",
        "meta.source_code": "源码",
        "meta.selection": (
            "自 {aa} 个模型中筛选：每个产品线仅保留最新一代，仅收录主流厂商"
            "（已排除 {superseded} 条旧代次、{vendors} 条非主流厂商）。"
        ),

        "preset.capability.label": "综合能力",
        "preset.value.label": "性价比",
        "preset.coding.label": "代码",
        "preset.longcontext.label": "长上下文",
        "preset.capability.desc": "绝对能力，不考虑价格。",
        "preset.value.desc": "在接近前沿的模型中比每美元能力。",
        "preset.coding.desc": "偏重代码生成与终端执行能力。",
        "preset.longcontext.desc": "面向整仓库或长文档推理。",
    },
}


def strings_for(lang: str) -> dict[str, str]:
    """Strings for one language, falling back to the default."""
    return STRINGS.get(lang) or STRINGS[DEFAULT_LANG]


def js_payload() -> str:
    """The translation table as JSON, for the in-page language switch."""
    import json

    return json.dumps(STRINGS, ensure_ascii=False)
