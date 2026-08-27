from __future__ import annotations

import streamlit as st

from common import db as DB
from common import nav as N
from common import style as S
from common import ui as U
from views import home, insights, marcom, new_media, resources, schedule
from views.media import pages as media_pages

st.set_page_config(
    page_title="DS COMMUNICATION CENTER",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB.ensure_ready()

p_home = st.Page(home.render, title="HOME", icon="🏠", url_path="home", default=True)
p_new_media = st.Page(new_media.render, title="NEW MEDIA", icon="🆕", url_path="new-media")
p_marcom = st.Page(marcom.render, title="MARCOM", icon="📣", url_path="marcom")
p_schedule = st.Page(schedule.render, title="SCHEDULE", icon="🗓️", url_path="schedule")
p_insights = st.Page(insights.render, title="INSIGHTS", icon="📊", url_path="insights")
p_resources = st.Page(resources.render, title="RESOURCES", icon="🗃️", url_path="resources")

N.register({
    "home": p_home,
    "new_media": p_new_media,
    "marcom": p_marcom,
    "schedule": p_schedule,
    "insights": p_insights,
    "resources": p_resources,
    **media_pages.MEDIA_PAGES,
})

# st.navigation only supports one level of section grouping, so MEDIA's
# 2-level IA (MEDIA > MONITOR & ANALYZE > Monitoring, ...) is flattened into
# section headers named after each MEDIA sub-group. Standalone top-level
# modules use blank-space section keys (each a distinct string, since dict
# keys must be unique) so their header isn't a redundant repeat of the
# page's own label.
pg = st.navigation({
    " ": [p_home],
    **media_pages.MEDIA_SECTIONS,
    "  ": [p_new_media],
    "   ": [p_marcom],
    "    ": [p_schedule],
    "     ": [p_insights],
    "      ": [p_resources],
})

S.inject_base_css()
U.inject_css()  # dashboard layer — must follow the base sheet, it widens the board
S.sidebar_demo_badge()
pg.run()
