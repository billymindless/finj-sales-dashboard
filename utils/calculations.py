from typing import Optional


def calculate_derived(data: dict) -> dict:
    """
    월별 원시 데이터에서 파생 지표를 계산합니다.
    """
    매출 = data.get("매출", {})
    광고비 = data.get("광고비", {})
    고정비 = data.get("고정비", {})
    변동비 = data.get("변동비", {})
    매입 = data.get("매입", {})

    오늘의집매출 = 매출.get("오늘의집", 0)
    자사몰매출 = 매출.get("자사몰", 0)
    합산매출 = 오늘의집매출 + 자사몰매출

    오늘의집광고 = 광고비.get("오늘의집_광고", 0)
    자사몰광고 = 광고비.get("자사몰_광고", 0)
    총광고비 = sum(광고비.values())

    자사몰ROAS: Optional[float] = 자사몰매출 / 자사몰광고 if 자사몰광고 > 0 else None
    오늘의집ROAS: Optional[float] = 오늘의집매출 / 오늘의집광고 if 오늘의집광고 > 0 else None

    총고정비 = sum(고정비.values())
    총변동비 = sum(변동비.values())
    매입금액 = sum(매입.values())

    비용계 = 총광고비 + 총고정비 + 총변동비
    총지출 = 비용계 + 매입금액
    영업이익 = 합산매출 - 총지출

    광고비율: Optional[float] = (총광고비 / 합산매출 * 100) if 합산매출 > 0 else None
    마진율: Optional[float] = (영업이익 / 합산매출 * 100) if 합산매출 > 0 else None

    return {
        "합산매출": 합산매출,
        "오늘의집매출": 오늘의집매출,
        "자사몰매출": 자사몰매출,
        "오늘의집광고": 오늘의집광고,
        "자사몰광고": 자사몰광고,
        "총광고비": 총광고비,
        "자사몰ROAS": 자사몰ROAS,
        "오늘의집ROAS": 오늘의집ROAS,
        "총고정비": 총고정비,
        "총변동비": 총변동비,
        "비용계": 비용계,
        "매입금액": 매입금액,
        "총지출": 총지출,
        "영업이익": 영업이익,
        "광고비율": 광고비율,
        "마진율": 마진율,
    }


def build_summary_df(all_data: dict):
    """전체 데이터를 pandas DataFrame으로 변환"""
    import pandas as pd

    rows = []
    for ym, month_data in sorted(all_data.items()):
        row = {"연월": ym}
        row.update(calculate_derived(month_data))
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("연월")


ROAS_TARGETS = {
    "자사몰": 3.5,
    "오늘의집": 18.0,
}
