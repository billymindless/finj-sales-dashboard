import streamlit as st
from datetime import date
from utils.auth import require_auth
from utils.database import load_all_data, save_month_data, get_empty_month
from utils.calculations import calculate_derived

require_auth()

st.title("✏️ 데이터 입력")
st.caption("월별 매출·광고비·비용을 입력하고 저장하세요.")

# ── 월 선택 ───────────────────────────────────────────────────────────────────
today = date.today()
year_options = list(range(today.year - 1, today.year + 2))
month_options = [f"{m:02d}" for m in range(1, 13)]

with st.sidebar:
    st.markdown("### 📅 월 선택")
    sel_year = st.selectbox("년도", year_options, index=year_options.index(today.year))
    sel_month = st.selectbox("월", month_options, index=today.month - 1)

year_month = f"{sel_year}-{sel_month}"
st.markdown(f"### {year_month} 데이터 입력")
st.markdown("---")

# 기존 데이터 로드 (있으면 불러오기)
all_data = load_all_data()
existing = all_data.get(year_month, get_empty_month())


def num_input(label, value, key, step=10000, prefix="₩"):
    return st.number_input(
        f"{label} ({prefix})" if prefix else label,
        value=int(value),
        step=step,
        format="%d",
        key=key,
    )


# ── 매출 ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">💰 매출</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    today_house = num_input("오늘의집 매출", existing["매출"].get("오늘의집", 0), "rev_today")
with col2:
    own_mall = num_input("자사몰 매출", existing["매출"].get("자사몰", 0), "rev_own")

합산매출 = today_house + own_mall
st.info(f"합산 매출: ₩{합산매출:,.0f}")

st.markdown("---")

# ── 광고비 ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📣 광고비</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    ad_today = num_input("오늘의집 광고", existing["광고비"].get("오늘의집_광고", 0), "ad_today")
    ad_naver = num_input("네이버 광고", existing["광고비"].get("네이버_광고", 0), "ad_naver")
with col2:
    ad_own = num_input("자사몰 광고", existing["광고비"].get("자사몰_광고", 0), "ad_own")
    ad_etc = num_input("기타 광고", existing["광고비"].get("기타_광고", 0), "ad_etc")
with col3:
    ad_meta = num_input("메타(인스타) 광고", existing["광고비"].get("메타_광고", 0), "ad_meta")

총광고비 = ad_today + ad_own + ad_meta + ad_naver + ad_etc
자사몰ROAS = 합산매출 and own_mall / ad_own if ad_own else None
오늘의집ROAS = 합산매출 and today_house / ad_today if ad_today else None

c1, c2, c3 = st.columns(3)
c1.metric("총 광고비", f"₩{총광고비:,.0f}")
c2.metric("자사몰 ROAS", f"{자사몰ROAS:.2f}" if 자사몰ROAS else "—")
c3.metric("오늘의집 ROAS", f"{오늘의집ROAS:.2f}" if 오늘의집ROAS else "—")

st.markdown("---")

# ── 고정비 ────────────────────────────────────────────────────────────────────
with st.expander("🏢 고정비 입력", expanded=True):
    g = existing["고정비"]
    col1, col2, col3 = st.columns(3)
    with col1:
        salary      = num_input("급여",       g.get("급여", 0),           "g_salary",      step=100000)
        insurance   = num_input("4대보험",     g.get("4대보험", 0),        "g_insurance",   step=50000)
        pension     = num_input("퇴직연금",    g.get("퇴직연금", 0),       "g_pension",     step=50000)
        meal        = num_input("식대",        g.get("식대", 0),           "g_meal",        step=10000)
    with col2:
        rent        = num_input("임대료",      g.get("임대료", 900000),    "g_rent",        step=50000)
        warehouse   = num_input("창고료",      g.get("창고료", 0),         "g_warehouse",   step=50000)
        elec        = num_input("전기료",      g.get("전기료", 200000),    "g_elec",        step=10000)
        mgmt_fee    = num_input("관리비",      g.get("관리비", 0),         "g_mgmt",        step=10000)
    with col3:
        interest    = num_input("이자(하나은행)", g.get("이자_하나은행", 1200000), "g_interest", step=100000)
        accountant  = num_input("세무사비",    g.get("세무사비", 0),       "g_acct",        step=50000)
        software    = num_input("솔루션구독비", g.get("솔루션구독비", 0),  "g_sw",          step=10000)
        telecom     = num_input("통신비",      g.get("통신비", 0),         "g_tel",         step=10000)
        other_fixed = num_input("기타고정비",  g.get("기타고정비", 0),     "g_other",       step=10000)

    총고정비 = salary + insurance + pension + meal + rent + warehouse + elec + mgmt_fee + interest + accountant + software + telecom + other_fixed
    st.info(f"고정비 합계: ₩{총고정비:,.0f}")

st.markdown("---")

# ── 변동비 ────────────────────────────────────────────────────────────────────
with st.expander("📦 변동비 입력", expanded=True):
    v = existing["변동비"]
    col1, col2, col3 = st.columns(3)
    with col1:
        delivery    = num_input("택배비",        v.get("택배비", 0),          "v_del",    step=10000)
        install_del = num_input("설치배송비",     v.get("설치배송비", 0),      "v_inst",   step=10000)
        return_cost = num_input("반품비",        v.get("반품비", 0),          "v_ret",    step=10000)
        packaging   = num_input("포장재비",      v.get("포장재비", 0),        "v_pack",   step=10000)
    with col2:
        pg_fee      = num_input("PG수수료",      v.get("PG수수료", 0),        "v_pg",     step=10000)
        platform_fee= num_input("플랫폼수수료",   v.get("플랫폼수수료", 0),   "v_plat",   step=10000)
        as_cost     = num_input("A/S비",         v.get("AS비", 0),            "v_as",     step=10000)
        defect_cost = num_input("불량처리비",     v.get("불량처리비", 0),      "v_defect", step=10000)
    with col3:
        photo_cost  = num_input("촬영비",        v.get("촬영비", 0),          "v_photo",  step=10000)
        influencer  = num_input("인플루언서비",   v.get("인플루언서비", 0),   "v_infl",   step=10000)
        travel      = num_input("출장·교통비",    v.get("출장교통비", 0),      "v_travel", step=10000)
        entertain   = num_input("접대비",        v.get("접대비", 0),          "v_entert", step=10000)
        supplies    = num_input("소모품비",       v.get("소모품비", 0),        "v_supply", step=10000)
        other_var   = num_input("기타변동비",     v.get("기타변동비", 0),      "v_other",  step=10000)

    총변동비 = (delivery + install_del + return_cost + packaging +
               pg_fee + platform_fee + as_cost + defect_cost +
               photo_cost + influencer + travel + entertain + supplies + other_var)
    st.info(f"변동비 합계: ₩{총변동비:,.0f}")

st.markdown("---")

# ── 매입 ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🛒 매입금액</div>', unsafe_allow_html=True)
purchase = num_input("매입금액", existing["매입"].get("매입금액", 0), "purchase", step=100000)

st.markdown("---")

# ── 미리보기 계산 ─────────────────────────────────────────────────────────────
total_cost   = 총광고비 + 총고정비 + 총변동비 + purchase
영업이익      = 합산매출 - total_cost
마진율        = (영업이익 / 합산매출 * 100) if 합산매출 > 0 else 0

st.markdown("#### 📋 입력 내용 미리보기")
p1, p2, p3, p4, p5 = st.columns(5)
p1.metric("합산 매출",   f"₩{합산매출:,.0f}")
p2.metric("총 비용",     f"₩{total_cost:,.0f}")
p3.metric("영업이익",    f"₩{영업이익:,.0f}", delta="흑자" if 영업이익 >= 0 else "적자")
p4.metric("마진율",      f"{마진율:.1f}%")
p5.metric("총 광고비율", f"{(총광고비 / 합산매출 * 100):.1f}%" if 합산매출 > 0 else "—")

st.markdown("---")

# ── 저장 ─────────────────────────────────────────────────────────────────────
if st.button("💾 저장", type="primary", use_container_width=True):
    month_data = {
        "매출": {"오늘의집": today_house, "자사몰": own_mall},
        "광고비": {
            "오늘의집_광고": ad_today,
            "자사몰_광고": ad_own,
            "메타_광고": ad_meta,
            "네이버_광고": ad_naver,
            "기타_광고": ad_etc,
        },
        "고정비": {
            "급여": salary, "4대보험": insurance, "퇴직연금": pension, "식대": meal,
            "임대료": rent, "창고료": warehouse, "전기료": elec, "관리비": mgmt_fee,
            "이자_하나은행": interest, "세무사비": accountant, "솔루션구독비": software,
            "통신비": telecom, "기타고정비": other_fixed,
        },
        "변동비": {
            "택배비": delivery, "설치배송비": install_del, "반품비": return_cost,
            "포장재비": packaging, "PG수수료": pg_fee, "플랫폼수수료": platform_fee,
            "AS비": as_cost, "불량처리비": defect_cost, "촬영비": photo_cost,
            "인플루언서비": influencer, "출장교통비": travel, "접대비": entertain,
            "소모품비": supplies, "기타변동비": other_var,
        },
        "매입": {"매입금액": purchase},
    }
    if save_month_data(year_month, month_data):
        st.success(f"✅ {year_month} 데이터가 저장되었습니다!")
        st.balloons()
    else:
        st.error("저장에 실패했습니다. 다시 시도하세요.")
