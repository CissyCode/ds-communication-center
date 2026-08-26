from __future__ import annotations

import streamlit as st

from common import db as DB
from common import nav as N
from common import style as S
from views import home, insights, marcom, media, new_media, resources, schedule

st.set_page_config(
    page_title="DS COMMUNICATION CENTER",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB.ensure_ready()

p_home = st.Page(home.render, title="HOME", icon="🏠", url_path="home", default=True)
p_media = st.Page(media.render, title="MEDIA", icon="📰", url_path="media")
p_new_media = st.Page(new_media.render, title="NEW MEDIA", icon="🆕", url_path="new-media")
p_marcom = st.Page(marcom.render, title="MARCOM", icon="📣", url_path="marcom")
p_schedule = st.Page(schedule.render, title="SCHEDULE", icon="🗓️", url_path="schedule")
p_insights = st.Page(insights.render, title="INSIGHTS", icon="📊", url_path="insights")
p_resources = st.Page(resources.render, title="RESOURCES", icon="🗃️", url_path="resources")

N.register({
    "home": p_home,
    "media": p_media,
    "new_media": p_new_media,
    "marcom": p_marcom,
    "schedule": p_schedule,
    "insights": p_insights,
    "resources": p_resources,
})

pg = st.navigation([p_home, p_media, p_new_media, p_marcom, p_schedule, p_insights, p_resources])

S.inject_base_css()
pg.run()
