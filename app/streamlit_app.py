import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime

# API_URL = "http://localhost:8000/api"
import os
API_URL = os.getenv("API_URL", "http://localhost:8000/api")

st.set_page_config(
    page_title="AI BI Copilot",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.main-header {
    font-size:2rem;font-weight:700;
    background:linear-gradient(90deg,#6366f1,#8b5cf6);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.sub-header { color:#6b7280;font-size:.95rem;margin-top:0; }
.insight-box {
    background:linear-gradient(135deg,#667eea22,#764ba222);
    border-left:4px solid #6366f1;border-radius:8px;
    padding:12px 16px;margin:8px 0;font-size:.95rem;
}
.kpi-card {
    background:var(--background-color);
    border:1px solid #e2e8f0;border-radius:12px;
    padding:20px;text-align:center;
}
.kpi-value { font-size:1.8rem;font-weight:700;color:#6366f1; }
.kpi-label { font-size:.85rem;color:#6b7280;margin-top:4px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "session_id"  not in st.session_state: st.session_state.session_id  = str(uuid.uuid4())
if "messages"    not in st.session_state: st.session_state.messages    = []
if "query_count" not in st.session_state: st.session_state.query_count = 0
if "last_df"     not in st.session_state: st.session_state.last_df     = None
if "active_db"   not in st.session_state: st.session_state.active_db   = "sample_data/sales.db"
if "active_db_name" not in st.session_state: st.session_state.active_db_name = "sales.db (default)"


# ── Helpers ───────────────────────────────────────────────────────────────────
def query_backend(question: str) -> dict:
    try:
        resp = requests.post(f"{API_URL}/query", json={
            "question":   question,
            "session_id": st.session_state.session_id,
            "db_path":    st.session_state.active_db
        }, timeout=60)
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend. Is FastAPI running on port 8000?"}
    except Exception as e:
        return {"error": str(e)}


def build_chart(df, chart_type, question):
    if df is None or df.empty or chart_type == "none": return None
    cols     = df.columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = [c for c in cols if c not in num_cols]
    if not num_cols: return None
    x_col = cat_cols[0] if cat_cols else cols[0]
    y_col = num_cols[0]
    title = question[:60] + "..." if len(question) > 60 else question
    colors = ["#6366f1","#8b5cf6","#a78bfa","#c4b5fd","#06b6d4","#10b981","#f59e0b","#ef4444"]
    try:
        if chart_type == "line":
            fig = px.line(df, x=x_col, y=num_cols, title=title, markers=True, color_discrete_sequence=colors)
        elif chart_type == "pie":
            fig = px.pie(df, names=x_col, values=y_col, title=title, color_discrete_sequence=colors)
        elif chart_type == "scatter" and len(num_cols) >= 2:
            fig = px.scatter(df, x=num_cols[0], y=num_cols[1], hover_data=cat_cols, title=title, color_discrete_sequence=colors)
        else:
            fig = px.bar(df, x=x_col, y=y_col, title=title, color=x_col if len(df)<=12 else None, color_discrete_sequence=colors)
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          font=dict(family="Inter,sans-serif",size=12), height=380,
                          margin=dict(l=20,r=20,t=40,b=20))
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(gridcolor="#f1f5f9")
        return fig
    except Exception: return None


def build_forecast_chart(data: dict):
    historical = pd.DataFrame(data.get("historical", []))
    forecast   = pd.DataFrame(data.get("forecast",   []))
    if historical.empty or forecast.empty: return None
    future  = forecast[forecast["is_future"] == True]
    fig     = go.Figure()
    fig.add_trace(go.Scatter(x=historical["date"], y=historical["actual"],
        name="Historical", line=dict(color="#6366f1", width=2), mode="lines+markers", marker=dict(size=4)))
    if not future.empty:
        fig.add_trace(go.Scatter(
            x=pd.concat([future["date"], future["date"].iloc[::-1]]),
            y=pd.concat([future["upper"], future["lower"].iloc[::-1]]),
            fill="toself", fillcolor="rgba(139,92,246,0.15)",
            line=dict(color="rgba(255,255,255,0)"), name="80% confidence"))
        fig.add_trace(go.Scatter(x=future["date"], y=future["forecast"],
            name="Forecast", line=dict(color="#8b5cf6", width=2, dash="dash"),
            mode="lines+markers", marker=dict(size=5, symbol="diamond")))
    fig.update_layout(
        title       = f"{data.get('metric','revenue').title()} Forecast — next {data.get('periods',6)} months",
        plot_bgcolor= "rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,sans-serif", size=12), height=420,
        margin=dict(l=20,r=20,t=50,b=20),
        legend=dict(orientation="h", y=-0.15), hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#f1f5f9")
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧠 AI BI Copilot")
    st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
    st.caption(f"DB: `{st.session_state.active_db_name}`")
    st.divider()

    st.markdown("**📊 Sample queries**")
    sample_questions = [
        "Show total revenue by region for 2024",
        "Show me the Odisha sales drop in Q3 2024",
        "Which product category has highest revenue?",
        "Top 5 products by total quantity sold",
        "Monthly revenue trend for 2024",
        "Compare online vs retail vs wholesale revenue",
        "Which city has most returns?",
        "Who are the top 3 sales reps by revenue?",
    ]
    for q in sample_questions:
        if st.button(q, key=q, use_container_width=True):
            st.session_state.pending_question = q

    st.divider()
    st.metric("Queries this session", st.session_state.query_count)

    st.divider()
    st.markdown("**📂 Upload your database**")
    uploaded_db = st.file_uploader("SQLite .db file", type=None, key="db_uploader")
    if uploaded_db is not None:
        fname = uploaded_db.name.lower()
        if not any(fname.endswith(ext) for ext in [".db",".sqlite",".sqlite3"]):
            st.error("Please upload a .db or .sqlite file")
        else:
            with st.spinner("Uploading..."):
                try:
                    resp = requests.post(f"{API_URL}/upload-db",
                        files={"file":(uploaded_db.name, uploaded_db.read(), "application/octet-stream")},
                        timeout=30)
                    info = resp.json()
                    if "db_path" in info:
                        st.session_state.active_db      = info["db_path"]
                        st.session_state.active_db_name = uploaded_db.name
                        st.success(f"✅ {uploaded_db.name}")
                        for tbl, meta in info["tables"].items():
                            st.caption(f"• {tbl} ({meta['row_count']} rows)")
                    else:
                        st.error(info.get("detail","Upload failed"))
                except Exception as e:
                    st.error(str(e))

    if st.session_state.active_db_name != "sales.db (default)":
        if st.button("↩️ Back to default DB", key="back_to_default_db", use_container_width=True):
            st.session_state.active_db      = "sample_data/sales.db"
            st.session_state.active_db_name = "sales.db (default)"
            st.rerun()

    st.divider()
    if st.session_state.last_df is not None:
        csv = st.session_state.last_df.to_csv(index=False)
        st.download_button("⬇️ Download last result (CSV)", data=csv,
            file_name=f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv", use_container_width=True)

    if st.button("🔄 New session", use_container_width=True, key="new_session"):
        st.session_state.session_id  = str(uuid.uuid4())
        st.session_state.messages    = []
        st.session_state.query_count = 0
        st.session_state.last_df     = None
        st.rerun()


# ── Main area — tabs ──────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🧠 Agentic AI BI Copilot</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Enterprise conversational analytics — ask anything about your data</p>', unsafe_allow_html=True)

tab_chat, tab_forecast, tab_quality, tab_dashboard, tab_rca, tab_optimizer, tab_alerts, tab_history = st.tabs([
    "💬 Chat analyst",
    "📈 Forecasting",
    "🔬 Data quality",
    "📊 Dashboard",
    "🔎 Root cause",
    "⚡ Optimizer",
    "🚨 Alerts",
    "🕓 History"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:

    # Render existing messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑" if msg["role"]=="user" else "🤖"):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                if msg.get("insight"):
                    st.markdown(f'<div class="insight-box">💡 <b>Insight:</b> {msg["insight"]}</div>', unsafe_allow_html=True)
                if msg.get("explanation"):
                    st.caption(f"📝 {msg['explanation']}")
                if msg.get("chart") is not None:
                    st.plotly_chart(msg["chart"], use_container_width=True, key=msg.get("chart_key"))
                if msg.get("df") is not None and not msg["df"].empty:
                    with st.expander(f"📋 View data ({len(msg['df'])} rows)", expanded=False):
                        st.dataframe(msg["df"], use_container_width=True)
                if msg.get("sql"):
                    with st.expander("🔍 SQL query", expanded=False):
                        st.code(msg["sql"], language="sql")
                if msg.get("error"):
                    st.error(f"❌ {msg['error']}")

    # Handle sidebar button click
    if "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")
        st.session_state.messages.append({"role":"user","content":question})
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🤔 Thinking..."):
                result = query_backend(question)
            st.session_state.query_count += 1
            _df    = pd.DataFrame(result.get("data",[]))
            _chart = None
            _key   = f"chart_sb_{st.session_state.query_count}"
            if result.get("insight"):
                st.markdown(f'<div class="insight-box">💡 <b>Insight:</b> {result["insight"]}</div>', unsafe_allow_html=True)
            if result.get("explanation"):
                st.caption(f"📝 {result['explanation']}")
            if not _df.empty:
                _chart = build_chart(_df, result.get("chart_type","bar"), question)
                if _chart: st.plotly_chart(_chart, use_container_width=True, key=_key)
                with st.expander(f"📋 View data ({len(_df)} rows)", expanded=len(_df)<=10):
                    st.dataframe(_df, use_container_width=True)
                st.session_state.last_df = _df
            if result.get("sql"):
                with st.expander("🔍 SQL query", expanded=False):
                    st.code(result["sql"], language="sql")
            if result.get("error"):
                st.error(f"❌ {result['error']}")
            st.session_state.messages.append({
                "role":"assistant","insight":result.get("insight",""),
                "explanation":result.get("explanation",""),"sql":result.get("sql",""),
                "df":_df if not _df.empty else None,"chart":_chart,"chart_key":_key,
                "error":result.get("error")
            })
        st.rerun()

    # PDF export
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("📄 Export session as PDF", key="pdf_btn", use_container_width=True):
            with st.spinner("Generating PDF..."):
                try:
                    paired = []
                    msgs   = st.session_state.messages
                    for i, m in enumerate(msgs):
                        if m["role"] == "assistant":
                            question = msgs[i-1]["content"] if i > 0 else ""
                            df_obj   = m.get("df")
                            paired.append({
                                "question":    question,
                                "sql":         m.get("sql",""),
                                "explanation": m.get("explanation",""),
                                "insight":     m.get("insight",""),
                                "row_count":   len(df_obj) if df_obj is not None else 0,
                                "data":        df_obj.to_dict(orient="records") if df_obj is not None else []
                            })
                    if not paired:
                        st.warning("Ask at least one question first.")
                    else:
                        pdf_resp = requests.post(f"{API_URL}/report/pdf",
                            json={"session_id":st.session_state.session_id,"session_data":paired},
                            timeout=30)
                        if pdf_resp.status_code == 200:
                            st.download_button("⬇️ Download PDF", data=pdf_resp.content,
                                file_name=f"report_{st.session_state.session_id[:8]}.pdf",
                                mime="application/pdf", use_container_width=True, key="pdf_dl")
                        else:
                            st.error(f"PDF error: {pdf_resp.text}")
                except Exception as e:
                    st.error(str(e))

    # Chat input
    if prompt := st.chat_input("Ask anything about your data..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🤔 Thinking..."):
                result = query_backend(prompt)
            st.session_state.query_count += 1
            df    = pd.DataFrame(result.get("data",[]))
            chart = None
            ckey  = f"chart_{st.session_state.query_count}"
            if result.get("error") and not result.get("sql"):
                st.error(f"❌ {result['error']}")
                st.session_state.messages.append({"role":"assistant","error":result["error"]})
            else:
                if result.get("insight"):
                    st.markdown(f'<div class="insight-box">💡 <b>Insight:</b> {result["insight"]}</div>', unsafe_allow_html=True)
                if result.get("explanation"):
                    st.caption(f"📝 {result['explanation']}")
                if not df.empty:
                    chart = build_chart(df, result.get("chart_type","bar"), prompt)
                    if chart: st.plotly_chart(chart, use_container_width=True, key=ckey)
                    with st.expander(f"📋 View data ({len(df)} rows)", expanded=len(df)<=10):
                        st.dataframe(df, use_container_width=True)
                    st.session_state.last_df = df
                if result.get("sql"):
                    with st.expander("🔍 SQL query", expanded=False):
                        st.code(result["sql"], language="sql")
                if result.get("error"):
                    st.warning(f"⚠️ {result['error']}")
                st.session_state.messages.append({
                    "role":"assistant","insight":result.get("insight",""),
                    "explanation":result.get("explanation",""),"sql":result.get("sql",""),
                    "df":df if not df.empty else None,"chart":chart,"chart_key":ckey,
                    "error":result.get("error")
                })
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — FORECASTING
# ══════════════════════════════════════════════════════════════════════════════
with tab_forecast:
    st.subheader("📈 ML Sales Forecasting")
    st.caption("Powered by Facebook Prophet — predicts future trends with confidence intervals")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        fc_metric = st.selectbox("Metric to forecast", ["revenue","quantity","orders"], key="fc_metric")
    with col2:
        fc_periods = st.slider("Months ahead", 1, 12, 6, key="fc_periods")
    with col3:
        fc_region = st.text_input("Filter by region (optional)", placeholder="e.g. Odisha", key="fc_region")

    if st.button("🚀 Generate forecast", key="fc_btn", use_container_width=True):
        with st.spinner("Running Prophet ML model..."):
            try:
                params = {
                    "metric":  fc_metric,
                    "periods": fc_periods,
                    "db_path": st.session_state.active_db
                }
                if fc_region.strip():
                    params["region"] = fc_region.strip()
                resp    = requests.get(f"{API_URL}/forecast", params=params, timeout=60)
                fc_data = resp.json()
                if fc_data.get("success"):
                    st.session_state.forecast_data = fc_data
                else:
                    st.error(f"❌ {fc_data.get('error','Unknown error')}")
            except Exception as e:
                st.error(str(e))

    if "forecast_data" in st.session_state:
        fc = st.session_state.forecast_data

        st.markdown(f'<div class="insight-box">💡 {fc.get("insight","")}</div>', unsafe_allow_html=True)
        st.caption(f"Model: **{fc.get('model','')}**")
        st.divider()

        fig = build_forecast_chart(fc)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="fc_main_chart")

        future_rows = [r for r in fc.get("forecast",[]) if r.get("is_future")]
        hist_rows   = fc.get("historical",[])

        col1, col2 = st.columns(2)
        with col1:
            if future_rows:
                st.markdown("**📋 Forecast table**")
                fc_df = pd.DataFrame(future_rows)[["date","forecast","lower","upper"]]
                fc_df.columns = ["Month","Forecast ₹","Lower ₹","Upper ₹"]
                for c in ["Forecast ₹","Lower ₹","Upper ₹"]:
                    fc_df[c] = fc_df[c].apply(lambda x: f"₹{x:,.0f}")
                st.dataframe(fc_df, use_container_width=True, hide_index=True)

        with col2:
            if hist_rows:
                st.markdown("**📊 Historical summary**")
                h_df  = pd.DataFrame(hist_rows)
                total = h_df["actual"].sum()
                avg   = h_df["actual"].mean()
                peak  = h_df.loc[h_df["actual"].idxmax()]
                st.metric("Total historical", f"₹{total:,.0f}")
                st.metric("Monthly average",  f"₹{avg:,.0f}")
                st.metric("Peak month",        f"{peak['date']} (₹{peak['actual']:,.0f})")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DATA QUALITY
# ══════════════════════════════════════════════════════════════════════════════
with tab_quality:
    st.subheader("🔬 Data Quality Scanner")
    st.caption("Detects missing values, duplicates, outliers, whitespace issues, and more")
    st.divider()

    if st.button("🔍 Run quality scan", key="quality_btn", use_container_width=True):
        with st.spinner("Scanning all tables..."):
            try:
                resp = requests.get(f"{API_URL}/quality",
                    params={"db_path": st.session_state.active_db}, timeout=30)
                st.session_state.quality_report = resp.json()
            except Exception as e:
                st.error(str(e))

    if "quality_report" in st.session_state:
        qr    = st.session_state.quality_report
        score = qr.get("overall_score", 0)
        color = "#10b981" if score>=80 else ("#f59e0b" if score>=60 else "#ef4444")
        label = "Excellent" if score>=80 else ("Needs attention" if score>=60 else "Critical issues")

        # Score banner
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown(
                f'<div style="text-align:center;padding:24px;border-radius:12px;'
                f'border:2px solid {color}22">'
                f'<div style="font-size:3.5rem;font-weight:700;color:{color}">{score}</div>'
                f'<div style="font-size:1rem;color:{color}">/100 — {label}</div>'
                f'<div style="font-size:.85rem;color:#6b7280;margin-top:8px">{qr.get("summary","")}</div>'
                f'</div>', unsafe_allow_html=True
            )

        st.divider()

        # Per-table breakdown
        for table in qr.get("tables",[]):
            issues    = table.get("issues",[])
            t_score   = table.get("score",100)
            t_color   = "#10b981" if t_score>=80 else ("#f59e0b" if t_score>=60 else "#ef4444")
            n_critical = sum(1 for i in issues if i["severity"]=="critical")
            n_warn     = sum(1 for i in issues if i["severity"]=="warning")
            n_info     = sum(1 for i in issues if i["severity"]=="info")

            with st.expander(
                f"{'✅' if not issues else '⚠️'} **{table['table']}** — "
                f"{table['row_count']:,} rows — score: {t_score}/100",
                expanded=bool(issues)
            ):
                if not issues:
                    st.success("No issues found — this table is clean.")
                else:
                    # Summary pills
                    c1,c2,c3 = st.columns(3)
                    c1.metric("🔴 Critical", n_critical)
                    c2.metric("🟡 Warnings", n_warn)
                    c3.metric("🔵 Info",     n_info)
                    st.divider()

                    for issue in issues:
                        sev  = issue["severity"]
                        icon = "🔴" if sev=="critical" else ("🟡" if sev=="warning" else "🔵")
                        col  = "#ef4444" if sev=="critical" else ("#f59e0b" if sev=="warning" else "#3b82f6")
                        st.markdown(
                            f'<div style="border-left:3px solid {col};padding:8px 12px;'
                            f'margin:6px 0;border-radius:0 6px 6px 0;">'
                            f'{icon} <b>{issue["column"]}</b> — {issue["detail"]}<br>'
                            f'<span style="font-size:.82rem;color:#6b7280">💡 {issue["suggestion"]}</span>'
                            f'</div>', unsafe_allow_html=True
                        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — AUTO DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.subheader("📊 Auto-Generated Business Dashboard")
    st.caption("Universal dashboard — works on any database, auto-discovers schema")
    st.divider()

    if st.button("⚡ Generate dashboard", key="dash_btn", use_container_width=True):
        with st.spinner("Building dashboard..."):
            try:
                resp = requests.get(f"{API_URL}/dashboard",
                    params={"db_path": st.session_state.active_db}, timeout=30)
                st.session_state.dashboard_data = resp.json()
            except Exception as e:
                st.error(str(e))

    if "dashboard_data" in st.session_state:
        d          = st.session_state.dashboard_data
        kpis       = d.get("kpis", {})
        charts     = d.get("charts", [])
        top_lists  = d.get("top_lists", [])
        is_sales   = d.get("is_sales_db", False)

        # ── KPI Cards (universal) ─────────────────────────────────────────────
        kpi_items = list(kpis.values())
        if kpi_items:
            cols_per_row = min(len(kpi_items), 6)
            rows         = [kpi_items[i:i+cols_per_row]
                            for i in range(0, len(kpi_items), cols_per_row)]
            for row in rows:
                cols = st.columns(len(row))
                for col, kpi in zip(cols, row):
                    col.metric(kpi.get("label",""), kpi.get("value",""))
            st.divider()

        # ── Sales DB: original beautiful layout ───────────────────────────────
        if is_sales:
            col1, col2 = st.columns(2)
            with col1:
                monthly = pd.DataFrame(d.get("monthly_trend",[]))
                if not monthly.empty:
                    fig = px.line(monthly, x="month", y="revenue",
                        title="📈 Monthly Revenue Trend",
                        markers=True, color_discrete_sequence=["#6366f1"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=300,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    fig.update_yaxes(gridcolor="#f1f5f9")
                    st.plotly_chart(fig, use_container_width=True, key="dash_monthly")
            with col2:
                region_df = pd.DataFrame(d.get("by_region",[]))
                if not region_df.empty:
                    fig = px.bar(region_df, x="region", y="revenue",
                        title="🌍 Revenue by Region", color="region",
                        color_discrete_sequence=["#6366f1","#8b5cf6",
                                                  "#a78bfa","#06b6d4","#10b981"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=300,
                        showlegend=False, margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True, key="dash_region")

            col3, col4 = st.columns(2)
            with col3:
                cat_df = pd.DataFrame(d.get("by_category",[]))
                if not cat_df.empty:
                    fig = px.pie(cat_df, names="category", values="revenue",
                        title="🏷️ Revenue by Category",
                        color_discrete_sequence=["#6366f1","#8b5cf6","#a78bfa",
                                                  "#06b6d4","#10b981","#f59e0b"])
                    fig.update_layout(height=300, margin=dict(l=10,r=10,t=40,b=10))
                    st.plotly_chart(fig, use_container_width=True, key="dash_cat")
            with col4:
                ch_df = pd.DataFrame(d.get("by_channel",[]))
                if not ch_df.empty:
                    fig = px.bar(ch_df, x="channel", y="revenue",
                        title="📡 Revenue by Channel", color="channel",
                        color_discrete_sequence=["#06b6d4","#10b981","#f59e0b"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=300,
                        showlegend=False, margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True, key="dash_ch")

            col5, col6 = st.columns(2)
            with col5:
                qoq_df = pd.DataFrame(d.get("qoq",[]))
                if not qoq_df.empty:
                    qoq_df["period"] = qoq_df["year"].astype(str) + " " + qoq_df["quarter"]
                    fig = px.bar(qoq_df, x="period", y="revenue",
                        title="📅 Quarterly Revenue (QoQ)", color="quarter",
                        color_discrete_sequence=["#6366f1","#8b5cf6","#a78bfa","#06b6d4"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=320,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False, tickangle=45)
                    st.plotly_chart(fig, use_container_width=True, key="dash_qoq")
            with col6:
                prod_df = pd.DataFrame(d.get("top_products",[]))
                if not prod_df.empty:
                    fig = px.bar(prod_df, x="revenue", y="product",
                        orientation="h", title="🏆 Top 5 Products",
                        color_discrete_sequence=["#6366f1"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=320,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True, key="dash_prod")

            col7, col8 = st.columns(2)
            with col7:
                reps_df = pd.DataFrame(d.get("top_reps",[]))
                if not reps_df.empty:
                    st.markdown("**🏅 Top Sales Reps**")
                    reps_df["revenue"] = reps_df["revenue"].apply(lambda x: f"₹{x:,.0f}")
                    st.dataframe(reps_df, use_container_width=True, hide_index=True)
            with col8:
                ret_df = pd.DataFrame(d.get("returns_summary",[]))
                if not ret_df.empty:
                    st.markdown("**↩️ Returns by Reason**")
                    ret_df["total_refunds"] = ret_df["total_refunds"].apply(
                        lambda x: f"₹{x:,.0f}")
                    st.dataframe(ret_df, use_container_width=True, hide_index=True)

        # ── Universal DB: dynamic chart layout ────────────────────────────────
        else:
            colors = ["#6366f1","#8b5cf6","#a78bfa","#06b6d4",
                      "#10b981","#f59e0b","#ef4444","#ec4899"]

            if not charts:
                st.info("No charts could be generated. Try a different database.")
            else:
                # Render charts in pairs
                for i in range(0, len(charts), 2):
                    pair = charts[i:i+2]
                    cols = st.columns(len(pair))
                    for col, chart in zip(cols, pair):
                        with col:
                            df = pd.DataFrame(chart["data"])
                            if df.empty:
                                continue
                            x = chart["x"]
                            y = chart["y"]
                            ct = chart["type"]
                            title = chart["title"]

                            try:
                                if ct == "line":
                                    fig = px.line(df, x=x, y=y, title=title,
                                        markers=True,
                                        color_discrete_sequence=colors)
                                elif ct == "pie":
                                    fig = px.pie(df, names=x, values=y,
                                        title=title,
                                        color_discrete_sequence=colors)
                                elif ct == "grouped_bar":
                                    y_labels = chart.get("y_labels", y)
                                    df_melt  = df.rename(columns={
                                        y[0]: y_labels[0],
                                        y[1]: y_labels[1]
                                    })
                                    fig = px.bar(df_melt, x=x,
                                        y=y_labels, barmode="group",
                                        title=title,
                                        color_discrete_sequence=colors)
                                else:
                                    fig = px.bar(df, x=x, y=y, title=title,
                                        color=x if len(df) <= 10 else None,
                                        color_discrete_sequence=colors)

                                fig.update_layout(
                                    plot_bgcolor ="rgba(0,0,0,0)",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    height       = 320,
                                    showlegend   = ct in ["pie","line","grouped_bar"],
                                    margin       = dict(l=10,r=10,t=40,b=10),
                                    font         = dict(size=11)
                                )
                                fig.update_xaxes(showgrid=False, tickangle=20)
                                fig.update_yaxes(gridcolor="#f1f5f9")
                                st.plotly_chart(fig,
                                    use_container_width=True,
                                    key=f"dash_chart_{i}_{chart['table']}")
                            except Exception as e:
                                st.caption(f"Could not render: {e}")

            # Top lists
            if top_lists:
                st.divider()
                st.markdown("### 🏆 Top lists")
                for i in range(0, len(top_lists), 2):
                    pair = top_lists[i:i+2]
                    cols = st.columns(len(pair))
                    for col, tl in zip(cols, pair):
                        with col:
                            st.markdown(f"**{tl['title']}**")
                            df = pd.DataFrame(tl["data"])
                            if not df.empty:
                                # Format value column
                                if "value" in df.columns:
                                    max_val = df["value"].max()
                                    if max_val > 10000:
                                        df["value"] = df["value"].apply(
                                            lambda x: f"₹{x:,.0f}")
                                    elif max_val > 100:
                                        df["value"] = df["value"].apply(
                                            lambda x: f"{x:,.1f}")
                                st.dataframe(df, use_container_width=True,
                                             hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ROOT CAUSE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab_rca:
    st.subheader("🔎 Root Cause Analysis Agent")
    st.caption("AI investigates why a metric dropped — analyses region, category, channel, returns, and discounts")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        rca_region  = st.text_input("Region to investigate", value="Odisha", key="rca_region")
        rca_metric  = st.selectbox("Metric", ["revenue","orders","quantity"], key="rca_metric")
    with col2:
        rca_period  = st.text_input("Target period (YYYY-MM)", value="2024-07",
                                     help="Start month of the problem period (Q3 2024 = 2024-07)",
                                     key="rca_period")
        rca_compare = st.text_input("Compare period (YYYY-MM)", value="2024-04",
                                     help="Start month of a good period to compare with (Q2 2024 = 2024-04)",
                                     key="rca_compare")
    with col3:
        rca_q = st.text_area("Your question", height=120,
            value="Why did sales drop in Odisha in Q3 2024?",
            key="rca_question")

    if st.button("🔍 Investigate root cause", key="rca_btn", use_container_width=True):
        with st.spinner("🤖 AI is investigating across all dimensions..."):
            try:
                resp = requests.post(f"{API_URL}/root-cause", json={
                    "question":       rca_q,
                    "region":         rca_region,
                    "period":         rca_period,
                    "compare_period": rca_compare,
                    "metric":         rca_metric,
                    "db_path":        st.session_state.active_db
                }, timeout=60)
                st.session_state.rca_result = resp.json()
            except Exception as e:
                st.error(str(e))

    if "rca_result" in st.session_state:
        rca = st.session_state.rca_result
        st.divider()

        # ── LLM Analysis ──────────────────────────────────────────────────────
        st.markdown("### 🤖 AI Analysis")
        st.markdown(
            f'<div class="insight-box">{rca.get("llm_analysis","")}</div>',
            unsafe_allow_html=True
        )
        st.divider()

        # ── Dimension insights ────────────────────────────────────────────────
        insights = rca.get("insights",[])
        if insights:
            st.markdown("### 📌 Key findings by dimension")
            for ins in insights:
                sev   = ins.get("severity","medium")
                color = "#ef4444" if sev=="high" else ("#f59e0b" if sev=="medium" else "#10b981")
                icon  = "🔴" if sev=="high" else ("🟡" if sev=="medium" else "🟢")
                st.markdown(
                    f'<div style="border-left:4px solid {color};padding:10px 16px;'
                    f'margin:8px 0;border-radius:0 8px 8px 0;">'
                    f'{icon} <b>{ins["dimension"]}</b>: {ins["finding"]}'
                    f'</div>', unsafe_allow_html=True
                )

        st.divider()

        # ── Data charts ───────────────────────────────────────────────────────
        snaps = rca.get("data_snapshots",{})
        st.markdown("### 📊 Evidence charts")

        col1, col2 = st.columns(2)
        with col1:
            cat_data = snaps.get("by_category",[])
            if cat_data:
                cat_df = pd.DataFrame(cat_data)
                if "target_rev" in cat_df.columns and "compare_rev" in cat_df.columns:
                    fig = px.bar(cat_df, x="category",
                        y=["compare_rev","target_rev"],
                        title="Category: target vs comparison period",
                        barmode="group",
                        color_discrete_sequence=["#6366f1","#ef4444"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=320,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True, key="rca_cat")

        with col2:
            ch_data = snaps.get("by_channel",[])
            if ch_data:
                ch_df = pd.DataFrame(ch_data)
                if "target_rev" in ch_df.columns and "compare_rev" in ch_df.columns:
                    fig = px.bar(ch_df, x="channel",
                        y=["compare_rev","target_rev"],
                        title="Channel: target vs comparison period",
                        barmode="group",
                        color_discrete_sequence=["#6366f1","#ef4444"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=320,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True, key="rca_ch")

        col3, col4 = st.columns(2)
        with col3:
            city_data = snaps.get("by_city",[])
            if city_data:
                city_df = pd.DataFrame(city_data)
                if "target_rev" in city_df.columns and "compare_rev" in city_df.columns:
                    fig = px.bar(city_df, x="city",
                        y=["compare_rev","target_rev"],
                        title="City: target vs comparison period",
                        barmode="group",
                        color_discrete_sequence=["#6366f1","#ef4444"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=320,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True, key="rca_city")

        with col4:
            ret_data = snaps.get("returns",[])
            if ret_data:
                ret_df = pd.DataFrame(ret_data)
                if "return_count" in ret_df.columns:
                    fig = px.bar(ret_df, x="reason", y="return_count",
                        title="↩️ Returns by reason",
                        color_discrete_sequence=["#f59e0b"])
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)", height=320,
                        margin=dict(l=10,r=10,t=40,b=10))
                    fig.update_xaxes(showgrid=False, tickangle=20)
                    st.plotly_chart(fig, use_container_width=True, key="rca_ret")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — QUERY OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════
with tab_optimizer:
    st.subheader("⚡ Query Optimizer Agent")
    st.caption("Paste any SQL query and get performance optimization suggestions")
    st.divider()

    sql_input = st.text_area(
        "Paste your SQL query here",
        height = 160,
        value  = "SELECT * FROM sales WHERE region = 'Odisha'",
        key    = "opt_sql_input"
    )

    if st.button("⚡ Analyse query", key="opt_btn", use_container_width=True):
        if sql_input.strip():
            with st.spinner("Analysing query..."):
                try:
                    resp = requests.post(f"{API_URL}/optimize", json={
                        "sql":     sql_input,
                        "db_path": st.session_state.active_db
                    }, timeout=30)
                    st.session_state.opt_result = resp.json()
                except Exception as e:
                    st.error(str(e))

    if "opt_result" in st.session_state:
        opt = st.session_state.opt_result
        score = opt.get("score", 100)
        color = "#10b981" if score>=80 else ("#f59e0b" if score>=60 else "#ef4444")
        label = "Well optimized" if score>=80 else ("Needs work" if score>=60 else "Poor performance")

        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown(
                f'<div style="text-align:center;padding:20px;border-radius:12px;'
                f'border:2px solid {color}22">'
                f'<div style="font-size:3rem;font-weight:700;color:{color}">{score}</div>'
                f'<div style="color:{color}">/100 — {label}</div>'
                f'<div style="font-size:.85rem;color:#6b7280;margin-top:6px">'
                f'{opt.get("summary","")}</div>'
                f'</div>', unsafe_allow_html=True
            )

        st.divider()

        suggestions = opt.get("suggestions", [])
        if not suggestions:
            st.success("✅ No issues found — query looks good!")
        else:
            st.markdown(f"### Found {len(suggestions)} suggestions")
            for s in suggestions:
                sev   = s.get("severity","info")
                color = "#ef4444" if sev=="critical" else ("#f59e0b" if sev=="warning" else "#3b82f6")
                icon  = "🔴" if sev=="critical" else ("🟡" if sev=="warning" else "🔵")
                with st.expander(f"{icon} [{s.get('category','')}] {s.get('issue','')}"):
                    st.markdown(f"**Suggestion:** {s.get('suggestion','')}")
                    if s.get("example"):
                        st.code(s.get("example",""), language="sql")

        # Show optimized query hint
        st.divider()
        st.markdown("**💡 Try this optimized version:**")
        better_sql = sql_input
        if "SELECT *" in sql_input.upper():
            better_sql = better_sql.replace("SELECT *", "SELECT region, revenue, date, product")
        if "LIMIT" not in sql_input.upper():
            better_sql = better_sql.rstrip(";").rstrip() + "\nLIMIT 500"
        st.code(better_sql, language="sql")

        if st.button("▶️ Run optimized query", key="run_opt_btn"):
            with st.spinner("Running..."):
                result = query_backend(f"Run this SQL and show me results: {better_sql}")
                if result.get("data"):
                    df = pd.DataFrame(result["data"])
                    st.dataframe(df, use_container_width=True)
                    st.session_state.last_df = df


# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — ALERTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_alerts:
    st.subheader("🚨 Business Alerts")
    st.caption("Automatically detects revenue drops, high returns, excessive discounts, and low order volumes")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        rev_thresh  = st.slider("Revenue drop threshold %",  5,  50, 20, key="rev_thresh")
    with col2:
        ret_thresh  = st.slider("Return rate threshold %",   5,  30, 10, key="ret_thresh")
    with col3:
        disc_thresh = st.slider("Avg discount threshold %",  5,  40, 15, key="disc_thresh")

    if st.button("🔍 Check alerts now", key="alert_btn", use_container_width=True):
        with st.spinner("Scanning metrics..."):
            try:
                resp = requests.get(f"{API_URL}/alerts", params={
                    "db_path":                st.session_state.active_db,
                    "revenue_drop_threshold": rev_thresh,
                    "return_rate_threshold":  ret_thresh,
                    "discount_threshold":     disc_thresh
                }, timeout=30)
                st.session_state.alert_result = resp.json()
            except Exception as e:
                st.error(str(e))

    if "alert_result" in st.session_state:
        ar = st.session_state.alert_result
        st.caption(f"Last checked: {ar.get('checked_at','')}")

        alerts = ar.get("alerts", [])
        if not alerts:
            st.success(f"✅ {ar.get('summary','All clear — no alerts.')}")
        else:
            # Summary metrics
            critical = sum(1 for a in alerts if a["severity"]=="critical")
            warnings = sum(1 for a in alerts if a["severity"]=="warning")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total alerts",  len(alerts))
            c2.metric("🔴 Critical",   critical)
            c3.metric("🟡 Warnings",   warnings)
            st.divider()

            # Alert cards
            for alert in alerts:
                sev   = alert.get("severity","warning")
                color = "#ef4444" if sev=="critical" else "#f59e0b"
                icon  = "🔴" if sev=="critical" else "🟡"
                change = alert.get("change", 0)
                change_str = f" ({change:+.1f}%)" if change != 0 else ""

                with st.expander(
                    f"{icon} {alert.get('title','')} {change_str}",
                    expanded = sev=="critical"
                ):
                    st.markdown(
                        f'<div style="border-left:4px solid {color};'
                        f'padding:10px 16px;border-radius:0 8px 8px 0;">'
                        f'<b>Finding:</b> {alert.get("message","")}<br><br>'
                        f'<b>💡 Recommendation:</b> {alert.get("suggestion","")}'
                        f'</div>', unsafe_allow_html=True
                    )
                    c1, c2 = st.columns(2)
                    c1.metric("Current value", f"{alert.get('current',0):,.1f}")
                    c2.metric("Threshold",     f"{alert.get('threshold',0):,.1f}")

                    # Quick investigate button
                    if st.button(
                        f"🔎 Investigate in chat",
                        key = f"inv_{alert.get('title','').replace(' ','_')}",
                        use_container_width = True
                    ):
                        st.session_state.pending_question = (
                            f"Investigate: {alert.get('message','')}. "
                            f"Show me the breakdown."
                        )
                        st.rerun()



# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — QUERY HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("🕓 Query history")
    st.caption("All queries run across all sessions")
    st.divider()

    if st.button("🔄 Refresh history", key="refresh_hist", use_container_width=False):
        try:
            resp = requests.get(f"{API_URL}/history?limit=50", timeout=10)
            st.session_state.history_data = resp.json().get("queries",[])
        except Exception as e:
            st.error(str(e))

    # Auto-load on first visit
    if "history_data" not in st.session_state:
        try:
            resp = requests.get(f"{API_URL}/history?limit=50", timeout=10)
            st.session_state.history_data = resp.json().get("queries",[])
        except Exception:
            st.session_state.history_data = []

    history = st.session_state.history_data
    if not history:
        st.info("No query history yet. Ask some questions in the Chat tab first.")
    else:
        success_count = sum(1 for h in history if h.get("success"))
        fail_count    = len(history) - success_count

        c1, c2, c3 = st.columns(3)
        c1.metric("Total queries",    len(history))
        c2.metric("Successful",       success_count)
        c3.metric("Failed / blocked", fail_count)
        st.divider()

        for item in history:
            icon = "✅" if item.get("success") else "❌"
            with st.expander(f"{icon} {item.get('question','')[:80]}"):
                st.code(item.get("sql",""), language="sql")
                col1, col2 = st.columns(2)
                col1.caption(f"Rows returned: {item.get('rows',0)}")
                col2.caption(f"Time: {item.get('time','')[:19]}")