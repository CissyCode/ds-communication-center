"""Shared visual language for DS COMMUNICATION CENTER.

Design intent: enterprise internal operations console — dense, flat, quiet.
No card-grid landing-page patterns, no gradients, no decorative icons/animation.
KPIs render as a single bordered stat strip; lists render as tables, not cards.
"""
from __future__ import annotations

import streamlit as st

BADGE_TONES = {
    "green": ("#E3EFE7", "#2A6E49"),
    "amber": ("#F3E9D6", "#8A5A11"),
    "red": ("#F3E1E0", "#9A3A32"),
    "slate": ("#E9EBEF", "#495568"),
    "blue": ("#DFE6F3", "#31518C"),
    "purple": ("#E9E3F1", "#5B3A8C"),
}

# Single shared status→tone mapping. Different modules track genuinely
# different status vocabularies (a project's lifecycle isn't a reporter's
# activity state), so values are NOT collapsed into one enum — but every
# status string used anywhere in the app is registered here once, instead of
# each view keeping its own copy. Spacing is normalized consistently
# ("진행 중", "기획 중", "준비 중" — never "진행중"/"기획중"/"준비중").
STATUS_TONE = {
    "완료": "green",
    "진행 중": "amber",
    "기획 중": "slate",
    "준비 중": "amber",
    "확정": "green",
    "활성": "green",
    "비활성": "slate",
    "배포 예정": "amber",
    "배포 완료": "green",
    "작성": "slate",
    "검토 중": "amber",
}

SENTIMENT_TONE = {"긍정": "green", "중립": "slate", "부정": "red"}
SECURITY_TONE = {"공개가능": "green", "내부": "amber"}
SEVERITY_TONE = {"HIGH": "red", "MEDIUM": "amber"}

_KR_WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]


def format_kr_date(d) -> str:
    """2026-09-07 -> '9.7(월)'. Display-only — never stored."""
    return f"{d.month}.{d.day}({_KR_WEEKDAY[d.weekday()]})"


def format_date_range(start, end) -> str:
    """Display-only date range, e.g. '9.7(월) ~ 9.9(수)' or '9.2(수)' for a single day."""
    if start == end:
        return format_kr_date(start)
    return f"{format_kr_date(start)} ~ {format_kr_date(end)}"


def format_period(start, end) -> str:
    """Display-only ISO period, e.g. '2026-07-01 ~ 2026-09-30'."""
    return f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"


def inject_base_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] { font-family: 'Noto Sans KR', -apple-system, 'Segoe UI', sans-serif; }

        .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1280px; }

        .dcc-appname {
            font-size: 1.05rem; font-weight: 700; letter-spacing: -0.01em; color: #16202F;
            padding-bottom: .1rem;
        }
        .dcc-appname .unit { color: #8993A4; font-weight: 500; }

        .dcc-pagetitle {
            font-size: 1.3rem; font-weight: 700; color: #16202F; margin: 0;
        }
        .dcc-pagesub { color: #6B7688; font-size: .86rem; margin: .15rem 0 .9rem 0; }
        .dcc-hr { border: none; border-top: 1px solid #E3E6EC; margin: .5rem 0 1.1rem 0; }

        .dcc-section-title {
            font-size: .82rem; font-weight: 700; color: #495568; letter-spacing: .01em;
            margin: 1.1rem 0 .4rem 0; text-transform: none;
        }

        /* KPI stat strip: one bordered row, cells separated by hairlines — not N cards */
        .dcc-stats {
            display: flex; border: 1px solid #E3E6EC; border-radius: 6px; background: #FFFFFF;
            margin-bottom: 1rem; overflow: hidden;
        }
        .dcc-stat {
            flex: 1; padding: .65rem 1rem; border-right: 1px solid #E3E6EC;
        }
        .dcc-stat:last-child { border-right: none; }
        .dcc-stat .label { font-size: .74rem; color: #7A8496; font-weight: 500; margin-bottom: .15rem; }
        .dcc-stat .value { font-size: 1.28rem; font-weight: 700; color: #16202F; line-height: 1.2; }
        .dcc-stat .value .unit { font-size: .78rem; font-weight: 500; color: #7A8496; margin-left: .1rem; }

        .dcc-panel {
            border: 1px solid #E3E6EC; border-radius: 6px; background: #FFFFFF;
            padding: .9rem 1rem; margin-bottom: .9rem;
        }
        .dcc-panel-title { font-size: .88rem; font-weight: 700; color: #16202F; margin-bottom: .5rem; }

        .dcc-badge {
            display: inline-block; padding: .07rem .5rem; border-radius: 4px;
            font-size: .72rem; font-weight: 600; white-space: nowrap;
        }
        .dcc-tag {
            display: inline-block; padding: .04rem .45rem; margin: .05rem .2rem .05rem 0;
            border-radius: 4px; font-size: .7rem; background: #EEF0F4; color: #5B6577;
        }

        .dcc-row {
            display: flex; justify-content: space-between; align-items: center; gap: .8rem;
            padding: .42rem 0; border-bottom: 1px solid #EEF0F4; font-size: .86rem;
        }
        .dcc-row:last-child { border-bottom: none; }
        .dcc-row .main { color: #26303F; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .dcc-muted { color: #8A94A6; font-size: .78rem; white-space: nowrap; }
        .dcc-pin-dot { color: #9A3A32; margin-right: .3rem; }

        .dcc-cal-cell {
            border: 1px solid #EDEFF4; border-radius: 4px; min-height: 84px;
            padding: .3rem .35rem; vertical-align: top; background: #FFFFFF;
        }
        .dcc-cal-cell.empty { background: transparent; border: none; }
        .dcc-cal-cell .d { font-size: .72rem; color: #93A0B4; font-weight: 600; }
        .dcc-cal-cell .d.today { color: #31518C; }
        .dcc-cal-evt {
            font-size: .64rem; margin-top: .18rem; padding: .04rem .28rem;
            border-radius: 3px; background: #EEF1F7; color: #31518C; font-weight: 600;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }

        div[data-testid="stTabs"] button[role="tab"] { font-size: .86rem; padding: .4rem .9rem; }

        section[data-testid="stSidebar"] { background: #182233; }
        section[data-testid="stSidebar"] * { color: #C7CEDB !important; }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #7E8AA3 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_name(unit: str = "DS COMMUNICATION CENTER") -> None:
    st.markdown(f'<div class="dcc-appname">{unit}</div>', unsafe_allow_html=True)


def page_title(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<p class="dcc-pagetitle">{title}</p>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="dcc-pagesub">{subtitle}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="margin-bottom:.7rem;"></div>', unsafe_allow_html=True)


def section_title(text: str) -> None:
    st.markdown(f'<div class="dcc-section-title">{text}</div>', unsafe_allow_html=True)


def stat_strip(items: list[tuple[str, str, str | None]]) -> None:
    """items: list of (label, value, unit_or_none)."""
    cells = "".join(
        f'<div class="dcc-stat"><div class="label">{label}</div>'
        f'<div class="value">{value}{f" <span class=\'unit\'>{unit}</span>" if unit else ""}</div></div>'
        for label, value, unit in items
    )
    st.markdown(f'<div class="dcc-stats">{cells}</div>', unsafe_allow_html=True)


def badge(text: str, tone: str = "slate") -> str:
    bg, fg = BADGE_TONES.get(tone, BADGE_TONES["slate"])
    return f'<span class="dcc-badge" style="background:{bg};color:{fg};">{text}</span>'


def tag(text: str) -> str:
    return f'<span class="dcc-tag">#{text}</span>'


def tags_html(values: list[str]) -> str:
    return "".join(tag(v) for v in values)


def panel_open(title: str | None = None) -> None:
    inner = f'<div class="dcc-panel-title">{title}</div>' if title else ""
    st.markdown(f'<div class="dcc-panel">{inner}', unsafe_allow_html=True)


def panel_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def list_row(main: str, meta: str = "") -> None:
    st.markdown(
        f'<div class="dcc-row"><span class="main">{main}</span><span class="dcc-muted">{meta}</span></div>',
        unsafe_allow_html=True,
    )
