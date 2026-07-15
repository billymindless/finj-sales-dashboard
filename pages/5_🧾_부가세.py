"""부가세 신고 자료(신용카드매출전표 등 수령명세서) 페이지."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from utils.auth import require_auth
from utils.vat import (
    build_report_excel,
    build_vendor_summary,
    compute_totals,
    get_company_info,
    load_txns_for_period,
)

require_auth()

st.title("🧾 부가세 신고")
st.caption("카드 지출 명세를 기반으로 매입세액 공제 신고 자료를 생성합니다.")

company = get_company_info()
with st.expander("🏢 회사 사업자정보", expanded=not bool(company.get("biz_no"))):
    if company.get("biz_no"):
        st.write(
            f"**{company.get('name', '')}** (사업자번호: {company.get('biz_no', '-')}) · "
            f"대표 {company.get('owner', '-')} · {company.get('industry', '-')} / {company.get('item', '-')}"
        )
    else:
        st.info(
            "`.streamlit/secrets.toml`의 `[company]` 섹션(name, biz_no, owner, industry, item)을 채우면 "
            "신고서 헤더에 회사 정보가 자동 표시됩니다."
        )

st.markdown("---")

# ── 기간 선택 ────────────────────────────────────────────────────────────────
today = date.today()
years = list(range(today.year - 2, today.year + 1))

col_y, col_p, col_pv = st.columns([1, 1, 2])
with col_y:
    year = st.selectbox("연도", years, index=years.index(today.year))
with col_p:
    period_type = st.radio("기간 단위", ["분기", "월"], horizontal=True)
with col_pv:
    if period_type == "분기":
        quarter = st.selectbox(
            "분기",
            [1, 2, 3, 4],
            index=(today.month - 1) // 3,
            format_func=lambda q: f"{q}분기",
        )
        month = None
    else:
        month = st.selectbox("월", list(range(1, 13)), index=today.month - 1)
        quarter = None

txns = load_txns_for_period(year=int(year), quarter=quarter, month=month)

if not txns:
    st.warning("해당 기간의 카드 거래가 없습니다. 먼저 **카드 내역 업로드** 페이지에서 명세서를 등록하세요.")
    st.stop()

totals = compute_totals(txns)

st.markdown("### 요약")
m1, m2, m3, m4 = st.columns(4)
m1.metric("공제 공급가액", f"₩{totals['공제_공급가액']:,}")
m2.metric("공제 부가세", f"₩{totals['공제_부가세']:,}")
m3.metric("불공제 공급가액", f"₩{totals['불공제_공급가액']:,}")
m4.metric("불공제 부가세", f"₩{totals['불공제_부가세']:,}")

st.markdown("---")
st.markdown("### 사업자번호별 집계")

vendor_df = build_vendor_summary(txns)
if vendor_df.empty:
    st.info("집계할 거래가 없습니다.")
else:
    money_cols = ["공급가액", "부가세", "합계금액"]
    display = vendor_df.copy()
    for col in money_cols:
        display[col] = display[col].apply(lambda v: f"₩{int(v):,}")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 거래 명세 (전체)")

lines = pd.DataFrame(
    [
        {
            "거래일": t.get("txn_date"),
            "사업자번호": t.get("biz_no") or "",
            "가맹점": t.get("merchant") or "",
            "카테고리": f"{t.get('category_group') or ''} > {t.get('category') or ''}",
            "공제": "✓" if bool(t.get("vat_deductible", True)) else "✗",
            "공급가액": int(t.get("supply_value") or 0),
            "부가세": int(t.get("vat") or 0),
            "합계금액": int(t.get("amount") or 0),
        }
        for t in sorted(txns, key=lambda x: (x.get("txn_date") or ""))
    ]
)
display_lines = lines.copy()
for col in ("공급가액", "부가세", "합계금액"):
    display_lines[col] = display_lines[col].apply(lambda v: f"₩{int(v):,}")
st.dataframe(display_lines, use_container_width=True, hide_index=True, height=420)

st.markdown("---")

report_bytes = build_report_excel(
    year=int(year), quarter=quarter, month=month, txns=txns
)
period_label = f"{year}년_{quarter}분기" if quarter is not None else f"{year}-{month:02d}"
st.download_button(
    "⬇️ 부가세 신고 엑셀 다운로드 (.xlsx)",
    data=report_bytes,
    file_name=f"부가세신고_{period_label}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
