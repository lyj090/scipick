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
        "card.best": "Best score",
        "card.best.note": "{score} pts",
        "card.value": "Best value",
        "card.value.note": "{eff} pts/$",
        "card.none": "no data",
        "card.noprice": "no published price",
        "card.points": "{score} pts",

        # Panels
        "panel.top": "Top {n}",
        "panel.full": "Full ranking",
        "panel.empty": "No models matched this view.",
        "panel.sorted.score": "Sorted by weighted score.",
        "panel.sorted.eff": "Sorted by ability per dollar.",
        "panel.cov_note": "Cov. is the share of this view's weight that had data.",
        "table.truncated": (
            "Showing the top {shown} of {total} models. "
            "The JSON export contains every model."
        ),
        "panel.floor": (
            "{n} further model(s) have a partial score here but fall below the "
            "{pct} coverage floor and are not ranked. Their data covers too few of "
            "the weighted benchmarks to place them meaningfully against the rest."
        ),

        # Table
        "th.rank": "#",
        "th.model": "Model",
        "th.family": "Family",
        "th.score": "Score",
        "th.price": "$/1M",
        "th.eff": "Eff.",
        "th.cov": "Cov.",
        "row.local": "local",

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
        "meta.sources": "Reachable sources",
        "meta.none": "not configured",
        "meta.byline": "Scoring and presentation by scipick.",
        "meta.license": "MIT licensed",
        "meta.source_code": "Source",
        "meta.selection": (
            "Selected from {aa} models: latest generation per product line, "
            "mainstream vendors only ({superseded} superseded and {vendors} "
            "non-allowlisted rows excluded)."
        ),

        # Preset descriptions (built-in presets only; custom presets from the
        # config file are shown as written by their author).
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
        "card.best": "最高分",
        "card.best.note": "{score} 分",
        "card.value": "最佳性价比",
        "card.value.note": "{eff} 分/美元",
        "card.none": "无数据",
        "card.noprice": "未公布价格",
        "card.points": "{score} 分",

        "panel.top": "前 {n} 名",
        "panel.full": "完整排名",
        "panel.empty": "该视图下没有符合条件的模型。",
        "panel.sorted.score": "按加权得分排序。",
        "panel.sorted.eff": "按每美元能力排序。",
        "panel.cov_note": "Cov. 表示该视图权重中真正有数据的比例。",
        "table.truncated": "共 {total} 个模型，此处显示前 {shown} 名。JSON 导出包含全部模型。",
        "panel.floor": (
            "另有 {n} 个模型在该视图下有部分得分，但低于 {pct} 的覆盖率下限，"
            "未参与排名。它们的数据覆盖的加权基准过少，与其他模型不具可比性。"
        ),

        "th.rank": "#",
        "th.model": "模型",
        "th.family": "家族",
        "th.score": "得分",
        "th.price": "$/1M",
        "th.eff": "效率",
        "th.cov": "覆盖",
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
        "meta.sources": "可达来源",
        "meta.none": "未配置",
        "meta.byline": "评分与呈现由 scipick 完成。",
        "meta.license": "MIT 许可",
        "meta.source_code": "源码",
        "meta.selection": (
            "自 {aa} 个模型中筛选：每个产品线仅保留最新一代，仅收录主流厂商"
            "（已排除 {superseded} 条旧代次、{vendors} 条非主流厂商）。"
        ),

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
