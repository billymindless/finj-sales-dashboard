"""
Gemini 기반 카드 거래 자동 분류기.

- 허용 카테고리(기존 monthly_data 스키마)만 반환하도록 강제.
- 가맹점→카테고리 캐시를 우선 조회해 AI 호출을 절감.
- 배치 호출로 여러 거래를 한 번에 분류.
- 저신뢰 응답은 성격(정기/일회성)에 따라 `기타고정비`/`기타변동비`로 폴백.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from utils.database import (
    load_merchant_map,
    merchant_key,
    upsert_merchant_mapping,
)


ALLOWED_CATEGORIES: dict[str, list[str]] = {
    "광고비": [
        "오늘의집_광고", "자사몰_광고", "메타_광고", "네이버_광고", "기타_광고",
    ],
    "고정비": [
        "급여", "4대보험", "퇴직연금", "식대", "임대료", "창고료", "전기료",
        "관리비", "이자_하나은행", "세무사비", "솔루션구독비", "통신비", "기타고정비",
    ],
    "변동비": [
        "택배비", "설치배송비", "반품비", "포장재비", "PG수수료", "플랫폼수수료",
        "AS비", "불량처리비", "촬영비", "인플루언서비", "출장교통비", "접대비",
        "소모품비", "기타변동비",
    ],
    "매입": ["매입금액"],
}

NON_DEDUCTIBLE_CATEGORIES = {"접대비"}

CONFIDENCE_THRESHOLD = 0.6
BATCH_SIZE = 25


@dataclass
class Classification:
    category_group: str
    category: str
    confidence: float
    vat_deductible: bool
    source: str  # rule | cache | gemini | fallback
    reason: str = ""


def _is_valid(group: str, category: str) -> bool:
    return group in ALLOWED_CATEGORIES and category in ALLOWED_CATEGORIES[group]


def _fallback(reason: str = "저신뢰 분류") -> Classification:
    """규칙/AI 모두 실패 시 유사 비용으로 폴백."""
    return Classification(
        category_group="변동비",
        category="기타변동비",
        confidence=0.0,
        vat_deductible=True,
        source="fallback",
        reason=reason,
    )


# ── 간단 키워드 규칙(선택적 우선순위) ──────────────────────────────────────────
KEYWORD_RULES: list[tuple[re.Pattern, str, str, bool]] = [
    (re.compile(r"오늘의집|ohou", re.I), "광고비", "오늘의집_광고", True),
    (re.compile(r"메타|meta|facebook|instagram", re.I), "광고비", "메타_광고", True),
    (re.compile(r"네이버\s*(광고|검색|성과형|GFA)|naver\s*ads", re.I), "광고비", "네이버_광고", True),
    (re.compile(r"KT|SKT|LG\s*U\+?|LGU|엘지유플러스|SK텔레콤|통신", re.I), "고정비", "통신비", True),
    (re.compile(r"한국전력|KEPCO|전기요금", re.I), "고정비", "전기료", True),
    (re.compile(r"CJ대한통운|롯데택배|한진택배|우체국택배|로젠택배|택배", re.I), "변동비", "택배비", True),
    (re.compile(r"세무|회계법인|택스", re.I), "고정비", "세무사비", True),
]


def _rule_match(merchant: str) -> Optional[Classification]:
    for pat, group, cat, ded in KEYWORD_RULES:
        if pat.search(merchant or ""):
            return Classification(
                category_group=group,
                category=cat,
                confidence=0.95,
                vat_deductible=ded,
                source="rule",
            )
    return None


# ── Gemini 호출 ──────────────────────────────────────────────────────────────

def _get_model():
    """Gemini 모델 반환. 키 없거나 SDK 미설치면 None."""
    try:
        api_key = st.secrets["gemini"]["api_key"]
    except Exception:
        return None
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    genai.configure(api_key=api_key)
    model_name = "gemini-1.5-flash"
    try:
        model_name = st.secrets["gemini"].get("model", model_name) or model_name
    except Exception:
        pass
    return genai.GenerativeModel(model_name)


def _build_prompt(items: list[dict]) -> str:
    schema = {g: cats for g, cats in ALLOWED_CATEGORIES.items()}
    header = (
        "당신은 한국 이커머스(가구 셀러 '핀즈')의 회계 담당자입니다. "
        "카드 명세서 거래를 아래 허용 카테고리 중 정확히 하나로 분류하세요.\n\n"
        f"허용 카테고리(JSON): {json.dumps(schema, ensure_ascii=False)}\n\n"
        "판단 지침:\n"
        "- 온라인 광고비는 '광고비' 그룹에서 매체별 항목으로 매칭.\n"
        "- 정기 지출성(매월 반복, 통신·구독·임대 등)은 '고정비'.\n"
        "- 일회성/변동성 지출은 '변동비'.\n"
        "- 상품 매입은 '매입 > 매입금액'.\n"
        "- 접대성(주점, 골프, 회원제 등)은 '변동비 > 접대비'이며 vat_deductible=false.\n"
        "- 애매하면 confidence를 낮게(<0.6) 주고 근접한 '기타*' 항목으로 분류.\n\n"
        "다음 거래 배열을 반드시 JSON 배열로만 응답하세요. 각 원소 필드:\n"
        "  index (int), category_group (str), category (str), confidence (0~1), "
        "  vat_deductible (bool), reason (str, 최대 40자).\n\n"
        f"거래:\n{json.dumps(items, ensure_ascii=False)}"
    )
    return header


def _extract_json_array(text: str) -> list:
    if not text:
        return []
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except Exception:
        return []


def _classify_batch_via_gemini(model, batch: list[dict]) -> list[Classification]:
    prompt_items = [
        {
            "index": i,
            "merchant": b.get("merchant", ""),
            "amount": b.get("amount", 0),
            "memo": b.get("memo") or "",
        }
        for i, b in enumerate(batch)
    ]
    prompt = _build_prompt(prompt_items)

    try:
        resp = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json", "temperature": 0.2},
        )
        text = resp.text or ""
    except Exception as e:
        st.warning(f"Gemini 호출 실패, 폴백 사용: {e}")
        return [_fallback("Gemini 실패") for _ in batch]

    arr = _extract_json_array(text)
    out: list[Optional[Classification]] = [None] * len(batch)
    for item in arr:
        try:
            idx = int(item.get("index"))
        except Exception:
            continue
        if not (0 <= idx < len(batch)):
            continue
        g = str(item.get("category_group") or "")
        c = str(item.get("category") or "")
        conf = float(item.get("confidence") or 0)
        ded = bool(item.get("vat_deductible", True))
        reason = str(item.get("reason") or "")

        if not _is_valid(g, c):
            out[idx] = _fallback(f"미허용 카테고리 응답: {g}/{c}")
            continue
        if conf < CONFIDENCE_THRESHOLD:
            fb = _fallback(f"저신뢰({conf:.2f}): {reason}")
            out[idx] = fb
            continue
        if c in NON_DEDUCTIBLE_CATEGORIES:
            ded = False
        out[idx] = Classification(
            category_group=g,
            category=c,
            confidence=conf,
            vat_deductible=ded,
            source="gemini",
            reason=reason,
        )

    return [c or _fallback("Gemini 응답 누락") for c in out]


def classify_transactions(
    txns: list[dict],
    use_cache: bool = True,
    persist_cache: bool = True,
) -> list[dict]:
    """거래 리스트에 분류 필드를 채워 반환.

    입력 원소는 최소 `merchant`, `amount` 필드를 포함해야 하며, `biz_no`가 있으면 캐시 키에 활용.
    반환은 원본 필드 + `category_group`, `category`, `confidence`, `vat_deductible`,
    `classify_source`, `classify_reason`.
    """
    if not txns:
        return []

    cache = load_merchant_map() if use_cache else {}
    model = _get_model()

    result: list[dict] = [dict(t) for t in txns]
    to_ask: list[int] = []

    for i, t in enumerate(result):
        key = merchant_key(t.get("merchant", ""), t.get("biz_no"))
        t["_merchant_key"] = key

        cached = cache.get(key) if use_cache else None
        if cached and _is_valid(cached.get("category_group"), cached.get("category")):
            t["category_group"] = cached["category_group"]
            t["category"] = cached["category"]
            t["confidence"] = 1.0
            t["vat_deductible"] = bool(cached.get("vat_deductible", True))
            t["classify_source"] = "cache"
            t["classify_reason"] = "이전 분류 결과 재사용"
            continue

        rule = _rule_match(t.get("merchant", ""))
        if rule:
            t["category_group"] = rule.category_group
            t["category"] = rule.category
            t["confidence"] = rule.confidence
            t["vat_deductible"] = rule.vat_deductible
            t["classify_source"] = rule.source
            t["classify_reason"] = "키워드 규칙"
            continue

        to_ask.append(i)

    if to_ask:
        if model is None:
            for i in to_ask:
                fb = _fallback("Gemini 미설정")
                t = result[i]
                t["category_group"] = fb.category_group
                t["category"] = fb.category
                t["confidence"] = fb.confidence
                t["vat_deductible"] = fb.vat_deductible
                t["classify_source"] = fb.source
                t["classify_reason"] = fb.reason
        else:
            for start in range(0, len(to_ask), BATCH_SIZE):
                idxs = to_ask[start : start + BATCH_SIZE]
                batch = [result[i] for i in idxs]
                classifications = _classify_batch_via_gemini(model, batch)
                for i, cls in zip(idxs, classifications):
                    t = result[i]
                    t["category_group"] = cls.category_group
                    t["category"] = cls.category
                    t["confidence"] = cls.confidence
                    t["vat_deductible"] = cls.vat_deductible
                    t["classify_source"] = cls.source
                    t["classify_reason"] = cls.reason

    if persist_cache:
        for t in result:
            if t.get("classify_source") in {"gemini", "rule"} and t.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
                key = t.get("_merchant_key")
                if key:
                    upsert_merchant_mapping(
                        key,
                        {
                            "category_group": t["category_group"],
                            "category": t["category"],
                            "vat_deductible": t["vat_deductible"],
                        },
                    )

    for t in result:
        t.pop("_merchant_key", None)

    return result


def override_and_learn(txn: dict) -> None:
    """사용자가 카테고리를 수동 교정한 뒤 캐시에 학습시킨다."""
    key = merchant_key(txn.get("merchant", ""), txn.get("biz_no"))
    if not _is_valid(txn.get("category_group"), txn.get("category")):
        return
    upsert_merchant_mapping(
        key,
        {
            "category_group": txn["category_group"],
            "category": txn["category"],
            "vat_deductible": bool(txn.get("vat_deductible", True)),
        },
    )
