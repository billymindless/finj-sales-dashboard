"""카드사 지출 명세서 업로드 · 자동 분류 · 월별 반영 페이지."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import require_auth
from utils.classifier import (
    ALLOWED_CATEGORIES,
    classify_transactions,
    override_and_learn,
)
from utils.database import (
    apply_transactions_to_month,
    delete_card_transactions_by_month,
    save_card_transactions,
)
from utils.excel_parser import (
    STANDARD_FIELDS,
    infer_year_month,
    list_sheets,
    normalize_rows,
    parse_excel,
)

require_auth()

st.title("🧾 카드 내역 업로드")
st.caption("카드사 엑셀 명세서를 업로드하면 AI가 자동 분류하고 월별 집계에 반영합니다.")

with st.sidebar:
    st.markdown("### 📤 카드 내역 업로드")
    st.caption("Step 1. 파일 업로드")
    st.caption("Step 2. 컬럼 자동 매핑 확인")
    st.caption("Step 3. AI 자동 분류")
    st.caption("Step 4. 검토·교정 후 저장")


uploaded = st.file_uploader(
    "카드사 명세서 엑셀 (.xlsx)",
    type=["xlsx", "xls"],
    accept_multiple_files=False,
)

if not uploaded:
    st.info("좌측 사이드바 또는 위 영역에 카드사 명세서 파일을 올려주세요. 여러 카드사 양식을 지원합니다.")
    st.stop()

file_bytes = uploaded.getvalue()

sheet_names = list_sheets(file_bytes)
sheet = st.selectbox("시트 선택", sheet_names, index=0)

st.markdown("---")
st.markdown("### 1) 파싱 & 컬럼 매핑")

parsed = parse_excel(file_bytes, sheet=sheet)

for w in parsed.warnings:
    st.warning(w)

with st.expander("원본 미리보기 (상위 20행)", expanded=False):
    st.dataframe(parsed.df.head(20), use_container_width=True, hide_index=True)

st.markdown("#### 표준 필드 매핑")
st.caption(f"자동 감지된 헤더 행: **{parsed.header_row + 1}행**")

col_options = ["(사용 안 함)"] + parsed.original_columns
mapping: dict[str, str | None] = {}
map_cols = st.columns(4)
for i, field in enumerate(STANDARD_FIELDS):
    with map_cols[i % 4]:
        default = parsed.detected_mapping.get(field)
        default_idx = col_options.index(default) if default in col_options else 0
        sel = st.selectbox(
            field,
            options=col_options,
            index=default_idx,
            key=f"map_{field}",
        )
        mapping[field] = None if sel == "(사용 안 함)" else sel

missing = [f for f in ("txn_date", "merchant", "amount") if not mapping.get(f)]
if missing:
    st.error(f"필수 컬럼을 지정해주세요: {', '.join(missing)}")
    st.stop()

try:
    normalized = normalize_rows(parsed.df, mapping)
except ValueError as e:
    st.error(str(e))
    st.stop()

if normalized.empty:
    st.warning("정규화 후 유효한 거래가 없습니다. 컬럼 매핑을 다시 확인하세요.")
    st.stop()

st.success(f"정규화 완료: {len(normalized)}건 (총 금액 ₩{int(normalized['amount'].sum()):,})")

with st.expander("정규화 결과 미리보기", expanded=False):
    show = normalized.drop(columns=["raw"], errors="ignore").head(30)
    st.dataframe(show, use_container_width=True, hide_index=True)

# ── 대상 월 선택 ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 2) 대상 월 & 분류")

inferred_ym = infer_year_month(normalized) or ""
default_ym = st.session_state.get("upload_year_month", inferred_ym)
year_month = st.text_input(
    "반영할 연월 (YYYY-MM)",
    value=default_ym,
    max_chars=7,
    help="거래일자로부터 자동 추정됩니다. 필요 시 수정하세요.",
    key="upload_year_month",
)

if not year_month or len(year_month) != 7 or year_month[4] != "-":
    st.warning("YYYY-MM 형식으로 입력하세요.")
    st.stop()

run_classify = st.button("🤖 AI 자동 분류 실행", type="primary", use_container_width=True)

if run_classify or "classified_df" in st.session_state and st.session_state.get("classified_source_key") == uploaded.name + sheet:
    if run_classify:
        with st.spinner("Gemini로 거래를 분류하는 중..."):
            txns = normalized.to_dict(orient="records")
            classified = classify_transactions(txns)
        cdf = pd.DataFrame(classified)
        cdf["txn_date"] = pd.to_datetime(cdf["txn_date"]).dt.date
        st.session_state["classified_df"] = cdf
        st.session_state["classified_source_key"] = uploaded.name + sheet
    cdf: pd.DataFrame = st.session_state["classified_df"]

    st.markdown("---")
    st.markdown("### 3) 검토 · 교정")
    st.caption("카테고리·매입세액공제 여부를 확인하고 필요 시 직접 교정하세요. 교정 결과는 다음 업로드부터 자동 적용됩니다.")

    all_cats: list[str] = []
    for group, items in ALLOWED_CATEGORIES.items():
        for cat in items:
            all_cats.append(cat)

    editable = cdf.copy()
    editable["편집가능"] = editable.apply(
        lambda r: f"{r['category_group']} > {r['category']}", axis=1
    )
    option_labels = [f"{g} > {c}" for g, cats in ALLOWED_CATEGORIES.items() for c in cats]

    edited = st.data_editor(
        editable[
            [
                "txn_date",
                "merchant",
                "biz_no",
                "amount",
                "supply_value",
                "vat",
                "편집가능",
                "vat_deductible",
                "confidence",
                "classify_source",
                "classify_reason",
            ]
        ].rename(columns={"편집가능": "카테고리"}),
        column_config={
            "txn_date": st.column_config.DateColumn("거래일"),
            "merchant": st.column_config.TextColumn("가맹점", width="medium"),
            "biz_no": st.column_config.TextColumn("사업자번호", width="small"),
            "amount": st.column_config.NumberColumn("금액", format="₩%d"),
            "supply_value": st.column_config.NumberColumn("공급가액", format="₩%d"),
            "vat": st.column_config.NumberColumn("부가세", format="₩%d"),
            "카테고리": st.column_config.SelectboxColumn(
                "카테고리",
                options=option_labels,
                required=True,
            ),
            "vat_deductible": st.column_config.CheckboxColumn("공제"),
            "confidence": st.column_config.NumberColumn("신뢰도", format="%.2f"),
            "classify_source": st.column_config.TextColumn("분류출처", width="small"),
            "classify_reason": st.column_config.TextColumn("사유", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        height=520,
        key="edit_table",
    )

    edited = edited.copy()
    edited[["category_group", "category"]] = edited["카테고리"].str.split(" > ", expand=True)
    for col in ("memo", "card_name", "raw"):
        if col in cdf.columns and col not in edited.columns:
            edited[col] = cdf[col].values

    st.markdown("#### 그룹별 합계(미리보기)")
    prev = (
        edited.groupby(["category_group", "category"])["amount"].sum().reset_index()
    )
    st.dataframe(prev, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 4) 저장 · 월별 반영")

    mode_label = st.radio(
        "월별 집계 반영 방식",
        options=["기존 값에 합산 (add)", "카드거래 값으로 덮어쓰기 (replace)"],
        index=0,
        horizontal=True,
    )
    mode = "add" if mode_label.startswith("기존") else "replace"

    clear_existing = st.checkbox(
        f"{year_month}의 기존 카드 거래를 삭제하고 새로 저장 (중복 방지)",
        value=True,
    )

    if st.button("💾 저장 & 월별 반영", type="primary", use_container_width=True):
        if clear_existing:
            deleted = delete_card_transactions_by_month(year_month)
            if deleted:
                st.info(f"{year_month} 기존 카드 거래 {deleted}건 삭제")

        rows_to_save: list[dict] = []
        for _, r in edited.iterrows():
            row = {
                "txn_date": r.get("txn_date"),
                "merchant": r.get("merchant"),
                "biz_no": r.get("biz_no"),
                "card_name": r.get("card_name"),
                "amount": int(r.get("amount") or 0),
                "supply_value": int(r.get("supply_value") or 0),
                "vat": int(r.get("vat") or 0),
                "category_group": r.get("category_group"),
                "category": r.get("category"),
                "vat_deductible": bool(r.get("vat_deductible", True)),
                "confidence": float(r.get("confidence") or 0),
                "classify_source": r.get("classify_source"),
                "classify_reason": r.get("classify_reason"),
                "memo": r.get("memo"),
                "raw": r.get("raw") if isinstance(r.get("raw"), dict) else {},
            }
            rows_to_save.append(row)
            override_and_learn(row)

        saved = save_card_transactions(year_month, rows_to_save)
        apply_transactions_to_month(year_month, rows_to_save, mode=mode)

        st.success(
            f"✅ {saved}건 저장 완료 · {year_month} 집계에 '{mode}' 방식으로 반영되었습니다."
        )
        st.balloons()
        st.session_state.pop("classified_df", None)
        st.session_state.pop("classified_source_key", None)
