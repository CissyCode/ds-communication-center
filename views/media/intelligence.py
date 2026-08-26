from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from common import data as D
from common import style as S

SENTIMENT_COLOR = {"긍정": "#2A6E49", "중립": "#7A8496", "부정": "#9A3A32"}


def render():
    S.page_title("MEDIA · Media Intelligence", "언론 환경 전체 동향을 분석합니다.")
    st.caption("여기는 운영 화면이 아니라 언론 환경 전체를 보는 분석 화면입니다 (INSIGHTS와 달리 MEDIA 내부 데이터만 다룹니다).")

    df = D.load_media_monitoring()
    press = D.load_press_history()
    all_tags = [t for row in df["tags_list"] for t in row]

    c1, c2 = st.columns([1, 1.4])
    with c1:
        S.section_title("감성 분포")
        sent_counts = df["sentiment"].value_counts().reset_index()
        sent_counts.columns = ["sentiment", "count"]
        chart = (
            alt.Chart(sent_counts).mark_arc(innerRadius=50).encode(
                theta="count",
                color=alt.Color("sentiment", scale=alt.Scale(domain=list(SENTIMENT_COLOR), range=list(SENTIMENT_COLOR.values())), legend=alt.Legend(title=None)),
                tooltip=["sentiment", "count"],
            ).properties(height=220)
        )
        st.altair_chart(chart, use_container_width=True)
    with c2:
        S.section_title("일자별 보도 추이")
        trend = df.groupby([df["date"].dt.date, "sentiment"]).size().reset_index(name="count")
        trend.columns = ["date", "sentiment", "count"]
        chart = (
            alt.Chart(trend).mark_bar().encode(
                x=alt.X("date:T", title=None), y=alt.Y("count:Q", title="건수"),
                color=alt.Color("sentiment", scale=alt.Scale(domain=list(SENTIMENT_COLOR), range=list(SENTIMENT_COLOR.values())), legend=alt.Legend(title=None)),
                tooltip=["date:T", "sentiment", "count"],
            ).properties(height=220)
        )
        st.altair_chart(chart, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        S.section_title("매체별 보도 건수")
        mc = df["media"].value_counts().reset_index()
        mc.columns = ["media", "count"]
        chart = alt.Chart(mc).mark_bar(color="#31518C").encode(
            x=alt.X("count:Q", title="건수"), y=alt.Y("media:N", sort="-x", title=None)
        ).properties(height=260)
        st.altair_chart(chart, use_container_width=True)
    with c4:
        S.section_title("태그 빈도 Top 10")
        tc = pd.Series(all_tags).value_counts().head(10).reset_index()
        tc.columns = ["tag", "count"]
        chart = alt.Chart(tc).mark_bar(color="#8A94A6").encode(
            x=alt.X("count:Q", title="건수"), y=alt.Y("tag:N", sort="-x", title=None)
        ).properties(height=260)
        st.altair_chart(chart, use_container_width=True)

    st.write("")
    S.section_title("최근 기자 문의 Topic vs 최근 보도 Topic")
    c5, c6 = st.columns(2)
    with c5:
        st.caption("기자 문의 (press_history 태그 기준)")
        inquiry_tags = [t for row in press["tags_list"] for t in row]
        it = pd.Series(inquiry_tags).value_counts().head(6).reset_index()
        it.columns = ["tag", "count"]
        chart = alt.Chart(it).mark_bar(color="#31518C").encode(
            x=alt.X("count:Q", title="건수"), y=alt.Y("tag:N", sort="-x", title=None)
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)
    with c6:
        st.caption("보도 (media_monitoring 태그 기준)")
        ct = pd.Series(all_tags).value_counts().head(6).reset_index()
        ct.columns = ["tag", "count"]
        chart = alt.Chart(ct).mark_bar(color="#8A94A6").encode(
            x=alt.X("count:Q", title="건수"), y=alt.Y("tag:N", sort="-x", title=None)
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)
    st.caption("동일 Topic이 기자 문의와 보도 양쪽에서 함께 상위에 있으면, 해당 주제에 대한 관심이 취재 단계부터 보도까지 이어지고 있다는 신호로 볼 수 있습니다.")
