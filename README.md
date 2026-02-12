# FDS Pipeline Lab: 실시간 이상거래 탐지 파이프라인

> 데이터 엔지니어 포트폴리오 프로젝트

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [핵심 성과](#핵심-성과)
3. [시스템 아키텍처](#시스템-아키텍처)
4. [기술 스택](#기술-스택)
5. [성능 최적화 과정](#성능-최적화-과정)
6. [FDS 룰 엔진](#fds-룰-엔진)
7. [모니터링 & 알림](#모니터링--알림)
8. [데이터 현실화](#데이터-현실화)
9. [실행 방법](#실행-방법)
10. [프로젝트 구조](#프로젝트-구조)
11. [문서](#문서)
12. [면접 예상 질문](#면접-예상-질문)

---

## 프로젝트 개요

### 배경

금융권에서는 실시간으로 발생하는 결제 데이터를 빠르게 처리하고, 이상거래를 탐지하는 것이 핵심입니다. 이 프로젝트는 실제 FDS(Fraud Detection System) 파이프라인을 구축하고, 단계별 성능 최적화를 통해 **250배 성능 개선**을 달성한 과정을 보여줍니다.

### 목표

1. **실시간 결제 데이터 처리 파이프라인 구축**
2. **단계별 병목 분석 및 성능 최적화**
3. **FDS 룰 기반 이상거래 탐지**
4. **SLA 모니터링 및 알림 시스템 구축**

---

## 핵심 성과

| 성과 | 상세 |
|------|------|
| 🚀 **성능 250배 개선** | TPS 70 → 17,500 |
| 🔍 **이상거래 탐지** | 4가지 FDS 룰로 5% 탐지 |
| 📊 **실시간 모니터링** | SLA 위반 + 이상거래 알림 |
| 📈 **현실적 데이터** | 10만 유저, 24시간 분포 |

---

## 시스템 아키텍처

### 전체 구조
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FDS Pipeline Architecture                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Generator  │────▶│    Redis    │────▶│  Consumer   │────▶│ PostgreSQL  │
│             │     │             │     │             │     │             │
│ • 결제 생성  │     │ • Queue     │     │ • FDS 검사  │     │ • 저장소    │
│ • 10만 유저  │     │ • 버퍼 역할  │     │ • 4가지 룰  │     │ • 분석용    │
│ • 현실적    │     │ • 스파이크   │     │ • Batch     │     │             │
│   데이터    │     │   흡수      │     │   INSERT    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                         ┌─────────────────────────────────────────┘
                         ▼
                  ┌─────────────┐
                  │     n8n     │
                  │  Monitoring │
                  └──────┬──────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
      ┌─────────┐  ┌─────────┐  ┌─────────┐
      │  Slack  │  │  Slack  │  │  Gmail  │
      │ SLA알림 │  │이상거래 │  │ SLA알림 │
      └─────────┘  └─────────┘  └─────────┘
```

### 데이터 흐름

1. **Generator**: 현실적인 결제 데이터 생성 (10만 유저 풀)
2. **Redis**: 메시지 큐로 트래픽 스파이크 흡수
3. **Consumer**: FDS 룰 검사 + Batch INSERT
4. **PostgreSQL**: 거래 데이터 저장
5. **n8n**: 1분마다 모니터링 → 알림 발송

---

## 기술 스택

| 컴포넌트 | 기술 | 버전 | 역할 |
|----------|------|------|------|
| Generator | Python, asyncio | 3.12 | 현실적인 결제 데이터 생성 |
| Queue | Redis | 7.x | 메시지 버퍼, 비동기 처리 |
| Consumer | Python, asyncpg | 3.12 | FDS 룰 검사, DB 저장 |
| Database | PostgreSQL | 15 | 트랜잭션 저장 |
| Monitoring | n8n | 2.7 | SLA 모니터링, 알림 |
| Container | Docker Compose | - | 환경 구성 |

---

## 성능 최적화 과정

### Phase 1: Baseline (동기 방식)
```python
# 매 요청마다 연결 생성/해제
conn = psycopg2.connect(...)
cur.execute("INSERT ...")
conn.close()
```

| 지표 | 값 |
|------|-----|
| TPS | 70 |
| Latency | 15ms |
| 병목 | Connection 생성 오버헤드 |

### Phase 2: Connection Pool + Async
```python
# Connection Pool 재사용
pool = await asyncpg.create_pool(...)
async with pool.acquire() as conn:
    await conn.execute("INSERT ...")
```

| 지표 | 값 | 개선 |
|------|-----|------|
| TPS | 175 | 2.5배 |
| Latency | 2.8ms | -82% |

### Phase 2-B: 동시 요청
```python
# 50개 동시 처리
await asyncio.gather(*[insert(tx) for tx in batch])
```

| 지표 | 값 | 개선 |
|------|-----|------|
| TPS | 5,100 | 73배 |
| Latency | 6.3ms | - |

### Phase 2-C: Batch INSERT
```python
# 100건씩 배치 처리
await conn.executemany("INSERT ...", batch)
```

| 지표 | 값 | 개선 |
|------|-----|------|
| TPS | 17,400 | 248배 |
| Latency | 0.26ms | -98% |

### Phase 2-D: 한계 테스트

| 지표 | 값 | 개선 |
|------|-----|------|
| TPS | **17,500** | **250배** |
| 병목 | PostgreSQL WAL I/O | - |

### Phase 3: Redis Buffer + Consumer
```
Generator (10,000 TPS) → Redis Queue → Consumer (5,000 TPS) → PostgreSQL
```

| 지표 | 값 |
|------|-----|
| TPS | 5,000 (안정적) |
| E2E Latency | 80ms |
| 장점 | 트래픽 스파이크 흡수, 장애 복구 용이 |

### 성능 개선 요약

| Phase | 방식 | TPS | Latency | 개선율 |
|-------|------|-----|---------|--------|
| 1 | 동기, No Pool | 70 | 15ms | 기준 |
| 2 | Async + Pool | 175 | 2.8ms | 2.5배 |
| 2-B | 동시 요청 | 5,100 | 6.3ms | 73배 |
| 2-C | Batch INSERT | 17,400 | 0.26ms | 248배 |
| 2-D | Max Pool + Batch | **17,500** | 0.30ms | **250배** |
| 3 | Redis + Consumer | 5,000 | 80ms | 안정적 |

### 병목 분석 과정
```
Phase 1: Connection 생성 오버헤드 (10ms)
    ↓ Pool 도입
Phase 2: 순차 처리 한계
    ↓ 동시 요청 + Batch
Phase 2-D: PostgreSQL WAL I/O 한계 (CPU 44% 여유)
    ↓ 더 올리려면 DB 튜닝/샤딩 필요
Phase 3: Producer-Consumer 분리로 안정성 확보
```

---

## FDS 룰 엔진

### 탐지 규칙 (4가지)

| 룰 | 조건 | 설명 | 실제 사례 |
|----|------|------|----------|
| **Velocity** | 1분 내 5회 이상 | 카드 도용 시 빠른 연속 결제 | 도난 카드로 여러 상점 결제 |
| **Amount Spike** | 평소의 10배 이상 | 비정상적 고액 결제 | 평소 5만원 → 갑자기 500만원 |
| **Dawn High Amount** | 새벽(0-5시) + 500만원 이상 | 새벽 시간대 고액 결제 | 새벽 3시 명품 구매 |
| **Unusual Category** | 일반등급 + 명품 1천만원 | 등급 대비 이상 소비 | 일반 회원이 1천만원 명품 |

### 탐지 결과 (10만 건 기준)

| 항목 | 값 |
|------|-----|
| 총 거래 | 100,000건 |
| 이상거래 | 5,070건 (**5.07%**) |
| 탐지 금액 | 189.8억원 |

### 룰별 탐지 현황

| 룰 | 건수 | 비율 |
|----|------|------|
| Amount Spike | 4,726 | 93% |
| Unusual Category | 354 | 7% |
| Dawn High Amount | 8 | 0.2% |
| Velocity | 0 | 0% |

> **Velocity가 0인 이유**: 유저 풀이 10만 명으로 충분히 커서 1분 내 5회 이상 결제하는 경우가 거의 없음 (현실적)

### 정상 vs 이상거래 비교

| 구분 | 평균 금액 | 배수 |
|------|----------|------|
| 정상 거래 | 109,353원 | 1x |
| 이상 거래 | 3,744,844원 | **34배** |

---

## 모니터링 & 알림

### 아키텍처
```
┌─────────────────┐
│ Schedule Trigger│ (매 1분)
└────────┬────────┘
         ▼
┌─────────────────┐
│   PostgreSQL    │
│   통합 쿼리     │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│  IF   │ │  IF1  │
│처리량 │ │이상   │
│<1000? │ │거래?  │
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
[Slack]   [Slack]
[Gmail]   이상거래
SLA위반   탐지알림
```

### 알림 종류

| 알림 | 조건 | 채널 | 의미 |
|------|------|------|------|
| **SLA 위반** | 처리량 < 1,000건/분 | Slack + Email | 파이프라인 장애 |
| **이상거래 탐지** | fraud_count > 0 | Slack | FDS 룰 탐지 |

### 모니터링 쿼리
```sql
SELECT 
    COUNT(*) as total_count,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) as fraud_count,
    ROUND(SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric 
          / NULLIF(COUNT(*), 0) * 100, 2) as fraud_rate,
    COALESCE(SUM(CASE WHEN is_fraud THEN amount ELSE 0 END), 0) as fraud_amount
FROM fds.transactions
WHERE processed_at >= NOW() - INTERVAL '1 minute'
```

### 알림 메시지 예시

**SLA 위반 알림**
```
🚨 FDS Pipeline SLA 위반

처리량: 0건/분 (최소 1,000건)
이상거래: 0건
시간: 2026-02-12 09:30:00
```

**이상거래 탐지 알림**
```
🚨 이상거래 탐지!

최근 1분간: 8건
탐지 금액: 111,968,000원
탐지율: 0.62%
시간: 2026-02-12 09:32:26
```

---

## 데이터 현실화

### 설정

| 항목 | 값 |
|------|-----|
| 유저 풀 | 100,000명 |
| 카테고리 | 10개 |
| 가맹점 | 49개 |
| 지역 | 10개 |

### 카테고리별 설정

| 카테고리 | 가맹점 예시 | 금액 범위 | 영업시간 |
|----------|------------|----------|----------|
| convenience | CU, GS25, 세븐일레븐 | 1,000~30,000 | 24시간 |
| coffee | 스타벅스, 투썸, 이디야 | 3,000~15,000 | 7~22시 |
| restaurant | 맥도날드, 교촌치킨 | 5,000~300,000 | 6~24시 |
| delivery | 배달의민족, 쿠팡이츠 | 15,000~100,000 | 10~2시 |
| online_shopping | 쿠팡, 네이버쇼핑 | 10,000~500,000 | 24시간 |
| supermarket | 이마트, 홈플러스 | 30,000~300,000 | 10~22시 |
| fashion | 자라, 유니클로 | 30,000~500,000 | 10~21시 |
| electronics | 삼성스토어, 하이마트 | 50,000~3,000,000 | 10~21시 |
| travel | 대한항공, 야놀자 | 50,000~5,000,000 | 24시간 |
| luxury | 루이비통, 샤넬 | 500,000~50,000,000 | 10~20시 |

### 데이터 분포

**시간대별**
| 시간대 | 비율 | 설명 |
|--------|------|------|
| 새벽 (0-5시) | 11% | 적음 |
| 아침 (6-9시) | 14% | 증가 |
| 낮/저녁 (10-21시) | 68% | 피크 |
| 밤 (22-23시) | 7% | 감소 |

**금액별**
| 구간 | 비율 |
|------|------|
| ~1만원 | 34% |
| 1~5만원 | 38% |
| 5~10만원 | 10% |
| 10~50만원 | 14% |
| 50~100만원 | 1% |
| 100만원~ | 3% |

**지역별**
| 지역 | 비율 |
|------|------|
| 서울 | 30% |
| 경기 | 25% |
| 인천 | 10% |
| 제주 | 10% |
| 기타 | 25% |

---

## 실행 방법

### 사전 요구사항

- Docker & Docker Compose
- PostgreSQL (기존 인스턴스 또는 Docker로 실행)

### 1. 환경 설정
```bash
# 저장소 클론
git clone https://github.com/Aguantar/fds-pipeline-lab.git
cd fds-pipeline-lab

# 환경 변수 설정
cp .env.example .env
vi .env
```

### 2. 인프라 실행
```bash
# Redis 실행
docker compose up -d fds-redis

# PostgreSQL 스키마 생성 (기존 DB 사용 시)
docker exec -i my-postgres psql -U calme -d blood_db < database/init_schema.sql
```

### 3. 파이프라인 실행
```bash
# Generator + Consumer 실행
docker compose --profile pipeline up generator consumer
```

### 4. 모니터링
```bash
# Redis Queue 확인
docker exec fds-redis redis-cli LLEN tx_queue

# DB 데이터 확인
docker exec -i my-postgres psql -U calme -d blood_db -c "
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) as fraud
FROM fds.transactions;
"

# 이상거래 비율 확인
docker exec -i my-postgres psql -U calme -d blood_db -c "
SELECT 
    COUNT(*) as total,
    ROUND(SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as fraud_rate
FROM fds.transactions;
"
```

---

## 프로젝트 구조
```
fds-pipeline-lab/
├── README.md                     # 프로젝트 문서
├── docker-compose.yml            # Docker 구성
├── .env                          # 환경 변수
│
├── database/
│   └── init_schema.sql           # DB 스키마
│
├── part-a-pipeline/
│   ├── generator/
│   │   ├── Dockerfile
│   │   ├── main.py               # 데이터 생성 + Redis 푸시
│   │   ├── config.py             # 설정
│   │   └── metrics.py            # 메트릭 수집
│   │
│   └── consumer/
│       ├── Dockerfile
│       ├── main.py               # Redis → FDS → PostgreSQL
│       ├── config.py             # 설정
│       ├── metrics.py            # 메트릭 수집
│       └── fds_rules.py          # FDS 룰 엔진
│
├── analysis/
│   ├── notebooks/
│   │   └── 01_pipeline_analysis.ipynb  # 데이터 분석
│   └── data/
│       ├── latency_distribution.png
│       ├── hourly_transactions.png
│       ├── category_analysis.png
│       ├── region_analysis.png
│       ├── tier_analysis.png
│       ├── fraud_types.png
│       └── normal_vs_fraud.png
│
└── docs/
    ├── 01-project-setup.md       # 프로젝트 초기 설정
    ├── 02-phase1-baseline-results.md   # Phase 1 결과
    ├── 03-phase2-optimization-results.md # Phase 2 최적화
    ├── 04-phase3-redis-consumer.md     # Phase 3 구현
    ├── 05-part-b-sla-monitoring.md     # 모니터링 & 알림
    └── 06-data-analysis.md       # 데이터 분석 결과
```

---

## 문서

| 문서 | 내용 |
|------|------|
| [01-project-setup](docs/01-project-setup.md) | 프로젝트 초기 설정, 인프라 구성 |
| [02-phase1-baseline](docs/02-phase1-baseline-results.md) | Baseline 측정 (TPS 70) |
| [03-phase2-optimization](docs/03-phase2-optimization-results.md) | 성능 최적화 과정 (TPS 17,500) |
| [04-phase3-redis-consumer](docs/04-phase3-redis-consumer.md) | Redis + Consumer 구현 |
| [05-sla-monitoring](docs/05-part-b-sla-monitoring.md) | SLA 모니터링 & 이상거래 알림 |
| [06-data-analysis](docs/06-data-analysis.md) | 데이터 분석 결과 |

---

## 면접 예상 질문

### 성능 최적화

**Q1. TPS 70에서 17,500까지 어떻게 개선했나요?**

> "단계별로 병목을 분석했습니다.
> 
> 1단계: Connection 생성 오버헤드가 10ms로, Pool을 도입해 2.5배 개선
> 2단계: 순차 처리를 동시 요청으로 바꿔 73배 개선
> 3단계: 개별 INSERT를 Batch로 바꿔 248배 개선
> 
> 최종적으로 PostgreSQL WAL I/O가 병목임을 확인했고, 이 이상은 DB 튜닝이나 샤딩이 필요하다고 판단했습니다."

**Q2. TPS 17,500에서 더 이상 안 올라간 이유는?**

> "CPU가 44%로 여유가 있었지만 TPS가 안 올랐습니다.
> PostgreSQL의 WAL(Write-Ahead Log) 쓰기가 병목이었습니다.
> Application 레벨 최적화의 한계이며, 더 올리려면 synchronous_commit=off 설정이나 파티셔닝이 필요합니다."

### 아키텍처

**Q3. Redis를 왜 사용했나요?**

> "세 가지 이유입니다.
> 
> 1. **속도 차이 흡수**: Generator와 Consumer의 처리 속도가 다를 때 버퍼 역할
> 2. **스파이크 대응**: 트래픽이 급증해도 데이터 유실 없이 순차 처리
> 3. **장애 복구**: DB 장애 시에도 Queue에 데이터 보관, 복구 후 처리 가능"

**Q4. SLA 모니터링을 왜 Airflow 대신 n8n으로 했나요?**

> "요구사항이 단순했기 때문입니다.
> 1분마다 DB 조회 → 조건 체크 → 알림, 이게 전부였습니다.
> 복잡한 DAG 의존성이나 백필 기능이 필요 없어서, 기존에 운영 중인 n8n을 활용했습니다.
> 
> Airflow가 필요한 경우는 일별 집계 → 주간 리포트 → S3 업로드처럼 여러 단계의 의존성이 있을 때입니다."

### FDS

**Q5. FDS 룰은 어떻게 설계했나요?**

> "실제 카드 사기 패턴을 기반으로 4가지 룰을 설계했습니다.
> 
> 1. **Velocity**: 도난 카드는 빠르게 여러 번 결제하는 경향
> 2. **Amount Spike**: 평소와 다른 고액 결제는 의심
> 3. **Dawn High Amount**: 새벽 시간대 고액은 비정상
> 4. **Unusual Category**: 등급 대비 과한 소비는 의심
> 
> 결과적으로 5%의 이상거래를 탐지했고, 이상거래 평균 금액이 정상의 34배로 룰이 잘 동작함을 확인했습니다."

**Q6. 이상거래 탐지 시 알림은 어떻게 보내나요?**

> "n8n으로 1분마다 DB를 조회해서 이상거래 건수가 0보다 크면 Slack으로 알림을 보냅니다.
> 탐지 건수, 금액, 탐지율을 포함해서 운영자가 즉시 파악할 수 있게 했습니다.
> 
> SLA 모니터링과 별개입니다. SLA는 '시스템이 죽었나?', 이상거래 알림은 '의심스러운 거래가 있나?'를 체크합니다."

### 한계 및 개선점

**Q7. 이 프로젝트의 한계는?**

> "세 가지 한계가 있습니다.
> 
> 1. **단일 서버**: 실제로는 Kafka + Flink로 분산 처리 필요
> 2. **시뮬레이션 데이터**: 실제 결제 패턴과 100% 동일하지 않음
> 3. **ML 미적용**: 현재는 룰 기반, 실제로는 ML 모델 병행 사용
> 
> 하지만 파이프라인 설계 원리와 최적화 과정은 실제 시스템과 동일합니다."

---

## 작성자

- GitHub: [@Aguantar](https://github.com/Aguantar)
