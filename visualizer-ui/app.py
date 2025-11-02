import streamlit as st
import pandas as pd
import json, time, os
import plotly.express as px

st.set_page_config(page_title="Anomaly Dashboard", layout="wide")
st.title("HDFS Anomaly Dashboard")
st.caption("Flask API에서 수집된 이상탐지 로그 스트림 모니터링")

LOG_PATH = "/data/events.jsonl"

@st.cache_data(ttl=3)
def load_logs():
    if not os.path.exists(LOG_PATH):
        return pd.DataFrame(columns=["timestamp", "status", "loss"])
    with open(LOG_PATH) as f:
        lines = [json.loads(l) for l in f.readlines()]
    df = pd.DataFrame(lines)
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.Timestamp.now()
    return df.tail(200)

# --- Sidebar Filters
st.sidebar.header("필터")
refresh_rate = st.sidebar.slider("갱신 주기 (초)", 1, 10, 2)
show_anomalies_only = st.sidebar.checkbox("이상치만 보기", False)

placeholder = st.empty()

while True:
    df = load_logs()
    if show_anomalies_only:
        df = df[df["status"] == "anomaly"]

    with placeholder.container():
        col1, col2, col3 = st.columns(3)
        total = len(df)
        anomalies = len(df[df["status"] == "anomaly"])
        anomaly_rate = (anomalies / total * 100) if total > 0 else 0

        col1.metric("총 로그 수", f"{total:,}")
        col2.metric("이상치 탐지 수", f"{anomalies:,}")
        col3.metric("이상치 비율 (%)", f"{anomaly_rate:.2f}")

        st.markdown("---")

        if len(df) > 0:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            chart = px.line(
                df,
                x="timestamp",
                y="loss",
                color="status",
                title="Loss Trend (최근 200개)",
                markers=True,
                color_discrete_map={"normal": "green", "anomaly": "red"},
            )

            st.plotly_chart(chart, use_container_width=True, key=f"chart_{time.time()}")

            st.subheader("📋 최근 로그 상세 (최신순)")
            st.dataframe(
                df.sort_values("timestamp", ascending=False)
                  .reset_index(drop=True)
                  .style.applymap(lambda v: "color:red" if v == "anomaly" else "")
            )
        else:
            st.info("수신된 로그가 아직 없습니다.")
    time.sleep(refresh_rate)