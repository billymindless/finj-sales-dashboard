import json
import os
import uuid
from datetime import datetime
from typing import Optional

import streamlit as st

LOCAL_DATA_FILE = "data/finj_data.json"
LOCAL_TXN_FILE = "data/card_transactions.json"
LOCAL_MERCHANT_MAP_FILE = "data/merchant_category_map.json"

DEFAULT_MONTH_DATA = {
    "매출": {
        "오늘의집": 0,
        "자사몰": 0,
    },
    "광고비": {
        "오늘의집_광고": 0,
        "자사몰_광고": 0,
        "메타_광고": 0,
        "네이버_광고": 0,
        "기타_광고": 0,
    },
    "고정비": {
        "급여": 0,
        "4대보험": 0,
        "퇴직연금": 0,
        "식대": 0,
        "임대료": 900000,
        "창고료": 0,
        "전기료": 200000,
        "관리비": 0,
        "이자_하나은행": 1200000,
        "세무사비": 0,
        "솔루션구독비": 0,
        "통신비": 0,
        "기타고정비": 0,
    },
    "변동비": {
        "택배비": 0,
        "설치배송비": 0,
        "반품비": 0,
        "포장재비": 0,
        "PG수수료": 0,
        "플랫폼수수료": 0,
        "AS비": 0,
        "불량처리비": 0,
        "촬영비": 0,
        "인플루언서비": 0,
        "출장교통비": 0,
        "접대비": 0,
        "소모품비": 0,
        "기타변동비": 0,
    },
    "매입": {
        "매입금액": 0,
    },
}


def _get_supabase():
    """Supabase 클라이언트 반환 (설정된 경우에만)"""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None


def _load_local() -> dict:
    if not os.path.exists(LOCAL_DATA_FILE):
        os.makedirs("data", exist_ok=True)
        return {}
    try:
        with open(LOCAL_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_local(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(LOCAL_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_all_data() -> dict:
    """전체 월별 데이터 로드 (Supabase 우선, 실패 시 로컬 JSON)"""
    supabase = _get_supabase()
    if supabase:
        try:
            response = supabase.table("monthly_data").select("*").order("year_month").execute()
            data = {}
            for row in response.data:
                data[row["year_month"]] = row["data"]
            return data
        except Exception as e:
            st.warning(f"Supabase 연결 실패 → 로컬 데이터 사용: {e}")
    return _load_local()


def save_month_data(year_month: str, month_data: dict) -> bool:
    """월별 데이터 저장 (upsert)"""
    supabase = _get_supabase()
    if supabase:
        try:
            supabase.table("monthly_data").upsert({
                "year_month": year_month,
                "data": month_data,
                "updated_at": datetime.now().isoformat(),
            }).execute()
            return True
        except Exception as e:
            st.error(f"Supabase 저장 실패: {e}")

    # 로컬 폴백
    data = _load_local()
    data[year_month] = month_data
    _save_local(data)
    return True


def delete_month_data(year_month: str) -> bool:
    """월별 데이터 삭제"""
    supabase = _get_supabase()
    if supabase:
        try:
            supabase.table("monthly_data").delete().eq("year_month", year_month).execute()
        except Exception:
            pass

    data = _load_local()
    if year_month in data:
        del data[year_month]
        _save_local(data)
    return True


def get_empty_month() -> dict:
    """빈 월 데이터 템플릿 반환 (깊은 복사)"""
    import copy
    return copy.deepcopy(DEFAULT_MONTH_DATA)


# ────────────────────────────────────────────────────────────────────────────
# 카드 거래 라인아이템 저장소 (card_transactions)
# ────────────────────────────────────────────────────────────────────────────

def _load_local_json(path: str) -> dict | list:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return [] if path.endswith("card_transactions.json") else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return [] if path.endswith("card_transactions.json") else {}


def _save_local_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _serialize_txn(txn: dict) -> dict:
    """날짜/객체 타입을 JSON/Supabase 호환 형식으로 변환. NaN → None."""
    import math

    out = dict(txn)
    for k, v in list(out.items()):
        if isinstance(v, float) and math.isnan(v):
            out[k] = None
    d = out.get("txn_date")
    if hasattr(d, "isoformat"):
        out["txn_date"] = d.isoformat()
    for k in ("amount", "supply_value", "vat"):
        if out.get(k) is not None:
            out[k] = int(out[k])
    if out.get("confidence") is not None:
        out["confidence"] = float(out["confidence"])
    return out


def save_card_transactions(year_month: str, txns: list[dict]) -> int:
    """월별 카드 거래 저장 (같은 upload_batch로 묶음). 저장된 건수 반환.

    - Supabase: card_transactions 테이블에 insert.
    - 로컬 폴백: data/card_transactions.json.
    """
    batch_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    prepared = []
    for t in txns:
        row = _serialize_txn(t)
        row.setdefault("id", str(uuid.uuid4()))
        row["year_month"] = year_month
        row["upload_batch"] = batch_id
        row["created_at"] = now
        row["updated_at"] = now
        prepared.append(row)

    supabase = _get_supabase()
    if supabase:
        try:
            supabase.table("card_transactions").insert(prepared).execute()
            return len(prepared)
        except Exception as e:
            st.warning(f"Supabase 저장 실패 → 로컬에 저장합니다: {e}")

    data = _load_local_json(LOCAL_TXN_FILE)
    if not isinstance(data, list):
        data = []
    data.extend(prepared)
    _save_local_json(LOCAL_TXN_FILE, data)
    return len(prepared)


def load_card_transactions(
    year_month: Optional[str] = None,
) -> list[dict]:
    """카드 거래 로드. year_month 지정 시 해당 월만."""
    supabase = _get_supabase()
    if supabase:
        try:
            q = supabase.table("card_transactions").select("*")
            if year_month:
                q = q.eq("year_month", year_month)
            resp = q.order("txn_date").execute()
            return list(resp.data or [])
        except Exception as e:
            st.warning(f"Supabase 조회 실패 → 로컬 데이터 사용: {e}")

    data = _load_local_json(LOCAL_TXN_FILE)
    if not isinstance(data, list):
        return []
    if year_month:
        return [r for r in data if r.get("year_month") == year_month]
    return data


def delete_card_transactions_batch(batch_id: str) -> int:
    """업로드 배치 단위로 삭제. 재업로드 시 롤백 용도."""
    supabase = _get_supabase()
    deleted = 0
    if supabase:
        try:
            resp = supabase.table("card_transactions").delete().eq("upload_batch", batch_id).execute()
            deleted = len(resp.data or [])
        except Exception as e:
            st.warning(f"Supabase 삭제 실패: {e}")

    data = _load_local_json(LOCAL_TXN_FILE)
    if isinstance(data, list):
        before = len(data)
        data = [r for r in data if r.get("upload_batch") != batch_id]
        _save_local_json(LOCAL_TXN_FILE, data)
        deleted = max(deleted, before - len(data))
    return deleted


def delete_card_transactions_by_month(year_month: str) -> int:
    """월별 카드 거래 전체 삭제."""
    supabase = _get_supabase()
    deleted = 0
    if supabase:
        try:
            resp = supabase.table("card_transactions").delete().eq("year_month", year_month).execute()
            deleted = len(resp.data or [])
        except Exception as e:
            st.warning(f"Supabase 삭제 실패: {e}")

    data = _load_local_json(LOCAL_TXN_FILE)
    if isinstance(data, list):
        before = len(data)
        data = [r for r in data if r.get("year_month") != year_month]
        _save_local_json(LOCAL_TXN_FILE, data)
        deleted = max(deleted, before - len(data))
    return deleted


# ────────────────────────────────────────────────────────────────────────────
# 가맹점 → 카테고리 매핑 캐시
# ────────────────────────────────────────────────────────────────────────────

def load_merchant_map() -> dict[str, dict]:
    """{merchant_key: {category_group, category, vat_deductible}} 반환."""
    supabase = _get_supabase()
    if supabase:
        try:
            resp = supabase.table("merchant_category_map").select("*").execute()
            out: dict[str, dict] = {}
            for row in resp.data or []:
                key = row.get("merchant_key") or row.get("merchant")
                if key:
                    out[key] = {
                        "category_group": row.get("category_group"),
                        "category": row.get("category"),
                        "vat_deductible": bool(row.get("vat_deductible", True)),
                    }
            return out
        except Exception:
            pass

    data = _load_local_json(LOCAL_MERCHANT_MAP_FILE)
    return data if isinstance(data, dict) else {}


def upsert_merchant_mapping(merchant_key: str, mapping: dict) -> None:
    """가맹점 분류 결과 캐시. `mapping`은 category_group/category/vat_deductible 포함."""
    payload = {
        "merchant_key": merchant_key,
        "category_group": mapping.get("category_group"),
        "category": mapping.get("category"),
        "vat_deductible": bool(mapping.get("vat_deductible", True)),
        "updated_at": datetime.now().isoformat(),
    }
    supabase = _get_supabase()
    if supabase:
        try:
            supabase.table("merchant_category_map").upsert(payload, on_conflict="merchant_key").execute()
            return
        except Exception:
            pass

    data = _load_local_json(LOCAL_MERCHANT_MAP_FILE)
    if not isinstance(data, dict):
        data = {}
    data[merchant_key] = {
        "category_group": payload["category_group"],
        "category": payload["category"],
        "vat_deductible": payload["vat_deductible"],
    }
    _save_local_json(LOCAL_MERCHANT_MAP_FILE, data)


# ────────────────────────────────────────────────────────────────────────────
# 월별 집계 반영 (카드 거래 → monthly_data)
# ────────────────────────────────────────────────────────────────────────────

CATEGORY_GROUPS = ("광고비", "고정비", "변동비", "매입")


def aggregate_transactions(txns: list[dict]) -> dict[str, dict[str, int]]:
    """거래 리스트를 {category_group: {category: 합계}}로 집계.

    금액은 amount(부가세 포함)로 집계한다. 매입세액 공제 계산은 utils/vat.py 참조.
    """
    result: dict[str, dict[str, int]] = {g: {} for g in CATEGORY_GROUPS}
    for t in txns:
        g = t.get("category_group")
        c = t.get("category")
        amt = t.get("amount") or 0
        if not g or not c or g not in result:
            continue
        result[g][c] = int(result[g].get(c, 0)) + int(amt)
    return result


def apply_transactions_to_month(
    year_month: str,
    txns: list[dict],
    mode: str = "add",
) -> dict:
    """카드거래 집계를 해당 월 monthly_data에 반영.

    mode:
      - "add"     : 기존 값 + 카드거래 합계
      - "replace" : 카드거래 합계로 덮어쓰기(해당 카테고리 항목만)
    """
    if mode not in {"add", "replace"}:
        raise ValueError("mode must be 'add' or 'replace'")

    all_data = load_all_data()
    month = all_data.get(year_month) or get_empty_month()

    agg = aggregate_transactions(txns)
    for group, items in agg.items():
        bucket = month.setdefault(group, {})
        for cat, val in items.items():
            if mode == "replace":
                bucket[cat] = int(val)
            else:
                bucket[cat] = int(bucket.get(cat, 0)) + int(val)

    save_month_data(year_month, month)
    return month


def merchant_key(merchant: str, biz_no: Optional[str]) -> str:
    """캐시 키 생성: 사업자번호 우선, 없으면 가맹점명."""
    if biz_no:
        digits = "".join(ch for ch in biz_no if ch.isdigit())
        if digits:
            return f"bizno:{digits}"
    name = (merchant or "").strip().lower()
    return f"name:{name}"
