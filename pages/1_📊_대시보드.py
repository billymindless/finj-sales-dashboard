import streamlit as st
from utils.auth import require_auth
from utils.database import load_all_data
from utils.calculations import calculate_derived, build_summary_df, ROAS_TARGETS
from utils import charts

require_auth()

st.title("📊 대시보드")
st.caption("월별 매출·비용·ROAS 시각화")

all_data = load_all_data()

if not all_data:
    st.info("데이터가 없습니다. **✏️ 데이터 입력** 페이지에서 데이터를 추가하세요.")
    st.stop()

months = sorted(all_data.keys())
df = build_summary_df(all_data)


# ── 필터 ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔧 설정")
    selected_month = st.selectbox("기준 월 (KPI / 파이 차트)", options=months[::-1], index=0)
    target_자사몰 = st.number_input("자사몰 ROAS 목표", value=ROAS_TARGETS["자사몰"], step=0.1, format="%.1f")
    target_오늘의집 = st.number_input("오늘의집 ROAS 목표", value=ROAS_TARGETS["오늘의집"], step=0.5, format="%.1f")

derived = calculate_derived(all_data[selected_month])


def fmt(v, prefix="₩"):
    if v is None:
        return "N/A"
    return f"{prefix}{v:,.0f}"


def roas_color(v, target):
    if v is None:
        return "kpi-warn"
    return "kpi-pos" if v >= target else "kpi-neg"


# ── KPI 카드 ─────────────────────────────────────────────────────────────────
st.markdown(f"#### {selected_month} 핵심 지표")
c1, c2, c3, c4, c5, c6 = st.columns(6)

cards = [
    (c1, "합산 매출",       fmt(derived["합산매출"]),                        ""),
    (c2, "영업이익",        fmt(derived["영업이익"]),
     "kpi-pos" if derived["영업이익"] >= 0 else "kpi-neg"),
    (c3, "마진율",
     f"{derived['마진율']:.1f}%" if derived["마진율"] is not None else "N/A",
     "kpi-pos" if (derived["마진율"] or 0) >= 0 else "kpi-neg"),
    (c4, "자사몰 ROAS",
     f"{derived['자사몰ROAS']:.2f}" if derived["자사몰ROAS"] else "N/A",
     roas_color(derived["자사몰ROAS"], target_자사몰)),
    (c5, "오늘의집 ROAS",
     f"{derived['오늘의집ROAS']:.2f}" if derived["오늘의집ROAS"] else "N/A",
     roas_color(derived["오늘의집ROAS"], target_오늘의집)),
    (c6, "총 광고비",       fmt(derived["총광고비"]),                        ""),
]

for col, label, value, css in cards:
    with col:
        st.markdown(
            f"""<div class="kpi-card">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value {css}">{value}</div>
                </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── 매출 & 비용 추이 ─────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2])
with col_left:
    st.plotly_chart(charts.revenue_trend_chart(df), use_container_width=True)
with col_right:
    st.plotly_chart(charts.cost_breakdown_pie(all_data[selected_month], selected_month),
                    use_container_width=True)

# ── ROAS 추이 & 비용 구성 ─────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        charts.roas_trend_chart(df, target_자사몰, target_오늘의집),
        use_container_width=True,
    )
with col_b:
    st.plotly_chart(charts.cost_trend_chart(df), use_container_width=True)

# ── 광고채널별 집행금액 ────────────────────────────────────────────────────────
st.plotly_chart(
    charts.ad_channel_bar(all_data[selected_month], selected_month),
    use_container_width=True,
)

# ── 요약 테이블 ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 전체 월별 요약")

import pandas as pd

display_cols = {
    "합산매출": "합산매출",
    "오늘의집매출": "오늘의집",
    "자사몰매출": "자사몰",
    "총광고비": "광고비",
    "총고정비": "고정비",
    "총변동비": "변동비",
    "매입금액": "매입",
    "영업이익": "영업이익",
    "자사몰ROAS": "자사몰ROAS",
    "오늘의집ROAS": "오늘ROAS",
    "광고비율": "광고비율(%)",
}
show_df = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)

def style_profit(val):
    if pd.isna(val):
        return ""
    try:
        return "color: #16A34A; font-weight:600" if float(val) >= 0 else "color: #DC2626; font-weight:600"
    except Exception:
        return ""

styled = show_df.style.format(
    {
        col: "{:,.0f}" for col in ["합산매출", "오늘의집", "자사몰", "광고비", "고정비", "변동비", "매입", "영업이익"]
        if col in show_df.columns
    }
).format(
    {
        col: "{:.2f}" for col in ["자사몰ROAS", "오늘ROAS"]
        if col in show_df.columns
    }
).format(
    {
        col: "{:.1f}%" for col in ["광고비율(%)"]
        if col in show_df.columns
    }
).map(style_profit, subset=["영업이익"] if "영업이익" in show_df.columns else [])

st.dataframe(styled, use_container_width=True)
