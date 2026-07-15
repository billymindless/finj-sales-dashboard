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
├── app.py                    # 메인 진입점 (인증 + 홈)
├── pages/
│   ├── 1_📊_대시보드.py       # 차트 대시보드
│   ├── 2_✏️_데이터입력.py     # 월별 데이터 입력
│   ├── 3_📋_데이터테이블.py    # 전체 테이블 & Excel 내보내기
│   ├── 4_🧾_카드내역업로드.py  # 카드사 엑셀 업로드 · AI 자동 분류
│   └── 5_🧾_부가세.py         # 부가세(매입세액) 신고 자료
├── utils/
│   ├── auth.py               # 인증 유틸
│   ├── database.py           # 데이터 저장/로드 (로컬 JSON ↔ Supabase)
│   ├── calculations.py       # 영업이익·ROAS 계산
│   ├── charts.py             # Plotly 차트 함수
│   ├── excel_parser.py       # 카드사 엑셀 파싱 + 컬럼 매핑
│   ├── classifier.py         # Gemini 기반 거래 자동 분류
│   └── vat.py                # 부가세 신고 자료 생성
├── data/                     # 로컬 데이터 저장소 (gitignore)
├── docs/
│   └── 카드지출_자동분류_부가세_설계.md
├── .streamlit/
│   ├── config.toml           # 테마 설정
│   └── secrets.toml          # 비밀번호·API키 (gitignore)
└── requirements.txt
```

## 카드 지출 자동 분류 · 부가세 신고

카드사 엑셀 명세서를 업로드하면 Gemini AI가 거래를 기존 비용 항목(광고비/고정비/변동비/매입)으로 자동 분류하고,
월별 집계에 반영하며, 가맹점 사업자등록번호를 유지해 부가세 신고 자료를 생성합니다.

### 사용 준비

`.streamlit/secrets.toml`에 다음 섹션을 추가하세요.

```toml
[gemini]
api_key = "발급받은-Gemini-API-키"
model   = "gemini-1.5-flash"

[company]
name     = "핀즈"
biz_no   = "000-00-00000"
owner    = "대표자명"
industry = "도소매"
item     = "가구"
```

Gemini API 키는 [Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급.

### Supabase 테이블 (선택)

Supabase를 사용하는 경우 아래 두 테이블을 추가하세요. 미생성 시 로컬 JSON에 폴백 저장됩니다.

```sql
create table if not exists card_transactions (
  id uuid primary key,
  year_month text not null,
  txn_date date,
  merchant text,
  biz_no text,
  card_name text,
  amount numeric,
  supply_value numeric,
  vat numeric,
  category_group text,
  category text,
  vat_deductible boolean default true,
  classify_source text,
  classify_reason text,
  confidence numeric,
  memo text,
  raw jsonb,
  upload_batch uuid,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists idx_card_txn_ym on card_transactions(year_month);
create index if not exists idx_card_txn_batch on card_transactions(upload_batch);

create table if not exists merchant_category_map (
  merchant_key text primary key,
  category_group text,
  category text,
  vat_deductible boolean default true,
  updated_at timestamptz default now()
);
```

### 사용 흐름

1. **카드 내역 업로드** 페이지에서 카드사 엑셀 업로드
2. 컬럼 자동 매핑 확인 (필요 시 수동 지정)
3. **AI 자동 분류 실행** 버튼 → Gemini가 배치 분류
4. 검토 테이블에서 카테고리/공제여부를 확인·교정 (교정 결과는 다음 업로드부터 자동 학습)
5. **저장 & 월별 반영** → 기존 월별 데이터에 합산 또는 덮어쓰기
6. **부가세** 페이지에서 분기/월 선택 → 사업자번호별 집계 확인 → 신고용 엑셀 다운로드
