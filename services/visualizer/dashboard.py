"""
Visualizer Dashboard
Streamlit-based dashboard for anomaly detection visualization
"""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

# API URL
API_URL = "http://localhost:8502"

# 페이지 설정
st.set_page_config(
    page_title="Anomaly Detection Dashboard",
    page_icon="🔍",
    layout="wide"
)

# 제목
st.title("🔍 Distributed System Anomaly Detection Dashboard")
st.markdown("---")

# ------------------------- Helper Functions ------------------------- #

def get_statistics():
    try:
        response = requests.get(f"{API_URL}/statistics", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.sidebar.error(f"Failed to fetch statistics: {e}")
    return None


def get_anomalies(limit=20):
    try:
        response = requests.get(f"{API_URL}/anomalies?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.sidebar.error(f"Failed to fetch anomalies: {e}")
    return None


def get_events(limit=100, status=None):
    try:
        url = f"{API_URL}/events?limit={limit}"
        if status:
            url += f"&status={status}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.sidebar.error(f"Failed to fetch events: {e}")
    return None

# ------------------------- Sidebar Controls ------------------------- #

st.sidebar.header("⚙️ Settings")
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 1, 30, 5)
anomaly_limit = st.sidebar.slider("Number of Anomalies to Display", 10, 100, 20)

# ------------------------- Statistics Section ------------------------- #

stats = get_statistics()
if stats:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Logs", stats.get("total_logs", 0))
    col2.metric("Anomalies", stats.get("total_anomalies", 0))
    col3.metric("Normal", stats.get("total_normal", 0))
    col4.metric("Anomaly Rate", f"{stats.get('anomaly_rate', 0)}%")

    st.markdown("---")

# ------------------------- Tab Layout ------------------------- #

tab1, tab2, tab3 = st.tabs(["📊 Recent Anomalies", "📈 All Events", "🤖 LLM Analysis Summary"])

# ------------------------- TAB 1: Recent Anomalies ------------------------- #

with tab1:
    st.header("📊 Recent Anomaly Detections")

    anomalies_data = get_anomalies(limit=anomaly_limit)

    if anomalies_data and anomalies_data.get("anomalies"):
        anomalies = anomalies_data["anomalies"]
        st.write(f"Showing {len(anomalies)} most recent anomalies (Total: {anomalies_data.get('total', 0)})")

        for idx, anomaly in enumerate(anomalies):
            with st.expander(f"🚨 Anomaly #{idx + 1} — {anomaly.get('timestamp', 'N/A')}", expanded=(idx < 3)):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.subheader("Log Information")
                    log = anomaly.get("log", {})
                    st.text(f"Message: {log.get('message', 'N/A')}")
                    st.text(f"Service: {log.get('service', {}).get('name', 'N/A')}")
                    st.text(f"Host: {log.get('host', {}).get('name', 'N/A')}")

                with col2:
                    st.subheader("Detection Metrics")
                    st.metric("Loss Score", f"{anomaly.get('loss', 0):.6f}")
                    st.metric("Threshold", f"{anomaly.get('threshold', 0):.6f}")

                    loss = anomaly.get("loss", 0)
                    threshold = anomaly.get("threshold", 1)
                    deviation = ((loss / threshold - 1) * 100) if threshold > 0 else 0
                    st.metric("Deviation", f"{deviation:.1f}%")

                # LLM 분석 블록
                llm = anomaly.get("llm_analysis") or {}

                if llm:
                    st.markdown("---")
                    st.subheader("🤖 LLM Analysis")

                    severity = llm.get("severity", "UNKNOWN")
                    severity_color = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")
                    st.markdown(f"**Severity:** {severity_color} {severity}")
                    st.markdown(f"**Summary:** {llm.get('summary', 'N/A')}")

                    if llm.get("root_cause"):
                        st.markdown(f"**Root Cause:** {llm.get('root_cause')}")

                    if llm.get("impact"):
                        st.markdown(f"**Impact:** {llm.get('impact')}")

                    recommendations = llm.get("recommendations", [])
                    if recommendations:
                        st.markdown("**Recommended Actions:**")
                        for r in recommendations:
                            st.markdown(f"- {r}")

                    if llm.get("llm_analyzed"):
                        st.success("Analyzed by LLM")
                    else:
                        st.info("Rule-based fallback used")

                st.markdown("---")
    else:
        st.info("No anomalies detected yet.")

# ------------------------- TAB 2: All Events ------------------------- #

with tab2:
    st.header("📈 All Events Timeline")

    event_filter = st.radio("Filter by status:", ["All", "Anomaly", "Normal"], horizontal=True)

    status_filter = None
    if event_filter == "Anomaly":
        status_filter = "anomaly"
    elif event_filter == "Normal":
        status_filter = "normal"

    events_data = get_events(limit=100, status=status_filter)

    if events_data and events_data.get("events"):
        events = events_data["events"]

        df = pd.DataFrame([
            {
                "Timestamp": e.get("timestamp", ""),
                "Status": e.get("status", ""),
                "Loss": f"{e.get('loss', 0):.6f}",
                "Threshold": f"{e.get('threshold', 0):.6f}",
                "Message": (e.get("log", {}).get("message", "")[:80] + "...")
            }
            for e in events
        ])

        def highlight(row):
            return ['background-color: #ffcccc' if row.Status == 'anomaly'
                    else 'background-color: #ccffcc'] * len(row)

        st.dataframe(df.style.apply(highlight, axis=1), use_container_width=True)
        st.write(f"Showing {len(events)} events")
    else:
        st.info("No events available.")

# ------------------------- TAB 3: LLM Summary ------------------------- #

with tab3:
    st.header("🤖 LLM Analysis Summary")

    anomalies_data = get_anomalies(limit=50)

    if anomalies_data and anomalies_data.get("anomalies"):
        anomalies = anomalies_data["anomalies"]

        llm_analyzed_count = sum(
            1 for a in anomalies
            if isinstance(a, dict)
            and isinstance(a.get("llm_analysis"), dict)
            and a["llm_analysis"].get("llm_analyzed") is True
        )

        col1, col2 = st.columns(2)
        col1.metric("Total Anomalies", len(anomalies))
        col2.metric("LLM Analyzed", f"{llm_analyzed_count}/{len(anomalies)}")

        # Severity distribution
        st.subheader("Severity Distribution")
        severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for anomaly in anomalies:
            llm = anomaly.get("llm_analysis") or {}
            sev = llm.get("severity")
            if sev in severity_counts:
                severity_counts[sev] += 1

        severity_df = pd.DataFrame({"Severity": list(severity_counts.keys()), "Count": list(severity_counts.values())})
        st.bar_chart(severity_df.set_index("Severity"))

        # Pattern distribution
        st.subheader("Pattern Distribution")
        pattern_counts = {}
        for anomaly in anomalies:
            llm = anomaly.get("llm_analysis") or {}
            pattern = llm.get("pattern", "unknown")
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        pattern_df = pd.DataFrame({"Pattern": list(pattern_counts.keys()), "Count": list(pattern_counts.values())})
        st.bar_chart(pattern_df.set_index("Pattern"))

        # Recent recommendations list
        st.subheader("Recent Recommendations")
        for anomaly in anomalies[:5]:
            llm = anomaly.get("llm_analysis") or {}
            if llm and llm.get("recommendations"):
                with st.expander(f"Anomaly at {anomaly.get('timestamp')}"):
                    st.markdown(f"**Summary:** {llm.get('summary', 'N/A')}")
                    for rec in llm.get("recommendations")[:3]:
                        st.markdown(f"- {rec}")
    else:
        st.info("No LLM analysis data available.")

# ------------------------- Auto Refresh ------------------------- #

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("🔍 **Anomaly Detection Dashboard** | Powered by LLM Analysis")