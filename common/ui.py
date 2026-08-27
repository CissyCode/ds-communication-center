"""Dashboard composition kit for DS COMMUNICATION CENTER.

`common/style.py` owns the app-wide visual language (type scale, badges, single
list rows). This module owns the *dashboard* layer built on top of it: a
12-column board grid, KPI tiles, an attention rail, agenda / queue / feed lists
and micro-charts.

Two decisions make the kit cheap to work with and cheap to run:

1. Every component is a pure function that returns an HTML string, and a whole
   screen is composed in memory and handed to Streamlit in ONE `st.markdown`
   call. That is not only fewer DOM writes — it is the only way a panel border
   can actually wrap its rows. The `panel_open()`/`panel_close()` pattern
   cannot: Streamlit closes unbalanced tags at the end of each markdown block,
   so anything rendered "between" the two calls lands outside the box.
2. Navigation happens through anchors (`nav.href`), not buttons. A button costs
   a full server rerun to reach a page a link reaches directly, and an anchor
   lets an entire row — not just a trailing control — be the click target.

Layout uses CSS grid rather than `st.columns` so that column spans, gaps and
the responsive collapse are one stylesheet instead of per-screen ratio lists.
"""
from __future__ import annotations

import html
from typing import Sequence

import streamlit as st

# Four semantic tones + one neutral. Deliberately not a palette: a colour on
# this board always means a state (needs action / watch / healthy / idle), so
# adding a sixth tone would mean inventing a sixth state.
TONES = {
    "crit": "#C0453B",
    "warn": "#B0761A",
    "ok": "#2C7A57",
    "info": "#2F6FED",
    "idle": "#8A94A6",
}

TONE_BG = {
    "crit": "#F8E9E7",
    "warn": "#F7EEDC",
    "ok": "#E6F1EA",
    "info": "#E6EDFB",
    "idle": "#EDEFF3",
}


def _c(tone: str) -> str:
    return TONES.get(tone, TONES["idle"])


def _e(value) -> str:
    return html.escape("" if value is None else str(value))


def _attrs(href: str | None) -> tuple[str, str]:
    """Render the same row markup as a link or a plain div depending on whether
    the caller has somewhere to send the user."""
    if href:
        return "a", f' href="{_e(href)}" target="_self"'
    return "div", ""


# ---------------------------------------------------------------- micro-charts

def sparkline(values: Sequence[float], tone: str = "info", height: int = 30) -> str:
    """Trend shape only — no axes, no labels. Used where the number already
    carries the value and the reader only needs 'rising or falling'."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return f'<div class="dcc-spark-empty" style="height:{height}px"></div>'
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = 100 / (len(vals) - 1)
    pts = " ".join(f"{i * step:.2f},{28 - (v - lo) / span * 26:.2f}" for i, v in enumerate(vals))
    last_x, last_y = pts.split(" ")[-1].split(",")
    col = _c(tone)
    return (
        f'<svg class="dcc-spark" viewBox="0 0 100 30" preserveAspectRatio="none" '
        f'style="height:{height}px" aria-hidden="true">'
        f'<polygon points="0,30 {pts} 100,30" fill="{col}" opacity=".10"/>'
        f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.4" '
        f'vector-effect="non-scaling-stroke" stroke-linejoin="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="1.8" fill="{col}" vector-effect="non-scaling-stroke"/>'
        f"</svg>"
    )


def microbars(values: Sequence[float], tone: str = "info", height: int = 26) -> str:
    """Counts over time. Bars, not a line: a line between "2 inquiries on Monday"
    and "0 on Tuesday" draws a slope through values that never existed, and at
    prototype volumes that slope is all the reader sees."""
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return f'<div class="dcc-spark-empty" style="height:{height}px"></div>'
    hi = max(vals) or 1.0
    n = len(vals)
    slot = 100 / n
    col = _c(tone)
    bars = []
    for i, v in enumerate(vals):
        h = max(v / hi * 24, 0.8)  # zero days keep a baseline tick, not a gap
        bars.append(
            f'<rect x="{i * slot + slot * .15:.2f}" y="{27 - h:.2f}" '
            f'width="{slot * .7:.2f}" height="{h:.2f}" fill="{col}" '
            f'opacity="{1 if v else .35:g}" rx="0.4"/>'
        )
    return (
        f'<svg class="dcc-spark" viewBox="0 0 100 30" preserveAspectRatio="none" '
        f'style="height:{height}px" aria-hidden="true">{"".join(bars)}'
        f'<line x1="0" y1="27.6" x2="100" y2="27.6" stroke="{col}" stroke-width="1" '
        f'opacity=".25" vector-effect="non-scaling-stroke"/></svg>'
    )


def meter(pct: float, tone: str = "info") -> str:
    """Single-value progress rail: share of a whole, or completion of a plan."""
    p = max(0.0, min(100.0, float(pct)))
    return (
        f'<div class="dcc-meter"><span style="width:{p:.1f}%;background:{_c(tone)}"></span></div>'
    )


def stackbar(segments: Sequence[tuple[str, float, str]]) -> str:
    """Composition of one total, e.g. 긍정/중립/부정. segments: (label, value, tone)."""
    total = sum(max(0.0, float(v)) for _, v, _ in segments) or 1.0
    bars = "".join(
        f'<span style="width:{max(0.0, float(v)) / total * 100:.2f}%;background:{_c(t)}" '
        f'title="{_e(lab)} {v:g}"></span>'
        for lab, v, t in segments
    )
    legend = "".join(
        f'<span class="dcc-lg"><i style="background:{_c(t)}"></i>{_e(lab)} '
        f'<b>{v:g}</b></span>'
        for lab, v, t in segments
    )
    return f'<div class="dcc-stack">{bars}</div><div class="dcc-lgs">{legend}</div>'


# ------------------------------------------------------------------ page frame

def context_bar(title: str, subtitle: str = "", meta: Sequence[tuple[str, str]] = ()) -> str:
    """Screen header carrying the reading context (as-of date, owner, scope) —
    a dashboard number is meaningless without knowing when it was true."""
    metas = "".join(
        f'<div class="m"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div></div>'
        for k, v in meta
    )
    sub = f'<div class="sub">{_e(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="dcc-ctx"><div><div class="h1">{_e(title)}</div>{sub}</div>'
        f'<div class="meta">{metas}</div></div>'
    )


def kpi_row(items: Sequence[dict]) -> str:
    """One bordered strip of action counts.

    item keys: label, value, unit, tone, delta (str), hint, href, spark (list).
    Every tile answers "how many things are waiting for me", never a vanity
    total — so a tile is always safe to click through to the work itself.
    """
    cells = []
    for it in items:
        tone = it.get("tone", "idle")
        tag, attr = _attrs(it.get("href"))
        unit = f'<span class="u">{_e(it["unit"])}</span>' if it.get("unit") else ""
        delta = it.get("delta")
        delta_html = (
            f'<span class="d {it.get("delta_tone", "idle")}">{_e(delta)}</span>' if delta else ""
        )
        if it.get("bars"):
            spark = microbars(it["bars"], tone, height=24)
        elif it.get("spark"):
            spark = sparkline(it["spark"], tone, height=22)
        else:
            spark = ""
        hint = f'<div class="h">{_e(it["hint"])}</div>' if it.get("hint") else ""
        cells.append(
            f'<{tag}{attr} class="dcc-kpi" style="--t:{_c(tone)}">'
            f'<div class="l">{_e(it["label"])}</div>'
            f'<div class="v">{_e(it["value"])}{unit}{delta_html}</div>'
            f"{hint}{spark}</{tag}>"
        )
    return f'<div class="dcc-kpis">{"".join(cells)}</div>'


def alerts(items: Sequence[dict], empty: str = "지금 즉시 확인할 항목이 없습니다.") -> str:
    """The 3-second lane: only items that need a decision today.

    item keys: tone, chip, title, meta, href. Capped by the caller — an
    attention lane that can grow without bound stops being one.
    """
    if not items:
        return f'<div class="dcc-alerts-empty">{_e(empty)}</div>'
    cards = []
    for it in items:
        tone = it.get("tone", "warn")
        tag, attr = _attrs(it.get("href"))
        cards.append(
            f'<{tag}{attr} class="dcc-al" style="--t:{_c(tone)};--tb:{TONE_BG.get(tone, "#EDEFF3")}">'
            f'<div class="top"><span class="chip">{_e(it.get("chip", ""))}</span>'
            f'<span class="meta">{_e(it.get("meta", ""))}</span></div>'
            f'<div class="ttl">{_e(it["title"])}</div></{tag}>'
        )
    return f'<div class="dcc-alerts">{"".join(cards)}</div>'


def panel(title: str, body: str, span: int | None = None,
          action: tuple[str, str] | None = None,
          note: str | None = None, subtitle: str | None = None) -> str:
    """A board tile: header (+ optional deep link), body, optional footnote.

    `span` only applies when the panel sits directly in the grid; inside a
    `column()` the wrapper owns the width.
    """
    sub = f'<span class="s">{_e(subtitle)}</span>' if subtitle else ""
    act = ""
    if action:
        label, href = action
        act = f'<a class="act" href="{_e(href)}" target="_self">{_e(label)} →</a>'
    foot = f'<div class="dcc-pn-f">{_e(note)}</div>' if note else ""
    width = f" s{span}" if span else ""
    return (
        f'<section class="dcc-pn{width}">'
        f'<header class="dcc-pn-h"><div class="t">{_e(title)}{sub}</div>{act}</header>'
        f'<div class="dcc-pn-b">{body}</div>{foot}</section>'
    )


def column(span: int, *panels: str) -> str:
    """A stack of panels occupying one board column.

    Placing panels directly in the grid ties every tile in a row to the tallest
    one, which leaves dead space under the short ones. Stacking them per column
    lets each side flow at its own height — the difference between a board and
    a set of boxes.
    """
    return f'<div class="dcc-col s{span}">{"".join(panels)}</div>'


def board(*blocks: str) -> str:
    return f'<div class="dcc-board">{"".join(blocks)}</div>'


def render(*blocks: str) -> None:
    """The single write. Everything above is a string until this call."""
    st.markdown("".join(blocks), unsafe_allow_html=True)


# ------------------------------------------------------------------ list bodies

def empty(text: str) -> str:
    return f'<div class="dcc-empty">{_e(text)}</div>'


def rows(items: Sequence[dict], empty_text: str = "표시할 항목이 없습니다.") -> str:
    """Queue / list body. item keys: main, meta, chip, chip_tone, href, sub."""
    if not items:
        return empty(empty_text)
    out = []
    for it in items:
        tag, attr = _attrs(it.get("href"))
        chip = ""
        if it.get("chip"):
            tone = it.get("chip_tone", "idle")
            chip = (
                f'<span class="dcc-chip" style="color:{_c(tone)};'
                f'background:{TONE_BG.get(tone, "#EDEFF3")}">{_e(it["chip"])}</span>'
            )
        sub = f'<div class="sub">{_e(it["sub"])}</div>' if it.get("sub") else ""
        meta = f'<span class="meta">{_e(it["meta"])}</span>' if it.get("meta") else ""
        out.append(
            f'<{tag}{attr} class="dcc-lr">{chip}'
            f'<div class="body"><div class="main">{_e(it["main"])}</div>{sub}</div>'
            f"{meta}</{tag}>"
        )
    return "".join(out)


def stat_rows(items: Sequence[dict]) -> str:
    """Module-health body: label, value, and a rail showing it against a target.
    item keys: label, value, pct, tone, href."""
    out = []
    for it in items:
        tag, attr = _attrs(it.get("href"))
        tone = it.get("tone", "info")
        rail = meter(it["pct"], tone) if it.get("pct") is not None else ""
        out.append(
            f'<{tag}{attr} class="dcc-sr">'
            f'<div class="hd"><span class="l">{_e(it["label"])}</span>'
            f'<span class="v">{_e(it["value"])}</span></div>{rail}</{tag}>'
        )
    return "".join(out)


def agenda(groups: Sequence[tuple[str, str, Sequence[dict]]],
           empty_text: str = "예정된 일정이 없습니다.") -> str:
    """Day-grouped schedule. groups: (day_label, day_tone, items);
    item keys: time, category, title, meta, href."""
    groups = [g for g in groups if g[2]]
    if not groups:
        return empty(empty_text)
    out = []
    for label, tone, items in groups:
        out.append(
            f'<div class="dcc-ag-d"><span class="lab" style="color:{_c(tone)}">{_e(label)}</span>'
            f'<span class="ln"></span><span class="n">{len(items)}건</span></div>'
        )
        for it in items:
            tag, attr = _attrs(it.get("href"))
            meta = f'<span class="meta">{_e(it["meta"])}</span>' if it.get("meta") else ""
            out.append(
                f'<{tag}{attr} class="dcc-ag-i">'
                f'<span class="tm">{_e(it.get("time") or "-")}</span>'
                f'<span class="cat">{_e(it.get("category", ""))}</span>'
                f'<span class="ttl">{_e(it["title"])}</span>{meta}</{tag}>'
            )
    return "".join(out)


def feed(items: Sequence[dict], empty_text: str = "최근 업데이트가 없습니다.") -> str:
    """Cross-module activity stream. item keys: date, module, text, href."""
    if not items:
        return empty(empty_text)
    out = []
    for it in items:
        tag, attr = _attrs(it.get("href"))
        out.append(
            f'<{tag}{attr} class="dcc-fd"><span class="dt">{_e(it["date"])}</span>'
            f'<span class="md">{_e(it["module"])}</span>'
            f'<span class="tx">{_e(it["text"])}</span></{tag}>'
        )
    return "".join(out)


# ------------------------------------------------------------------------- CSS

_CSS = """
<style>
:root{
  --dcc-line:#E3E6EC; --dcc-line-soft:#EDEFF4; --dcc-surface:#FFFFFF;
  --dcc-ink:#16202F; --dcc-ink2:#49546A; --dcc-ink3:#7A8496;
  --dcc-hover:#F6F8FC; --dcc-accent:#2F6FED;
}

/* A 12-column board needs more than the 1280px reading width the text pages
   use, or every tile collapses to its mobile breakpoint on a laptop. */
.block-container{max-width:1460px;}

.dcc-ctx{display:flex;align-items:flex-end;justify-content:space-between;gap:1.5rem;
  padding:0 0 .6rem;border-bottom:1px solid var(--dcc-line);margin:0 0 .9rem;flex-wrap:wrap;}
.dcc-ctx .h1{font-size:1.34rem;font-weight:800;letter-spacing:-.02em;color:var(--dcc-ink);line-height:1.2;}
.dcc-ctx .sub{font-size:.82rem;color:var(--dcc-ink3);margin-top:.2rem;}
.dcc-ctx .meta{display:flex;gap:1.4rem;}
.dcc-ctx .meta .k{font-size:.68rem;color:var(--dcc-ink3);font-weight:500;}
.dcc-ctx .meta .v{font-size:.84rem;color:var(--dcc-ink);font-weight:700;font-variant-numeric:tabular-nums;}

.dcc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  border:1px solid var(--dcc-line);border-radius:8px;background:var(--dcc-surface);
  overflow:hidden;margin-bottom:.7rem;}
.dcc-kpi{display:block;padding:.6rem .85rem .55rem;text-decoration:none;
  border-right:1px solid var(--dcc-line-soft);border-top:2px solid var(--t);transition:background .12s;}
.dcc-kpi:last-child{border-right:none;}
a.dcc-kpi:hover{background:var(--dcc-hover);}
.dcc-kpi .l{font-size:.72rem;color:var(--dcc-ink3);font-weight:600;margin-bottom:.1rem;}
.dcc-kpi .v{font-size:1.42rem;font-weight:800;color:var(--dcc-ink);line-height:1.15;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums;}
.dcc-kpi .v .u{font-size:.74rem;font-weight:600;color:var(--dcc-ink3);margin-left:.15rem;}
.dcc-kpi .v .d{font-size:.7rem;font-weight:700;margin-left:.35rem;}
.dcc-kpi .v .d.ok{color:#2C7A57;} .dcc-kpi .v .d.crit{color:#C0453B;}
.dcc-kpi .v .d.warn{color:#B0761A;} .dcc-kpi .v .d.idle{color:#8A94A6;}
.dcc-kpi .h{font-size:.68rem;color:var(--dcc-ink3);margin-top:.1rem;}
.dcc-spark{display:block;width:100%;margin-top:.25rem;}
.dcc-spark-empty{width:100%;}

.dcc-alerts{display:grid;grid-template-columns:repeat(auto-fit,minmax(258px,1fr));
  gap:.5rem;margin-bottom:.75rem;}
.dcc-alerts-empty{border:1px dashed var(--dcc-line);border-radius:8px;padding:.55rem .85rem;
  font-size:.78rem;color:var(--dcc-ink3);background:var(--dcc-surface);margin-bottom:.75rem;}
.dcc-al{display:block;text-decoration:none;background:var(--dcc-surface);
  border:1px solid var(--dcc-line);border-left:3px solid var(--t);border-radius:6px;
  padding:.45rem .7rem .5rem;transition:background .12s;}
a.dcc-al:hover{background:var(--tb);}
.dcc-al .top{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.15rem;}
.dcc-al .chip{font-size:.66rem;font-weight:800;color:var(--t);letter-spacing:.03em;}
.dcc-al .meta{font-size:.68rem;color:var(--dcc-ink3);white-space:nowrap;}
.dcc-al .ttl{font-size:.82rem;font-weight:600;color:var(--dcc-ink);line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}

.dcc-board{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:.7rem;align-items:start;}
.dcc-board>*{min-width:0;}
.dcc-board>.s3{grid-column:span 3;} .dcc-board>.s4{grid-column:span 4;}
.dcc-board>.s5{grid-column:span 5;} .dcc-board>.s6{grid-column:span 6;}
.dcc-board>.s7{grid-column:span 7;} .dcc-board>.s8{grid-column:span 8;}
.dcc-board>.s9{grid-column:span 9;} .dcc-board>.s12{grid-column:span 12;}
.dcc-col{display:flex;flex-direction:column;gap:.7rem;min-width:0;}
@media (max-width:1180px){
  .dcc-board{grid-template-columns:repeat(6,minmax(0,1fr));}
  .dcc-board>.s3,.dcc-board>.s4,.dcc-board>.s5{grid-column:span 3;}
  .dcc-board>.s6,.dcc-board>.s7,.dcc-board>.s8,
  .dcc-board>.s9,.dcc-board>.s12{grid-column:span 6;}
}
@media (max-width:820px){ .dcc-board{grid-template-columns:1fr;} .dcc-board>*{grid-column:1/-1;} }

.dcc-pn{border:1px solid var(--dcc-line);border-radius:8px;background:var(--dcc-surface);overflow:hidden;}
.dcc-pn-h{display:flex;align-items:baseline;justify-content:space-between;gap:.6rem;
  padding:.55rem .85rem;border-bottom:1px solid var(--dcc-line-soft);background:#FCFDFE;}
.dcc-pn-h .t{font-size:.84rem;font-weight:700;color:var(--dcc-ink);}
.dcc-pn-h .t .s{font-size:.7rem;font-weight:500;color:var(--dcc-ink3);margin-left:.35rem;}
.dcc-pn-h .act{font-size:.71rem;font-weight:700;color:var(--dcc-accent);text-decoration:none;white-space:nowrap;}
.dcc-pn-h .act:hover{text-decoration:underline;}
.dcc-pn-b{padding:.2rem .85rem .45rem;}
.dcc-pn-f{padding:.35rem .85rem .5rem;font-size:.68rem;color:var(--dcc-ink3);
  border-top:1px solid var(--dcc-line-soft);}
.dcc-empty{font-size:.78rem;color:var(--dcc-ink3);padding:.7rem 0;}

/* Full-bleed hover: the row highlights across the panel's own padding, so the
   whole strip reads as one target instead of a floating text box. */
.dcc-lr,.dcc-ag-i,.dcc-fd{text-decoration:none;transition:background .12s;}
a.dcc-lr:hover,a.dcc-ag-i:hover,a.dcc-fd:hover{background:var(--dcc-hover);
  box-shadow:-.85rem 0 0 var(--dcc-hover),.85rem 0 0 var(--dcc-hover);}

.dcc-lr{display:flex;align-items:center;gap:.5rem;padding:.4rem 0;
  border-bottom:1px solid var(--dcc-line-soft);}
.dcc-lr:last-child{border-bottom:none;}
.dcc-lr .body{flex:1;min-width:0;}
.dcc-lr .main{font-size:.83rem;color:#26303F;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.dcc-lr .sub{font-size:.7rem;color:var(--dcc-ink3);margin-top:.05rem;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.dcc-lr .meta{font-size:.72rem;color:var(--dcc-ink3);white-space:nowrap;flex:none;
  font-variant-numeric:tabular-nums;}
.dcc-chip{flex:none;font-size:.66rem;font-weight:800;padding:.08rem .36rem;border-radius:3px;
  letter-spacing:.02em;}

.dcc-sr{display:block;padding:.42rem 0;border-bottom:1px solid var(--dcc-line-soft);text-decoration:none;}
.dcc-sr:last-child{border-bottom:none;}
.dcc-sr .hd{display:flex;justify-content:space-between;align-items:baseline;gap:.5rem;margin-bottom:.28rem;}
.dcc-sr .l{font-size:.78rem;color:var(--dcc-ink2);}
.dcc-sr .v{font-size:.82rem;font-weight:700;color:var(--dcc-ink);font-variant-numeric:tabular-nums;}
.dcc-meter{height:4px;border-radius:2px;background:#EDEFF4;overflow:hidden;}
.dcc-meter>span{display:block;height:100%;border-radius:2px;}

.dcc-ag-d{display:flex;align-items:center;gap:.5rem;margin:.5rem 0 .1rem;}
.dcc-ag-d .lab{font-size:.71rem;font-weight:800;letter-spacing:.01em;}
.dcc-ag-d .ln{flex:1;height:1px;background:var(--dcc-line-soft);}
.dcc-ag-d .n{font-size:.68rem;color:var(--dcc-ink3);}
.dcc-ag-i{display:flex;align-items:center;gap:.5rem;padding:.3rem 0;}
.dcc-ag-i .tm{flex:none;width:2.9rem;font-size:.73rem;color:var(--dcc-ink3);font-variant-numeric:tabular-nums;}
.dcc-ag-i .cat{flex:none;font-size:.68rem;color:var(--dcc-ink3);background:#F0F2F6;
  border-radius:3px;padding:.05rem .34rem;}
.dcc-ag-i .ttl{flex:1;min-width:0;font-size:.83rem;color:#26303F;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.dcc-ag-i .meta{flex:none;font-size:.7rem;color:var(--dcc-ink3);}

.dcc-fd{display:flex;align-items:center;gap:.55rem;padding:.32rem 0;
  border-bottom:1px dashed var(--dcc-line-soft);}
.dcc-fd:last-child{border-bottom:none;}
.dcc-fd .dt{flex:none;font-size:.71rem;color:var(--dcc-ink3);font-variant-numeric:tabular-nums;}
.dcc-fd .md{flex:none;font-size:.66rem;font-weight:700;color:var(--dcc-ink2);
  background:#F0F2F6;border-radius:3px;padding:.05rem .34rem;}
.dcc-fd .tx{flex:1;min-width:0;font-size:.81rem;color:#26303F;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* Streamlit's own markdown stylesheet underlines and recolours every <a>.
   These rows ARE links, but they must read as rows, so the kit takes the
   anchor styling back — the only place !important is used here. */
.dcc-ctx a,.dcc-kpis a,.dcc-alerts a,.dcc-board a{text-decoration:none !important;}
a.dcc-kpi,a.dcc-al,a.dcc-lr,a.dcc-ag-i,a.dcc-fd,a.dcc-sr{color:inherit !important;}
a.dcc-kpi:hover,a.dcc-al:hover,a.dcc-lr:hover,a.dcc-ag-i:hover,a.dcc-fd:hover,
a.dcc-sr:hover{text-decoration:none !important;}
.dcc-pn-h .act{color:var(--dcc-accent) !important;}
.dcc-pn-h .act:hover{text-decoration:underline !important;}

.dcc-stack{display:flex;height:8px;border-radius:4px;overflow:hidden;background:#EDEFF4;margin:.35rem 0 .4rem;}
.dcc-stack>span{display:block;height:100%;}
.dcc-lgs{display:flex;flex-wrap:wrap;gap:.75rem;}
.dcc-lg{font-size:.72rem;color:var(--dcc-ink2);display:inline-flex;align-items:center;gap:.28rem;}
.dcc-lg i{width:8px;height:8px;border-radius:2px;display:inline-block;}
.dcc-lg b{color:var(--dcc-ink);font-variant-numeric:tabular-nums;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
