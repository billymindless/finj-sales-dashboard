# 📊 핀즈 영업 대시보드

온라인 가구 셀링 비즈니스(핀즈)의 월별 매출·비용·ROAS를 한눈에 시각화하는 대시보드입니다.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 자동 접속

기본 비밀번호: `finj2024` (`.streamlit/secrets.toml`에서 변경)

## 웹 배포 (Streamlit Cloud + Supabase)

자세한 가이드는 아래 **배포 가이드** 참조.

## 폴더 구조

```
finj_sales/
├── app.py                  # 메인 진입점 (인증 + 홈)
├── pages/
│   ├── 1_📊_대시보드.py    # 차트 대시보드
│   ├── 2_✏️_데이터입력.py  # 월별 데이터 입력
│   └── 3_📋_데이터테이블.py # 전체 테이블 & Excel 내보내기
├── utils/
│   ├── auth.py             # 인증 유틸
│   ├── database.py         # 데이터 저장/로드 (로컬 JSON ↔ Supabase)
│   ├── calculations.py     # 영업이익·ROAS 계산
│   └── charts.py           # Plotly 차트 함수
├── data/                   # 로컬 데이터 저장소 (gitignore)
├── .streamlit/
│   ├── config.toml         # 테마 설정
│   └── secrets.toml        # 비밀번호·API키 (gitignore)
└── requirements.txt
```
