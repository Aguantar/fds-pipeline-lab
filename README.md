# FDS Pipeline Lab: 실시간 이상거래 탐지 파이프라인

> 토스 데이터 엔지니어 면접 대비 포트폴리오 프로젝트

## 프로젝트 개요

**목표:** 실시간 결제 데이터를 처리하고 이상거래를 탐지하는 파이프라인 구축 및 성능 최적화

**핵심 성과:**
- TPS 70 → 17,500 (250배 성능 개선)
- 단계별 병목 분석 및 해결
- Redis 버퍼를 통한 안정적인 비동기 처리

---

## 아키텍처
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Generator  │────▶│    Redis    │────▶│  Consumer   │────▶│ PostgreSQL  │
│ (결제 생성)  │     │   (Queue)   │     │ (FDS 검사)  │     │  (저장소)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
     │                    │                   │                    │
     │                    │                   │                    │
   10,000 TPS         버퍼 역할          FDS 룰 적용           최종 저장
   현실적 데이터       스파이크 흡수      이상거래 탐지         분석용 데이터
```

---

## 기술 스택

| 컴포넌트 | 기술 | 역할 |
|----------|------|------|
| Generator | Python, asyncio, Faker | 현실적인 결제 데이터 생성 |
| Queue | Redis | 메시지 버퍼, 비동기 처리 |
| Consumer | Python, asyncpg | FDS 룰 검사, DB 저장 |
| Database | PostgreSQL 15 | 트랜잭션 저장 |
| Container | Docker Compose | 환경 구성 |

---

## 성능 최적화 과정

### Phase 1: Baseline (동기 방식)
```
psycopg2.connect() → INSERT → close()
결과: TPS 70, Latency 15ms
```

### Phase 2: Connection Pool + Async
```
asyncpg.create_pool() → 재사용
결과: TPS 175 (2.5배 향상)
```

### Phase 2-B: 동시 요청
```
asyncio.gather() → 50개 동시 처리
결과: TPS 5,100 (73배 향상)
```

### Phase 2-C: Batch INSERT
```
executemany() → 100건씩 배치
결과: TPS 17,400 (248배 향상)
```

### Phase 2-D: Pool 200 + Batch 500
```
최대 설정으로 한계 테스트
결과: TPS 17,500 (250배 향상) - PostgreSQL 한계 도달
```

### Phase 3: Redis Buffer + Consumer
```
Generator → Redis → Consumer → PostgreSQL
결과: 안정적인 5,000 TPS 처리, Queue 균형 유지
```

---

## 성능 개선 요약

| Phase | 방식 | TPS | Latency | 개선율 |
|-------|------|-----|---------|--------|
| 1 | 동기, No Pool | 70 | 15ms | 기준 |
| 2 | Async + Pool | 175 | 2.8ms | 2.5배 |
| 2-B | 동시 요청 | 5,100 | 6.3ms | 73배 |
| 2-C | Batch INSERT | 17,400 | 0.26ms | 248배 |
| 2-D | Max Pool + Batch | 17,500 | 0.30ms | 250배 |
| 3 | Redis + Consumer | 5,000 | 80ms (E2E) | 안정적 |

---

## FDS 룰 엔진

### 탐지 규칙

| 룰 | 조건 | 설명 |
|----|------|------|
| Velocity | 1분 내 5회 이상 | 카드 도용 의심 |
| Amount Spike | 평소의 10배 이상 | 비정상 금액 |
| Dawn High Amount | 새벽 + 500만원 이상 | 시간대 이상 |
| Unusual Category | 일반등급 + 명품 1천만원 | 카테고리 이상 |

---

## 데이터 구조

### 현실적인 거래 데이터
```python
{
    'tx_id': 'uuid',
    'user_id': 'user_00123',        # 500명 사용자 풀
    'user_tier': 'vip',             # normal/premium/vip
    'card_number': '4532-****-****-1234',
    'amount': 45000,
    'merchant': '스타벅스',
    'merchant_category': 'coffee',  # 10개 카테고리
    'region': '서울',
    'hour': 14,
    'day_of_week': 2,
    'is_weekend': False,
    'time_slot': 'afternoon',
    'is_fraud': False,
    'fraud_rules': None
}
```

### 데이터 현실화 적용

- **사용자 풀**: 500명 (인당 평균 20건 결제)
- **카테고리별 영업시간**: 백화점 10~21시, 편의점 24시간
- **금액 분포**: 소액 70%, 중액 25%, 고액 5%
- **회식 반영**: 식당 5% 확률로 10만원 이상

---

## 실행 방법

### 사전 요구사항
- Docker & Docker Compose
- PostgreSQL (기존 인스턴스 또는 신규)

### 환경 설정
```bash
# .env 파일 생성
cp .env.example .env

# 환경 변수 수정
vi .env
```

### 실행
```bash
# Phase 3 실행 (Generator + Consumer)
docker compose --profile pipeline up generator consumer

# Redis Queue 확인
docker exec fds-redis redis-cli LLEN tx_queue

# DB 데이터 확인
docker exec -i my-postgres psql -U calme -d blood_db -c "
SELECT COUNT(*) FROM fds.transactions;
"
```

---

## 프로젝트 구조
```
fds-pipeline-lab/
├── README.md
├── docker-compose.yml
├── .env
├── database/
│   └── init_schema.sql
├── part-a-pipeline/
│   ├── generator/
│   │   ├── Dockerfile
│   │   ├── main.py              # 데이터 생성 + Redis 푸시
│   │   ├── config.py
│   │   ├── metrics.py
│   │   └── sample_data_generator.py
│   └── consumer/
│       ├── Dockerfile
│       ├── main.py              # Redis → FDS → PostgreSQL
│       ├── config.py
│       ├── metrics.py
│       └── fds_rules.py         # FDS 룰 엔진
├── part-b-sla/
│   └── airflow/                 # (예정)
├── analysis/
│   └── data/
│       └── sample_transactions.csv
└── docs/
    ├── 01-project-setup.md
    ├── 02-phase1-baseline-results.md
    ├── 03-phase2-optimization-results.md
    └── 04-phase3-redis-consumer.md
```

---

## 문서

| 문서 | 내용 |
|------|------|
| [01-project-setup.md](docs/01-project-setup.md) | 프로젝트 초기 설정, 인프라 구성 |
| [02-phase1-baseline-results.md](docs/02-phase1-baseline-results.md) | Phase 1 Baseline 측정 결과 |
| [03-phase2-optimization-results.md](docs/03-phase2-optimization-results.md) | Phase 2 성능 최적화 과정 |
| [04-phase3-redis-consumer.md](docs/04-phase3-redis-consumer.md) | Phase 3 Redis + Consumer 구현 |

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
> 이는 PostgreSQL의 WAL(Write-Ahead Log) 쓰기 병목으로 판단했습니다.
> Application 레벨 최적화의 한계이며, 더 올리려면 DB 튜닝이나 파티셔닝이 필요합니다."

---

## 향후 계획

- [ ] Part B: Airflow SLA 모니터링
- [ ] 데이터 분석 & 시각화 (Jupyter Notebook)
- [ ] n8n 웹훅 알림 연동
- [ ] 성능 테스트 자동화

---

## 작성자

- GitHub: [@Aguantar](https://github.com/Aguantar)
- 프로젝트: 토스 데이터 엔지니어 면접 대비
