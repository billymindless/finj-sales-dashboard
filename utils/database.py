import json
import os
from datetime import datetime

import streamlit as st

LOCAL_DATA_FILE = "data/finj_data.json"

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
