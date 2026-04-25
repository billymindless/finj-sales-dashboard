import streamlit as st

st.set_page_config(
    page_title="핀즈 영업 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 공통 CSS ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', 'Malgun Gothic', sans-serif; }

    /* KPI 카드 */
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border-left: 4px solid #2563EB;
    }
    .kpi-label { font-size: 0.8rem; color: #64748B; font-weight: 500; margin-bottom: 4px; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: #1E293B; }
    .kpi-sub   { font-size: 0.78rem; color: #94A3B8; margin-top: 2px; }
    .kpi-pos   { color: #16A34A !important; }
    .kpi-neg   { color: #DC2626 !important; }
    .kpi-warn  { color: #D97706 !important; }

    /* 섹션 헤더 */
    .section-header {
        font-size: 1rem; font-weight: 600; color: #1E293B;
        border-left: 3px solid #2563EB; padding-left: 10px;
        margin: 1.2rem 0 0.8rem 0;
    }

    /* 사이드바 로그아웃 버튼 */
    .stButton > button { border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 인증 ──────────────────────────────────────────────────────────────────────
from utils.auth import require_auth
require_auth()

# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 핀즈 대시보드")
    st.markdown("---")
    st.caption("FINJ Sales Dashboard v1.0")

    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ── 홈 콘텐츠 ────────────────────────────────────────────────────────────────
from utils.database import load_all_data
from utils.calculations import calculate_derived, build_summary_df, ROAS_TARGETS


def fmt(value, prefix="₩"):
    if value is None:
        return "N/A"
    return f"{prefix}{value:,.0f}"


def roas_color(value, target):
    if value is None:
        return "kpi-warn"
    return "kpi-pos" if value >= target else "kpi-neg"


st.title("📊 핀즈 영업 대시보드")
st.caption("좌측 메뉴에서 페이지를 선택하거나, 아래에서 최근 실적을 확인하세요.")
st.markdown("---")

all_data = load_all_data()

if not all_data:
    st.info("📝 아직 입력된 데이터가 없습니다. **데이터 입력** 페이지에서 첫 번째 월 데이터를 추가하세요.")
    st.markdown(
        """
        ### 시작 방법
        1. 좌측 사이드바 → **✏️ 데이터 입력** 클릭
        2. 월 선택 후 매출·비용 입력
        3. **저장** 버튼 클릭
        4. **📊 대시보드** 에서 시각화 확인
        """
    )
else:
    latest_month = sorted(all_data.keys())[-1]
    derived = calculate_derived(all_data[latest_month])
    df = build_summary_df(all_data)

    st.markdown(f"#### 최근 월 요약 — {latest_month}")

    c1, c2, c3, c4, c5 = st.columns(5)

    cards = [
        (c1, "합산 매출", fmt(derived["합산매출"]), ""),
        (c2, "영업이익",  fmt(derived["영업이익"]),
         "kpi-pos" if derived["영업이익"] >= 0 else "kpi-neg"),
        (c3, "자사몰 ROAS",
         f"{derived['자사몰ROAS']:.2f}" if derived["자사몰ROAS"] else "N/A",
         roas_color(derived["자사몰ROAS"], ROAS_TARGETS["자사몰"])),
        (c4, "오늘의집 ROAS",
         f"{derived['오늘의집ROAS']:.2f}" if derived["오늘의집ROAS"] else "N/A",
         roas_color(derived["오늘의집ROAS"], ROAS_TARGETS["오늘의집"])),
        (c5, "총 광고비", fmt(derived["총광고비"]), ""),
    ]

    for col, label, value, css_cls in cards:
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value {css_cls}">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown("#### 연간 누적 현황")

    cum1, cum2, cum3 = st.columns(3)
    with cum1:
        total_revenue = df["합산매출"].sum()
        st.metric("누적 합산매출", fmt(total_revenue))
    with cum2:
        total_profit = df["영업이익"].sum()
        st.metric("누적 영업이익", fmt(total_profit),
                  delta="흑자" if total_profit >= 0 else "적자")
    with cum3:
        total_ad = df["총광고비"].sum()
        st.metric("누적 광고비", fmt(total_ad))

    st.markdown("---")
    st.info("📈 자세한 차트는 좌측 메뉴에서 **📊 대시보드** 를 클릭하세요.")
