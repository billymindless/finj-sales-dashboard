"""부가세(매입세액) 신고 자료 생성 유틸."""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import streamlit as st

from utils.database import load_card_transactions


def _parse_ym(ym: str) -> tuple[int, int]:
    y, m = ym.split("-")
    return int(y), int(m)


def _quarter_months(year: int, quarter: int) -> list[str]:
    start_month = (quarter - 1) * 3 + 1
    return [f"{year:04d}-{start_month + i:02d}" for i in range(3)]


def load_txns_for_period(
    year: int,
    quarter: Optional[int] = None,
    month: Optional[int] = None,
) -> list[dict]:
    if quarter is not None:
        yms = _quarter_months(year, quarter)
    elif month is not None:
        yms = [f"{year:04d}-{month:02d}"]
    else:
        yms = [f"{year:04d}-{m:02d}" for m in range(1, 13)]

    out: list[dict] = []
    for ym in yms:
        out.extend(load_card_transactions(ym))
    return out


def build_vendor_summary(txns: list[dict]) -> pd.DataFrame:
    """사업자번호(없으면 가맹점명) 단위로 공급가액/부가세/건수 집계."""
    rows = []
    for t in txns:
        rows.append(
            {
                "사업자번호": t.get("biz_no") or "(미상)",
                "가맹점": t.get("merchant") or "",
                "카테고리": f"{t.get('category_group') or ''} > {t.get('category') or ''}",
                "공제여부": bool(t.get("vat_deductible", True)),
                "공급가액": int(t.get("supply_value") or 0),
                "부가세": int(t.get("vat") or 0),
                "합계금액": int(t.get("amount") or 0),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["사업자번호", "가맹점", "건수", "공급가액", "부가세", "합계금액"]
        )
    df = pd.DataFrame(rows)
    grouped = (
        df.groupby(["사업자번호", "가맹점"], dropna=False)
        .agg(
            건수=("공급가액", "size"),
            공급가액=("공급가액", "sum"),
            부가세=("부가세", "sum"),
            합계금액=("합계금액", "sum"),
        )
        .reset_index()
        .sort_values("합계금액", ascending=False)
    )
    return grouped


def compute_totals(txns: list[dict]) -> dict[str, int]:
    ded_supply = ded_vat = non_supply = non_vat = 0
    for t in txns:
        s = int(t.get("supply_value") or 0)
        v = int(t.get("vat") or 0)
        if bool(t.get("vat_deductible", True)):
            ded_supply += s
            ded_vat += v
        else:
            non_supply += s
            non_vat += v
    return {
        "공제_공급가액": ded_supply,
        "공제_부가세": ded_vat,
        "불공제_공급가액": non_supply,
        "불공제_부가세": non_vat,
        "총_공급가액": ded_supply + non_supply,
        "총_부가세": ded_vat + non_vat,
    }


def get_company_info() -> dict[str, str]:
    """secrets의 [company] 섹션을 반환. 없으면 빈 dict."""
    try:
        cfg = dict(st.secrets["company"])
    except Exception:
        return {}
    return {str(k): str(v) for k, v in cfg.items()}


def build_report_excel(
    year: int,
    quarter: Optional[int],
    month: Optional[int],
    txns: list[dict],
) -> bytes:
    """국세청 '신용카드매출전표 등 수령명세서'에 준하는 신고용 엑셀 생성."""
    company = get_company_info()
    period_label = (
        f"{year}년 {quarter}분기"
        if quarter is not None
        else (f"{year}-{month:02d}" if month is not None else f"{year}년 전체")
    )

    vendor = build_vendor_summary(txns)
    totals = compute_totals(txns)

    lines = pd.DataFrame(
        [
            {
                "거래일": t.get("txn_date"),
                "사업자번호": t.get("biz_no") or "",
                "가맹점": t.get("merchant") or "",
                "카드": t.get("card_name") or "",
                "카테고리그룹": t.get("category_group") or "",
                "카테고리": t.get("category") or "",
                "공제여부": "공제" if bool(t.get("vat_deductible", True)) else "불공제",
                "공급가액": int(t.get("supply_value") or 0),
                "부가세": int(t.get("vat") or 0),
                "합계금액": int(t.get("amount") or 0),
                "메모": t.get("memo") or "",
            }
            for t in sorted(txns, key=lambda x: (x.get("txn_date") or ""))
        ]
    )

    header = pd.DataFrame(
        [
            {"항목": "신고기간", "값": period_label},
            {"항목": "회사(상호)", "값": company.get("name", "")},
            {"항목": "사업자등록번호", "값": company.get("biz_no", "")},
            {"항목": "대표자", "값": company.get("owner", "")},
            {"항목": "업태", "값": company.get("industry", "")},
            {"항목": "종목", "값": company.get("item", "")},
            {"항목": "공제 대상 공급가액 합계", "값": totals["공제_공급가액"]},
            {"항목": "공제 대상 부가세 합계", "값": totals["공제_부가세"]},
            {"항목": "불공제 공급가액 합계", "값": totals["불공제_공급가액"]},
            {"항목": "불공제 부가세 합계", "값": totals["불공제_부가세"]},
        ]
    )

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        header.to_excel(writer, sheet_name="신고서요약", index=False)
        vendor.to_excel(writer, sheet_name="사업자별집계", index=False)
        if not lines.empty:
            lines.to_excel(writer, sheet_name="거래명세", index=False)
    buf.seek(0)
    return buf.getvalue()
