import streamlit as st
import pandas as pd
import io
from utils.auth import require_auth
from utils.database import load_all_data, delete_month_data
from utils.calculations import calculate_derived

require_auth()

st.title("📋 데이터 테이블")
st.caption("전체 월별 원본 데이터 조회 및 관리")

all_data = load_all_data()

if not all_data:
    st.info("입력된 데이터가 없습니다.")
    st.stop()

months = sorted(all_data.keys())

# ── 요약 테이블 ────────────────────────────────────────────────────────────────
st.markdown("### 월별 요약")

rows = []
for ym in months:
    d = calculate_derived(all_data[ym])
    rows.append({
        "연월": ym,
        "합산매출": d["합산매출"],
        "오늘의집매출": d["오늘의집매출"],
        "자사몰매출": d["자사몰매출"],
        "총광고비": d["총광고비"],
        "오늘의집광고": d["오늘의집광고"],
        "자사몰광고": d["자사몰광고"],
        "총고정비": d["총고정비"],
        "총변동비": d["총변동비"],
        "매입금액": d["매입금액"],
        "총지출": d["총지출"],
        "영업이익": d["영업이익"],
        "자사몰ROAS": round(d["자사몰ROAS"], 2) if d["자사몰ROAS"] else None,
        "오늘의집ROAS": round(d["오늘의집ROAS"], 2) if d["오늘의집ROAS"] else None,
        "광고비율(%)": round(d["광고비율"], 1) if d["광고비율"] else None,
        "마진율(%)": round(d["마진율"], 1) if d["마진율"] else None,
    })

df = pd.DataFrame(rows).set_index("연월")

money_cols = ["합산매출", "오늘의집매출", "자사몰매출", "총광고비", "오늘의집광고", "자사몰광고",
              "총고정비", "총변동비", "매입금액", "총지출", "영업이익"]

styled = df.style.format(
    {col: "₩{:,.0f}" for col in money_cols if col in df.columns}
).format(
    {col: "{:.2f}" for col in ["자사몰ROAS", "오늘의집ROAS"] if col in df.columns}
).format(
    {col: "{:.1f}%" for col in ["광고비율(%)", "마진율(%)"] if col in df.columns}
).map(
    lambda v: "color:#16A34A;font-weight:600" if isinstance(v, (int, float)) and v >= 0
    else ("color:#DC2626;font-weight:600" if isinstance(v, (int, float)) and v < 0 else ""),
    subset=["영업이익"] if "영업이익" in df.columns else [],
)

st.dataframe(styled, use_container_width=True, height=400)

# ── Excel 다운로드 ─────────────────────────────────────────────────────────────
st.markdown("---")
col_dl, col_del = st.columns([3, 1])

with col_dl:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="요약")

        # 원본 데이터 시트
        raw_rows = []
        for ym in months:
            md = all_data[ym]
            row = {"연월": ym}
            for category, items in md.items():
                for key, val in items.items():
                    row[f"{category}_{key}"] = val
            raw_rows.append(row)
        pd.DataFrame(raw_rows).set_index("연월").to_excel(writer, sheet_name="원본데이터")

    buffer.seek(0)
    st.download_button(
        label="⬇️ Excel 다운로드 (.xlsx)",
        data=buffer,
        file_name="핀즈_영업데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ── 월별 삭제 ─────────────────────────────────────────────────────────────────
with col_del:
    with st.expander("🗑️ 데이터 삭제"):
        del_month = st.selectbox("삭제할 월", options=months[::-1], key="del_sel")
        if st.button("삭제", type="secondary", use_container_width=True):
            if delete_month_data(del_month):
                st.success(f"{del_month} 삭제 완료")
                st.rerun()

# ── 세부 항목 보기 ─────────────────────────────────────────────────────────────
st.markdown("---")

col_title, col_edit = st.columns([4, 1])
with col_title:
    st.markdown("### 월별 세부 항목")

detail_month = st.selectbox("조회할 월", options=months[::-1], key="detail_sel")

with col_edit:
    st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
    if st.button("✏️ 수정하기", use_container_width=True, type="secondary"):
        year, month = detail_month.split("-")
        st.session_state["goto_year"] = int(year)
        st.session_state["goto_month"] = f"{int(month):02d}"
        st.switch_page("pages/2_✏️_데이터입력.py")
detail_data = all_data[detail_month]

tab1, tab2, tab3, tab4, tab5 = st.tabs(["매출", "광고비", "고정비", "변동비", "매입"])

label_maps = {
    "매출": {"오늘의집": "오늘의집 매출", "자사몰": "자사몰 매출"},
    "광고비": {
        "오늘의집_광고": "오늘의집", "자사몰_광고": "자사몰",
        "메타_광고": "메타(인스타)", "네이버_광고": "네이버", "기타_광고": "기타",
    },
    "고정비": {
        "급여": "급여", "4대보험": "4대보험", "퇴직연금": "퇴직연금", "식대": "식대",
        "임대료": "임대료", "창고료": "창고료", "전기료": "전기료", "관리비": "관리비",
        "이자_하나은행": "이자(하나은행)", "세무사비": "세무사비",
        "솔루션구독비": "솔루션구독비", "통신비": "통신비", "기타고정비": "기타고정비",
    },
    "변동비": {
        "택배비": "택배비", "설치배송비": "설치배송비", "반품비": "반품비",
        "포장재비": "포장재비", "PG수수료": "PG수수료", "플랫폼수수료": "플랫폼수수료",
        "AS비": "A/S비", "불량처리비": "불량처리비", "촬영비": "촬영비",
        "인플루언서비": "인플루언서비", "출장교통비": "출장·교통비",
        "접대비": "접대비", "소모품비": "소모품비", "기타변동비": "기타변동비",
    },
    "매입": {"매입금액": "매입금액"},
}


def render_category_table(tab, category):
    with tab:
        items = detail_data.get(category, {})
        lmap = label_maps.get(category, {})
        rows = [
            {"항목": lmap.get(k, k), "금액 (₩)": v}
            for k, v in items.items()
        ]
        tdf = pd.DataFrame(rows)
        tdf["금액 (₩)"] = tdf["금액 (₩)"].apply(lambda x: f"₩{x:,.0f}")
        st.dataframe(tdf, use_container_width=True, hide_index=True)
        total = sum(items.values())
        st.markdown(f"**합계: ₩{total:,.0f}**")


render_category_table(tab1, "매출")
render_category_table(tab2, "광고비")
render_category_table(tab3, "고정비")
render_category_table(tab4, "변동비")
render_category_table(tab5, "매입")
