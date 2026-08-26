from __future__ import annotations

import altair as alt
import streamlit as st

from common import data as D
from common import style as S


def _overview():
    content = D.load_new_media_content()
    channels = D.load_new_media_channels()
    series = D.load_new_media_series()

    S.stat_strip([
        ("등록 콘텐츠", f"{len(content)}", "건"),
        ("운영 채널", f"{len(channels)}", "개"),
        ("총 팔로워", f"{channels['followers'].sum():,}", "명"),
        ("평균 참여율", f"{content['engagement_rate'].mean():.1f}", "%"),
        ("진행중 시리즈", f"{(series['status'] == '진행 중').sum()}", "건"),
    ])

    left, right = st.columns(2)
    with left:
        S.section_title("최근 콘텐츠")
        show = content.head(6).copy()
        show["date"] = show["date"].dt.date
        st.dataframe(
            show[["date", "title", "format", "channel", "views"]].rename(
                columns={"date": "게시일", "title": "제목", "format": "포맷", "channel": "채널", "views": "조회수"}
            ),
            hide_index=True, use_container_width=True, height=246,
        )
    with right:
        S.section_title("채널 현황")
        show = channels.copy()
        show["last_post_date"] = show["last_post_date"].dt.date
        st.dataframe(
            show[["channel_name", "platform", "followers", "last_post_date"]].rename(
                columns={"channel_name": "채널명", "platform": "플랫폼", "followers": "팔로워", "last_post_date": "최근 게시일"}
            ),
            hide_index=True, use_container_width=True, height=246,
        )


def _content():
    df = D.load_new_media_content()

    f1, f2, f3 = st.columns([1, 1, 1.4])
    with f1:
        fmt_sel = st.multiselect("포맷", sorted(df["format"].unique()), key="nc_fmt")
    with f2:
        ch_sel = st.multiselect("채널", sorted(df["channel"].unique()), key="nc_ch")
    with f3:
        query = st.text_input("검색 (제목/설명)", "", key="nc_q")

    filtered = df.copy()
    if fmt_sel:
        filtered = filtered[filtered["format"].isin(fmt_sel)]
    if ch_sel:
        filtered = filtered[filtered["channel"].isin(ch_sel)]
    if query:
        q = query.strip()
        filtered = filtered[
            filtered["title"].str.contains(q, case=False, na=False)
            | filtered["summary"].str.contains(q, case=False, na=False)
        ]

    st.caption(f"{len(filtered)}건 표시 중 (전체 {len(df)}건) · 행을 클릭하면 상세 설명을 볼 수 있습니다.")

    show = filtered.copy()
    show["date"] = show["date"].dt.date
    event = st.dataframe(
        show[["date", "title", "format", "channel", "views", "engagement_rate", "owner"]].rename(
            columns={"date": "게시일", "title": "제목", "format": "포맷", "channel": "채널",
                     "views": "조회수", "engagement_rate": "참여율(%)", "owner": "담당자"}
        ),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = filtered.iloc[event.selection.rows[0]]["content_id"]
        r = df[df["content_id"] == sel_id].iloc[0]
        S.panel_open(r["title"])
        st.markdown(
            f"{S.badge(r['format'], 'blue')} {S.badge(r['channel'], 'slate')} "
            f"<span class='dcc-muted'>{r['owner']} · {r['date'].date()} · 조회수 {r['views']:,} · 참여율 {r['engagement_rate']}%</span>",
            unsafe_allow_html=True,
        )
        st.markdown(r["summary"])
        S.panel_close()


def _channels():
    df = D.load_new_media_channels()
    content = D.load_new_media_content()

    show = df.copy()
    show["last_post_date"] = show["last_post_date"].dt.date
    event = st.dataframe(
        show[["channel_name", "platform", "followers", "last_post_date", "owner"]].rename(columns={
            "channel_name": "채널명", "platform": "플랫폼", "followers": "팔로워",
            "last_post_date": "최근 게시일", "owner": "운영 담당자",
        }),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = df.iloc[event.selection.rows[0]]["channel_id"]
        r = df[df["channel_id"] == sel_id].iloc[0]
        S.panel_open(f"{r['channel_name']} · 관련 최근 콘텐츠")
        related = content[content["channel"] == r["channel_name"]].sort_values("date", ascending=False).head(5)
        if related.empty:
            st.caption("연결된 콘텐츠가 없습니다.")
        for _, c in related.iterrows():
            st.markdown(f"**{c['date'].date()}** · {c['title']} · 조회수 {c['views']:,}")
        S.panel_close()


def _series():
    df = D.load_new_media_series()
    event = st.dataframe(
        df[["series_name", "topic", "episode", "status", "owner"]].rename(columns={
            "series_name": "시리즈명", "topic": "주제", "episode": "회차",
            "status": "진행상태", "owner": "담당자",
        }),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = df.iloc[event.selection.rows[0]]["series_id"]
        r = df[df["series_id"] == sel_id].iloc[0]
        S.panel_open(r["series_name"])
        st.markdown(
            f"{S.badge(r['status'], S.STATUS_TONE.get(r['status'], 'slate'))} "
            f"<span class='dcc-muted'>담당 {r['owner']} · {r['episode']}화</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"주제: {r['topic']}")
        S.panel_close()


def _analytics():
    content = D.load_new_media_content()
    channels = D.load_new_media_channels()

    c1, c2 = st.columns(2)
    with c1:
        S.section_title("채널별 팔로워")
        chart = alt.Chart(channels).mark_bar(color="#31518C").encode(
            x=alt.X("followers:Q", title="팔로워"), y=alt.Y("channel_name:N", sort="-x", title=None)
        ).properties(height=240)
        st.altair_chart(chart, use_container_width=True)
    with c2:
        S.section_title("포맷별 평균 참여율")
        by_fmt = content.groupby("format", as_index=False)["engagement_rate"].mean()
        chart = alt.Chart(by_fmt).mark_bar(color="#8A94A6").encode(
            x=alt.X("engagement_rate:Q", title="평균 참여율(%)"), y=alt.Y("format:N", sort="-x", title=None)
        ).properties(height=240)
        st.altair_chart(chart, use_container_width=True)

    S.section_title("일자별 조회수 추이")
    trend = content.sort_values("date")
    chart = alt.Chart(trend).mark_line(point=True, color="#31518C").encode(
        x=alt.X("date:T", title=None), y=alt.Y("views:Q", title="조회수"),
        tooltip=["date:T", "title", "views"],
    ).properties(height=240)
    st.altair_chart(chart, use_container_width=True)


def render():
    S.page_title("NEW MEDIA", "SNS·오운드 채널·시리즈 기획 등 뉴미디어 커뮤니케이션 영역입니다.")
    tabs = st.tabs(["Overview", "콘텐츠", "채널", "시리즈 / 기획", "New Media Analytics"])
    with tabs[0]:
        _overview()
    with tabs[1]:
        _content()
    with tabs[2]:
        _channels()
    with tabs[3]:
        _series()
    with tabs[4]:
        _analytics()
