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

# 사이드바 - 설정
st.sidebar.header("⚙️ Settings")
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 1, 30, 5)
anomaly_limit = st.sidebar.slider("Number of Anomalies to Display", 10, 100, 20)

# 통계 정보 가져오기
def get_statistics():
    try:
        response = requests.get(f"{API_URL}/statistics", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.sidebar.error(f"Failed to fetch statistics: {e}")
    return None

# 이상 로그 가져오기
def get_anomalies(limit=20):
    try:
        response = requests.get(f"{API_URL}/anomalies?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.sidebar.error(f"Failed to fetch anomalies: {e}")
    return None

# 전체 이벤트 가져오기
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

# 통계 섹션
stats = get_statistics()
if stats:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Logs", stats.get("total_logs", 0))

    with col2:
        st.metric("Anomalies", stats.get("total_anomalies", 0))

    with col3:
        st.metric("Normal", stats.get("total_normal", 0))

    with col4:
        anomaly_rate = stats.get("anomaly_rate", 0)
        st.metric("Anomaly Rate", f"{anomaly_rate}%")

    st.markdown("---")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📊 Recent Anomalies", "📈 All Events", "🤖 LLM Analysis"])

# 탭 1: 최근 이상 탐지
with tab1:
    st.header("📊 Recent Anomaly Detections")

    anomalies_data = get_anomalies(limit=anomaly_limit)

    if anomalies_data and anomalies_data.get("anomalies"):
        anomalies = anomalies_data["anomalies"]

        st.write(f"Showing {len(anomalies)} most recent anomalies (Total: {anomalies_data.get('total', 0)})")

        for idx, anomaly in enumerate(anomalies):
            with st.expander(f"🚨 Anomaly #{idx+1} - {anomaly.get('timestamp', 'N/A')}", expanded=(idx < 3)):
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

                    loss = anomaly.get('loss', 0)
                    threshold = anomaly.get('threshold', 1)
                    deviation = ((loss / threshold - 1) * 100) if threshold > 0 else 0
                    st.metric("Deviation", f"{deviation:.1f}%")

                # LLM 분석 결과
                llm_analysis = anomaly.get("llm_analysis")
                if llm_analysis:
                    st.markdown("---")
                    st.subheader("🤖 LLM Analysis")

                    # Severity 배지
                    severity = llm_analysis.get("severity", "UNKNOWN")
                    severity_colors = {
                        "LOW": "🟢",
                        "MEDIUM": "🟡",
                        "HIGH": "🟠",
                        "CRITICAL": "🔴"
                    }
                    st.markdown(f"**Severity:** {severity_colors.get(severity, '⚪')} {severity}")

                    # 요약
                    st.markdown(f"**Summary:** {llm_analysis.get('summary', 'N/A')}")

                    # 근본 원인
                    if llm_analysis.get('root_cause'):
                        st.markdown(f"**Root Cause:** {llm_analysis.get('root_cause')}")

                    # 영향
                    if llm_analysis.get('impact'):
                        st.markdown(f"**Impact:** {llm_analysis.get('impact')}")

                    # 추천 조치
                    recommendations = llm_analysis.get("recommendations", [])
                    if recommendations:
                        st.markdown("**Recommended Actions:**")
                        for rec_idx, rec in enumerate(recommendations, 1):
                            st.markdown(f"{rec_idx}. {rec}")

                    # LLM 분석 여부
                    if llm_analysis.get('llm_analyzed'):
                        st.success("✅ Analyzed by LLM")
                    else:
                        st.info("ℹ️ Rule-based analysis (LLM unavailable)")

                st.markdown("---")
    else:
        st.info("No anomalies detected yet.")

# 탭 2: 전체 이벤트
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

        # DataFrame 생성
        df_data = []
        for event in events:
            df_data.append({
                "Timestamp": event.get("timestamp", ""),
                "Status": event.get("status", ""),
                "Loss": f"{event.get('loss', 0):.6f}",
                "Threshold": f"{event.get('threshold', 0):.6f}",
                "Message": event.get("log", {}).get("message", "")[:80] + "..."
            })

        df = pd.DataFrame(df_data)

        # 상태별 색상
        def highlight_status(row):
            if row.Status == 'anomaly':
                return ['background-color: #ffcccc'] * len(row)
            else:
                return ['background-color: #ccffcc'] * len(row)

        st.dataframe(df.style.apply(highlight_status, axis=1), use_container_width=True)

        st.write(f"Showing {len(events)} events")
    else:
        st.info("No events available.")

# 탭 3: LLM 분석 요약
with tab3:
    st.header("🤖 LLM Analysis Summary")

    anomalies_data = get_anomalies(limit=50)

    if anomalies_data and anomalies_data.get("anomalies"):
        anomalies = anomalies_data["anomalies"]

        # LLM 분석 통계
        llm_analyzed_count = sum(
            1 for a in anomalies
            if (a or {}).get("llm_analysis", {}).get("llm_analyzed") is True
        )
        total_anomalies = len(anomalies)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Anomalies", total_anomalies)
        with col2:
            st.metric("LLM Analyzed", f"{llm_analyzed_count}/{total_anomalies}")

        # Severity 분포
        st.subheader("Severity Distribution")
        severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

        for anomaly in anomalies:
            llm = anomaly.get("llm_analysis", {})
            severity = llm.get("severity", "UNKNOWN")
            if severity in severity_counts:
                severity_counts[severity] += 1

        severity_df = pd.DataFrame({
            "Severity": list(severity_counts.keys()),
            "Count": list(severity_counts.values())
        })

        st.bar_chart(severity_df.set_index("Severity"))

        # 패턴 분포
        st.subheader("Pattern Distribution")
        pattern_counts = {}

        for anomaly in anomalies:
            llm = anomaly.get("llm_analysis", {})
            pattern = llm.get("pattern", "unknown")
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        pattern_df = pd.DataFrame({
            "Pattern": list(pattern_counts.keys()),
            "Count": list(pattern_counts.values())
        })

        st.bar_chart(pattern_df.set_index("Pattern"))

        # 최근 추천 조치
        st.subheader("Recent Recommendations")

        for idx, anomaly in enumerate(anomalies[:5]):
            llm = anomaly.get("llm_analysis", {})
            if llm and llm.get("recommendations"):
                with st.expander(f"Anomaly at {anomaly.get('timestamp', 'N/A')}"):
                    st.markdown(f"**Summary:** {llm.get('summary', 'N/A')}")
                    st.markdown("**Actions:**")
                    for rec in llm.get("recommendations", [])[:3]:
                        st.markdown(f"- {rec}")

    else:
        st.info("No LLM analysis data available.")

# Auto refresh
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("🔍 **Anomaly Detection Dashboard** | Powered by LLM Analysis")
