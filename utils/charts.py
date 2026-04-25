import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional

COLORS = {
    "오늘의집": "#FF6B35",
    "자사몰": "#2563EB",
    "영업이익_pos": "#16A34A",
    "영업이익_neg": "#DC2626",
    "광고비": "#F59E0B",
    "고정비": "#8B5CF6",
    "변동비": "#06B6D4",
    "매입": "#64748B",
    "bg": "#F8FAFC",
}

LAYOUT_DEFAULTS = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Pretendard, Malgun Gothic, sans-serif", size=13),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def revenue_trend_chart(df: pd.DataFrame) -> go.Figure:
    """월별 매출 추이 (오늘의집 + 자사몰 누적 바 + 영업이익 라인)"""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="오늘의집 매출",
        x=df.index,
        y=df["오늘의집매출"],
        marker_color=COLORS["오늘의집"],
    ))
    fig.add_trace(go.Bar(
        name="자사몰 매출",
        x=df.index,
        y=df["자사몰매출"],
        marker_color=COLORS["자사몰"],
    ))
    fig.add_trace(go.Scatter(
        name="영업이익",
        x=df.index,
        y=df["영업이익"],
        mode="lines+markers",
        line=dict(width=3, dash="dot"),
        marker=dict(size=8),
        marker_color=[COLORS["영업이익_pos"] if v >= 0 else COLORS["영업이익_neg"] for v in df["영업이익"]],
        yaxis="y2",
    ))

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="월별 매출 & 영업이익 추이",
        barmode="stack",
        yaxis=dict(title="매출 (원)", tickformat=",.0f"),
        yaxis2=dict(title="영업이익 (원)", overlaying="y", side="right", tickformat=",.0f"),
    )
    return fig


def roas_trend_chart(df: pd.DataFrame, target_자사몰: float = 3.5, target_오늘의집: float = 18.0) -> go.Figure:
    """월별 ROAS 추이 차트"""
    fig = go.Figure()

    if "자사몰ROAS" in df.columns:
        fig.add_trace(go.Scatter(
            name="자사몰 ROAS",
            x=df.index,
            y=df["자사몰ROAS"],
            mode="lines+markers",
            line=dict(color=COLORS["자사몰"], width=2),
            marker=dict(size=8),
        ))
        fig.add_hline(
            y=target_자사몰, line_dash="dash", line_color=COLORS["자사몰"],
            annotation_text=f"자사몰 목표 {target_자사몰}",
            annotation_position="bottom right",
        )

    if "오늘의집ROAS" in df.columns:
        fig.add_trace(go.Scatter(
            name="오늘의집 ROAS",
            x=df.index,
            y=df["오늘의집ROAS"],
            mode="lines+markers",
            line=dict(color=COLORS["오늘의집"], width=2),
            marker=dict(size=8),
        ))
        fig.add_hline(
            y=target_오늘의집, line_dash="dash", line_color=COLORS["오늘의집"],
            annotation_text=f"오늘의집 목표 {target_오늘의집}",
            annotation_position="bottom right",
        )

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="월별 ROAS 추이",
        yaxis=dict(title="ROAS"),
    )
    return fig


def cost_breakdown_pie(month_data: dict, year_month: str) -> go.Figure:
    """비용 구성 파이 차트"""
    from utils.calculations import calculate_derived
    derived = calculate_derived(month_data)

    labels = ["광고비", "고정비", "변동비", "매입금액"]
    values = [derived["총광고비"], derived["총고정비"], derived["총변동비"], derived["매입금액"]]
    colors = [COLORS["광고비"], COLORS["고정비"], COLORS["변동비"], COLORS["매입"]]

    filtered = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not filtered:
        fig = go.Figure()
        fig.add_annotation(text="데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    labels, values, colors = zip(*filtered)

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=colors,
        hole=0.4,
        textinfo="label+percent",
        textfont_size=13,
    ))
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=f"{year_month} 비용 구성",
        legend=dict(orientation="v"),
    )
    return fig


def cost_trend_chart(df: pd.DataFrame) -> go.Figure:
    """월별 비용 항목 추이 누적 바차트"""
    fig = go.Figure()

    categories = [
        ("총광고비", "광고비", COLORS["광고비"]),
        ("총고정비", "고정비", COLORS["고정비"]),
        ("총변동비", "변동비", COLORS["변동비"]),
        ("매입금액", "매입금액", COLORS["매입"]),
    ]

    for col, name, color in categories:
        if col in df.columns:
            fig.add_trace(go.Bar(
                name=name,
                x=df.index,
                y=df[col],
                marker_color=color,
            ))

    if "합산매출" in df.columns:
        fig.add_trace(go.Scatter(
            name="합산매출",
            x=df.index,
            y=df["합산매출"],
            mode="lines+markers",
            line=dict(color="#1E293B", width=2),
            marker=dict(size=7),
        ))

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="월별 비용 구성 & 매출 비교",
        barmode="stack",
        yaxis=dict(title="금액 (원)", tickformat=",.0f"),
    )
    return fig


def ad_channel_bar(month_data: dict, year_month: str) -> go.Figure:
    """광고 채널별 비용 바차트"""
    광고비 = month_data.get("광고비", {})
    label_map = {
        "오늘의집_광고": "오늘의집",
        "자사몰_광고": "자사몰",
        "메타_광고": "메타",
        "네이버_광고": "네이버",
        "기타_광고": "기타",
    }
    labels = [label_map.get(k, k) for k, v in 광고비.items() if v > 0]
    values = [v for v in 광고비.values() if v > 0]

    if not labels:
        fig = go.Figure()
        fig.add_annotation(text="광고비 데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=[COLORS["오늘의집"], COLORS["자사몰"], "#F59E0B", "#10B981", "#94A3B8"][:len(labels)],
        text=[f"₩{v:,.0f}" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=f"{year_month} 광고채널별 집행금액",
        yaxis=dict(title="금액 (원)", tickformat=",.0f"),
    )
    return fig
