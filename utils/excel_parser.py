"""
카드사 지출 엑셀 파서.

여러 카드사 명세서 양식을 처리하기 위해:
1. 헤더 행을 자동 탐색 (첫 몇 줄이 회사정보/공백일 수 있음).
2. 컬럼명을 동의어 사전으로 표준 필드에 자동 매핑.
3. 금액/날짜/사업자번호를 정규화하고 취소 행은 음수로 처리.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd


STANDARD_FIELDS = [
    "txn_date",
    "merchant",
    "amount",
    "biz_no",
    "card_name",
    "supply_value",
    "vat",
    "memo",
]

REQUIRED_FIELDS = ["txn_date", "merchant", "amount"]

COLUMN_SYNONYMS: dict[str, list[str]] = {
    "txn_date": [
        "이용일", "이용일자", "거래일자", "승인일자", "매출일자", "결제일자",
        "매입일자", "사용일자", "일자", "date", "transaction date",
    ],
    "merchant": [
        "가맹점명", "이용가맹점", "가맹점", "상호", "가맹점상호", "이용처",
        "사용처", "merchant", "store", "store name",
    ],
    "amount": [
        "이용금액", "승인금액", "결제금액", "합계금액", "총결제금액",
        "청구금액", "매출금액", "금액", "amount", "total", "합계",
    ],
    "biz_no": [
        "사업자번호", "사업자등록번호", "가맹점사업자번호",
        "가맹점사업자등록번호", "biz no", "business number", "vendor id",
    ],
    "card_name": [
        "카드명", "카드종류", "카드구분", "카드번호", "card", "card name",
    ],
    "supply_value": [
        "공급가액", "supply value", "net amount",
    ],
    "vat": [
        "부가세", "부가가치세", "세액", "vat", "tax",
    ],
    "memo": [
        "적요", "비고", "메모", "memo", "note", "description",
    ],
}

CANCEL_TOKENS = ["취소", "환불", "반품", "cancel", "refund", "chargeback"]


@dataclass
class ParseResult:
    """엑셀 파싱 결과."""

    df: pd.DataFrame
    detected_mapping: dict[str, Optional[str]]
    header_row: int
    original_columns: list[str]
    sheet_name: str
    warnings: list[str] = field(default_factory=list)


def _normalize(name: object) -> str:
    if name is None:
        return ""
    return re.sub(r"[\s_\-()·.]+", "", str(name)).lower()


def _match_field(col: str) -> Optional[str]:
    norm = _normalize(col)
    if not norm:
        return None
    for field_name, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            if _normalize(syn) == norm:
                return field_name
    for field_name, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            syn_norm = _normalize(syn)
            if syn_norm and (syn_norm in norm or norm in syn_norm):
                return field_name
    return None


def _detect_header_row(raw: pd.DataFrame, max_scan: int = 15) -> int:
    """헤더 후보 행 자동 탐색: 표준필드 매칭 개수가 가장 많은 행."""
    best_row = 0
    best_hits = -1
    limit = min(max_scan, len(raw))
    for i in range(limit):
        row_vals = raw.iloc[i].tolist()
        hits = sum(1 for v in row_vals if _match_field(v))
        if hits > best_hits:
            best_hits = hits
            best_row = i
    return best_row


def _read_workbook(file: io.BytesIO | bytes, sheet: Optional[str] = None) -> tuple[pd.DataFrame, str]:
    if isinstance(file, bytes):
        buf = io.BytesIO(file)
    else:
        buf = file
    xls = pd.ExcelFile(buf, engine="openpyxl")
    sheet_name = sheet or xls.sheet_names[0]
    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=object)
    return raw, sheet_name


def list_sheets(file: io.BytesIO | bytes) -> list[str]:
    if isinstance(file, bytes):
        buf = io.BytesIO(file)
    else:
        buf = file
    return pd.ExcelFile(buf, engine="openpyxl").sheet_names


def parse_excel(
    file: io.BytesIO | bytes,
    sheet: Optional[str] = None,
    header_row: Optional[int] = None,
) -> ParseResult:
    """엑셀을 읽어 헤더 자동 감지 + 컬럼 자동 매핑 결과 반환.

    - `header_row=None`이면 자동 감지.
    - `sheet=None`이면 첫 시트.
    """
    raw, sheet_name = _read_workbook(file, sheet)
    if raw.empty:
        return ParseResult(
            df=pd.DataFrame(),
            detected_mapping={f: None for f in STANDARD_FIELDS},
            header_row=0,
            original_columns=[],
            sheet_name=sheet_name,
            warnings=["빈 시트입니다."],
        )

    hr = _detect_header_row(raw) if header_row is None else header_row
    header = raw.iloc[hr].tolist()
    body = raw.iloc[hr + 1 :].reset_index(drop=True)
    body.columns = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(header)]
    original_cols = list(body.columns)

    mapping: dict[str, Optional[str]] = {f: None for f in STANDARD_FIELDS}
    for col in original_cols:
        matched = _match_field(col)
        if matched and mapping.get(matched) is None:
            mapping[matched] = col

    warnings: list[str] = []
    for req in REQUIRED_FIELDS:
        if mapping[req] is None:
            warnings.append(f"필수 컬럼 '{req}'을(를) 자동 감지하지 못했습니다. 수동으로 지정하세요.")

    return ParseResult(
        df=body,
        detected_mapping=mapping,
        header_row=hr,
        original_columns=original_cols,
        sheet_name=sheet_name,
        warnings=warnings,
    )


def _to_amount(v: object) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and pd.isna(v):
            return None
        return float(v)
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none", "-"}:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-") or s.startswith("△") or s.startswith("▲"):
        negative = True
        s = s.lstrip("-△▲")
    s = re.sub(r"[₩원,\s]", "", s)
    if not s:
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if negative else val


def _to_date(v: object) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(".", "-").replace("/", "-").replace(" ", "T", 1) if "T" not in s else s
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%y-%m-%d"):
        try:
            return datetime.strptime(s[: len(fmt.replace("%Y", "2000").replace("%y", "00"))], fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _to_biz_no(v: object) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = re.sub(r"[^0-9]", "", str(v))
    if not s:
        return None
    if len(s) == 10:
        return f"{s[0:3]}-{s[3:5]}-{s[5:10]}"
    return s


def normalize_rows(
    df: pd.DataFrame,
    mapping: dict[str, Optional[str]],
) -> pd.DataFrame:
    """컬럼 매핑을 적용해 표준 스키마 DataFrame으로 변환하고 값을 정규화."""
    for req in REQUIRED_FIELDS:
        if not mapping.get(req):
            raise ValueError(f"필수 컬럼 매핑 누락: {req}")

    out_rows: list[dict] = []
    for _, row in df.iterrows():
        raw_dict = {c: (None if pd.isna(v) else v) for c, v in row.items()}
        txn_date = _to_date(row.get(mapping["txn_date"]))
        merchant = row.get(mapping["merchant"])
        merchant_str = "" if merchant is None or (isinstance(merchant, float) and pd.isna(merchant)) else str(merchant).strip()
        amount = _to_amount(row.get(mapping["amount"]))
        if txn_date is None and not merchant_str and amount is None:
            continue
        if amount is None:
            continue

        memo_col = mapping.get("memo")
        memo_val = str(row.get(memo_col) or "") if memo_col else ""
        combined = f"{merchant_str} {memo_val}".lower()
        if amount > 0 and any(tok in combined for tok in CANCEL_TOKENS):
            amount = -amount

        biz_no_col = mapping.get("biz_no")
        biz_no = _to_biz_no(row.get(biz_no_col)) if biz_no_col else None

        card_col = mapping.get("card_name")
        card_name = row.get(card_col) if card_col else None
        card_name = None if card_name is None or (isinstance(card_name, float) and pd.isna(card_name)) else str(card_name).strip()

        sv_col = mapping.get("supply_value")
        supply_value = _to_amount(row.get(sv_col)) if sv_col else None
        vat_col = mapping.get("vat")
        vat = _to_amount(row.get(vat_col)) if vat_col else None
        if supply_value is None:
            supply_value = round(amount / 1.1) if amount else 0
        if vat is None:
            vat = round(amount - supply_value) if amount else 0

        out_rows.append(
            {
                "txn_date": txn_date,
                "merchant": merchant_str,
                "amount": int(round(amount)),
                "supply_value": int(round(supply_value)),
                "vat": int(round(vat)),
                "biz_no": biz_no,
                "card_name": card_name,
                "memo": memo_val.strip() or None,
                "raw": raw_dict,
            }
        )

    return pd.DataFrame(out_rows)


def infer_year_month(df: pd.DataFrame) -> Optional[str]:
    """정규화된 DataFrame에서 가장 흔한 연월(YYYY-MM)을 추정."""
    if df.empty or "txn_date" not in df.columns:
        return None
    dates = [d for d in df["txn_date"].tolist() if isinstance(d, date)]
    if not dates:
        return None
    counter: dict[str, int] = {}
    for d in dates:
        key = f"{d.year:04d}-{d.month:02d}"
        counter[key] = counter.get(key, 0) + 1
    return max(counter.items(), key=lambda kv: kv[1])[0]
