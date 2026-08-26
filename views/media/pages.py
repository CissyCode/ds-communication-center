"""The 11 MEDIA leaves as independent st.Page objects, grouped into sections
that mirror the MEDIA IA (Dashboard / Monitor & Analyze / PR / Media
Relations / Result / AI Workbench). main.py imports MEDIA_SECTIONS directly
into its st.navigation() call instead of routing through one internal page."""
from __future__ import annotations

import streamlit as st

from views.media import (
    ai_workbench, coverage_results, dashboard, intelligence, issues_risk,
    monitoring, pr_planning, pr_studio, programs, reporter_crm, response_desk,
)

p_dashboard = st.Page(dashboard.render, title="Dashboard", icon="📰", url_path="media-dashboard")
p_monitoring = st.Page(monitoring.render, title="Monitoring", icon="📡", url_path="media-monitoring")
p_issues_risk = st.Page(issues_risk.render, title="Issues & Risk", icon="⚠️", url_path="media-issues-risk")
p_intelligence = st.Page(intelligence.render, title="Media Intelligence", icon="📈", url_path="media-intelligence")
p_pr_planning = st.Page(pr_planning.render, title="PR Planning", icon="🧭", url_path="media-pr-planning")
p_pr_studio = st.Page(pr_studio.render, title="PR Studio", icon="📝", url_path="media-pr-studio")
p_programs = st.Page(programs.render, title="Media Programs", icon="🎤", url_path="media-programs")
p_response_desk = st.Page(response_desk.render, title="Response Desk", icon="📮", url_path="media-response-desk")
p_reporter_crm = st.Page(reporter_crm.render, title="Reporter CRM", icon="🗂️", url_path="media-reporter-crm")
p_coverage_results = st.Page(coverage_results.render, title="Coverage & Results", icon="📊", url_path="media-coverage-results")
p_ai_workbench = st.Page(ai_workbench.render, title="AI Workbench", icon="🤖", url_path="media-ai-workbench")

# Section-grouped, in sidebar display order.
MEDIA_SECTIONS: dict[str, list] = {
    "MEDIA": [p_dashboard],
    "MONITOR & ANALYZE": [p_monitoring, p_issues_risk, p_intelligence],
    "PR": [p_pr_planning, p_pr_studio, p_programs],
    "MEDIA RELATIONS": [p_response_desk, p_reporter_crm],
    "RESULT": [p_coverage_results],
    "AI WORKBENCH": [p_ai_workbench],
}

# key -> page, for common/nav.py deep-linking.
MEDIA_PAGES: dict[str, st.Page] = {
    "media_dashboard": p_dashboard,
    "media_monitoring": p_monitoring,
    "media_issues_risk": p_issues_risk,
    "media_intelligence": p_intelligence,
    "media_pr_planning": p_pr_planning,
    "media_pr_studio": p_pr_studio,
    "media_programs": p_programs,
    "media_response_desk": p_response_desk,
    "media_reporter_crm": p_reporter_crm,
    "media_coverage_results": p_coverage_results,
    "media_ai_workbench": p_ai_workbench,
}
