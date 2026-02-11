# FDS Pipeline Lab: 실시간 이상거래 탐지 파이프라인

> 데이터 엔지니어 포트폴리오 프로젝트

## 프로젝트 개요

**목표:** 실시간 결제 데이터를 처리하고 이상거래를 탐지하는 파이프라인 구축 및 성능 최적화

**핵심 성과:**
- TPS 70 → 17,500 (250배 성능 개선)
- 단계별 병목 분석 및 해결
- Redis 버퍼를 통한 안정적인 비동기 처리
- FDS 룰 엔진으로 5% 이상거래 탐지
- SLA 모니터링 (Slack/Email 알림)

---

## 아키텍처
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Generator  │────▶│    Redis    │────▶│  Consumer   │────▶│ PostgreSQL  │
│ (결제 생성)  │     │   (Queue)   │     │ (FDS 검사)  │     │  (저장소)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                              ┌────────────────────┘
                                              ▼
                                        ┌───────────┐
                                        │    n8n    │
                                        │ SLA 모니터 │
                                        └─────┬─────┘
                                              │ SLA 위반 시
                                        ┌─────┴─────┐
                                        ▼           ▼
                                    [Slack]     [Gmail]
```

---

## 기술 스택

| 컴포넌트 | 기술 | 역할 |
|----------|------|------|
| Generator | Python, asyncio | 현실적인 결제 데이터 생성 |
| Queue | Redis | 메시지 버퍼, 비동기 처리 |
| Consumer | Python, asyncpg | FDS 룰 검사, DB 저장 |
| Database | PostgreSQL 15 | 트랜잭션 저장 |
| Monitoring | n8n | SLA 모니터링, 알림 |
| Container | Docker Compose | 환경 구성 |

---

## 성능 최적화 과정

| Phase | 방식 | TPS | Latency | 개선율 |
|-------|------|-----|---------|--------|
| 1 | 동기, No Pool | 70 | 15ms | 기준 |
| 2 | Async + Pool | 175 | 2.8ms | 2.5배 |
| 2-B | 동시 요청 | 5,100 | 6.3ms | 73배 |
| 2-C | Batch INSERT | 17,400 | 0.26ms | 248배 |
| 2-D | Max Pool + Batch | 17,500 | 0.30ms | **250배** |
| 3 | Redis + Consumer | 5,000 | 80ms (E2E) | 안정적 |

### 병목 분석
```
Phase 1: Connection 생성 오버헤드 → Pool 도입
Phase 2: 순차 처리 → 동시 요청 + Batch
Phase 2-D: PostgreSQL WAL I/O 한계 도달
Phase 3: Producer-Consumer 분리로 안정성 확보
```

---

## FDS 룰 엔진

### 탐지 규칙

| 룰 | 조건 | 설명 |
|----|------|------|
| Velocity | 1분 내 5회 이상 | 카드 도용 의심 |
| Amount Spike | 평소의 10배 이상 | 비정상 금액 |
| Dawn High Amount | 새벽 + 500만원 이상 | 시간대 이상 |
| Unusual Category | 일반등급 + 명품 1천만원 | 카테고리 이상 |

### 탐지 결과

| 항목 | 값 |
|------|-----|
| 총 거래 | 100,000건 |
| 이상거래 | 5,070건 (5.07%) |
| 정상 거래 평균 | 109,353원 |
| 이상 거래 평균 | 3,744,844원 (34배) |

---

## SLA 모니터링

### 워크플로우
```
Schedule Trigger (1분) → PostgreSQL 조회 → IF (처리량 < 1,000) → Slack + Gmail 알림
```

### SLA 정의

| SLA | 조건 | 알림 |
|-----|------|------|
| Consumer 처리량 | 1분간 < 1,000건 | Slack + Email |

---

## 데이터 현실화

### 설정

| 항목 | 값 |
|------|-----|
| 유저 풀 | 100,000명 |
| 카테고리 | 10개 (편의점, 커피, 식당 등) |
| 가맹점 | 49개 |
| 지역 | 10개 (서울 30%, 경기 25% 등) |

### 분포

| 항목 | 분포 |
|------|------|
| 시간대 | 새벽 11%, 낮/저녁 68% |
| 금액 | 소액 72%, 중액 24%, 고액 4% |
| 유저당 거래 | 1건 57%, 2건 28% |

---

## 실행 방법

### 환경 설정
```bash
cp .env.example .env
vi .env
```

### 실행
```bash
# 파이프라인 실행
docker compose --profile pipeline up generator consumer

# 데이터 확인
docker exec -i my-postgres psql -U calme -d blood_db -c "
SELECT COUNT(*), SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) as fraud
FROM fds.transactions;
"
```

---

## 프로젝트 구조
```
fds-pipeline-lab/
├── README.md
├── docker-compose.yml
├── .env
├── part-a-pipeline/
│   ├── generator/          # 데이터 생성
│   │   ├── main.py
│   │   └── config.py
│   └── consumer/           # FDS + DB 저장
│       ├── main.py
│       └── fds_rules.py
├── analysis/
│   ├── notebooks/          # Jupyter 분석
│   └── data/               # 시각화 이미지
└── docs/
    ├── 01-project-setup.md
    ├── 02-phase1-baseline-results.md
    ├── 03-phase2-optimization-results.md
    ├── 04-phase3-redis-consumer.md
    ├── 05-part-b-sla-monitoring.md
    └── 06-data-analysis.md
```

---

## 문서

| 문서 | 내용 |
|------|------|
| [01-project-setup](docs/01-project-setup.md) | 프로젝트 초기 설정 |
| [02-phase1-baseline](docs/02-phase1-baseline-results.md) | Baseline 측정 (TPS 70) |
| [03-phase2-optimization](docs/03-phase2-optimization-results.md) | 성능 최적화 (TPS 17,500) |
| [04-phase3-redis-consumer](docs/04-phase3-redis-consumer.md) | Redis + Consumer 구현 |
| [05-sla-monitoring](docs/05-part-b-sla-monitoring.md) | n8n SLA 모니터링 |
| [06-data-analysis](docs/06-data-analysis.md) | 데이터 분석 결과 |

---

## 면접 예상 질문

### Q1. 왜 Connection Pool을 사용했나요?

> "매 요청마다 DB 연결을 생성하면 TCP handshake, 인증 과정이 반복됩니다. 
> 실험 결과 15ms 중 약 10ms가 이 오버헤드였습니다.
> Pool을 사용하면 미리 만들어둔 연결을 재사용하므로 Latency가 2.8ms로 줄었습니다."

### Q2. Redis를 왜 사용했나요?

> "Generator와 Consumer의 처리 속도 차이를 흡수하기 위해 버퍼로 사용했습니다.
> 트래픽 스파이크 시에도 데이터 유실 없이 순차 처리가 가능하고,
> DB 장애 시에도 Queue에 데이터가 보관되어 복구 후 처리할 수 있습니다."

### Q3. TPS 17,500에서 더 이상 안 올라간 이유는?

> "CPU가 44%로 여유가 있었지만 TPS가 안 올랐습니다.
> PostgreSQL의 WAL(Write-Ahead Log) 쓰기 병목으로 판단했습니다.
> 더 올리려면 DB 튜닝, 파티셔닝, 또는 분산 DB가 필요합니다."

### Q4. SLA 모니터링을 어떻게 구현했나요?

> "n8n으로 1분마다 DB를 조회해서 처리량이 기준 미달이면 Slack과 Email로 알림을 보냅니다.
> 복잡한 DAG 의존성이 없어서 Airflow 대신 기존 n8n 인프라를 활용했습니다."

---

## 작성자

- GitHub: [@Aguantar](https://github.com/Aguantar)
