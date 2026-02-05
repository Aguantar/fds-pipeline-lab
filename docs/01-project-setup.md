# 프로젝트 초기 설정 문서

## 1. 프로젝트 개요

### 프로젝트명
Real-Time Pipeline Lab with SLA Governance

### 목적
- 저사양 환경(Intel N100)에서 실시간 데이터 파이프라인 성능 최적화 실험
- Airflow 기반 SLA 모니터링 체계 구축
- 기존 운영 중인 인프라(PostgreSQL, n8n)와의 통합

### 핵심 메시지
> "파이프라인을 만드는 것에서 끝나지 않고, 운영 관점에서 안정성까지 고려했습니다"

---

## 2. 인프라 설계 결정

### 2-1. 기존 인프라 활용 (AS-IS → TO-BE)

| 컴포넌트 | 기존 상태 | 프로젝트 적용 | 결정 이유 |
|----------|----------|--------------|----------|
| PostgreSQL | `my-postgres` 운영 중 (헌혈 데이터) | 스키마 분리로 통합 | RAM 600MB 절약, 실무적 통합 경험 |
| n8n | `n8n.calmee.store` 운영 중 | 워크플로우 추가 | RAM 300MB 절약, 기존 자동화와 연계 |
| Redis | 없음 | 신규 추가 | 메시지 버퍼, FDS 캐시용 필수 |
| Airflow | 없음 | 신규 추가 | SLA 모니터링, 배치 스케줄링 |

### 2-2. 스키마 분리 전략
```
PostgreSQL (my-postgres)
├── public 스키마: 기존 헌혈 데이터 (영향 없음)
└── fds 스키마: 새 프로젝트 전용
    ├── transactions (거래 데이터)
    ├── daily_transaction_summary (일별 집계)
    ├── pipeline_completion_log (파이프라인 완료 기록)
    ├── sla_definitions (SLA 정의)
    └── sla_violations (SLA 위반 이력)
```

**면접 포인트:**
> "기존 운영 중인 DB에 새 프로젝트를 스키마 분리로 통합했습니다. 별도 DB 인스턴스를 띄우는 것보다 리소스 효율적이고, 실무에서도 이런 방식으로 멀티 테넌트 구조를 설계합니다."

### 2-3. 네트워크 구성
```
┌─────────────────────────────────────────────────────────────┐
│                    fds-network (Docker Bridge)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ my-postgres │  │  fds-redis  │  │ fds-generator/      │ │
│  │ (기존 연결)  │  │  (신규)     │  │ fds-consumer        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Airflow (webserver + scheduler) - 프로필: sla       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**면접 포인트:**
> "기존 PostgreSQL 컨테이너를 새 Docker 네트워크에 연결하여 신규 서비스들과 통신할 수 있게 구성했습니다. `docker network connect` 명령으로 운영 중단 없이 네트워크 연결이 가능합니다."

---

## 3. 리소스 계획

### 3-1. 하드웨어 제약

| 항목 | 사양 |
|------|------|
| CPU | Intel N100 (4C/4T, 최대 3.4GHz) |
| RAM | 16GB DDR4 |
| Storage | 512GB NVMe SSD |

### 3-2. 컨테이너별 예상 리소스

| 컨테이너 | RAM | 비고 |
|----------|-----|------|
| my-postgres (기존) | ~600MB | 이미 운영 중 |
| fds-redis | ~150MB | 신규 |
| fds-generator | ~300MB | 신규 |
| fds-consumer | ~300MB | 신규 |
| Airflow (전체) | ~1.5GB | 신규, sla 프로필 |
| **신규 추가분** | **~2.3GB** | |

**면접 포인트:**
> "제한된 리소스(16GB RAM)에서 기존 서비스 영향 없이 새 프로젝트를 배포하기 위해 리소스 사용량을 사전에 계산했습니다. 기존 인프라를 재활용하여 약 900MB를 절약했습니다."

---

## 4. Docker Compose 프로필 전략

### 4-1. 프로필 구성
```yaml
profiles:
  - pipeline  # Part A: Generator, Consumer
  - sla       # Part B: Airflow
```

### 4-2. 실행 시나리오

| 시나리오 | 명령어 | 실행되는 서비스 |
|----------|--------|----------------|
| 인프라만 | `docker compose up -d redis` | Redis |
| Part A 실험 | `docker compose --profile pipeline up -d` | Redis, Generator, Consumer |
| Part B 포함 전체 | `docker compose --profile pipeline --profile sla up -d` | 전체 |
| Part A 스파이크 테스트 | Airflow 중지 후 실행 | Redis, Generator, Consumer |

**면접 포인트:**
> "Docker Compose 프로필을 활용하여 실험 목적에 따라 서비스를 선택적으로 실행할 수 있게 구성했습니다. 특히 성능 측정 시 Airflow와 CPU 경합을 피하기 위해 프로필을 분리했습니다."

---

## 5. 데이터베이스 스키마 설계

### 5-1. Part A: 트랜잭션 관련
```sql
-- 메인 거래 테이블
CREATE TABLE fds.transactions (
    id SERIAL PRIMARY KEY,
    tx_id VARCHAR(50) UNIQUE NOT NULL,      -- 거래 고유 ID
    card_number VARCHAR(20) NOT NULL,        -- 카드 번호
    amount BIGINT NOT NULL,                  -- 거래 금액
    merchant VARCHAR(100),                   -- 가맹점
    is_fraud BOOLEAN DEFAULT false,          -- 사기 여부
    fraud_rules TEXT[],                      -- 탐지된 룰 목록
    created_at TIMESTAMP DEFAULT NOW(),      -- 생성 시각
    processed_at TIMESTAMP                   -- 처리 완료 시각
);

-- 인덱스 전략
CREATE INDEX idx_fds_transactions_created_at ON fds.transactions(created_at);
CREATE INDEX idx_fds_transactions_card_number ON fds.transactions(card_number);
CREATE INDEX idx_fds_transactions_is_fraud ON fds.transactions(is_fraud) WHERE is_fraud = true;
```

**인덱스 설계 이유:**
- `created_at`: 시계열 조회 (일별 집계, 최근 데이터 조회)
- `card_number`: FDS 룰에서 카드별 조회 빈번
- `is_fraud` (Partial Index): 사기 거래만 조회 시 효율적, 전체 대비 비율 낮아 Partial Index 적합

### 5-2. Part B: SLA 관련
```sql
-- SLA 정의 테이블
CREATE TABLE fds.sla_definitions (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,     -- 파이프라인 이름
    sla_type VARCHAR(20) NOT NULL,           -- hourly, daily, realtime
    deadline_minutes INT,                     -- 데드라인 (분)
    owner VARCHAR(50),                        -- 담당자
    slack_channel VARCHAR(50),                -- 알림 채널
    enabled BOOLEAN DEFAULT true              -- 활성화 여부
);

-- 초기 데이터
INSERT INTO fds.sla_definitions VALUES
(1, 'consumer_batch', 'hourly', 5, 'data-team', '#data-alerts', true),
(2, 'daily_aggregation', 'daily', 540, 'data-team', '#data-alerts', true);
```

**SLA 정의 설명:**
- `consumer_batch`: 매 시간 정각 + 5분 내 최소 1회 Batch 처리 완료
- `daily_aggregation`: 매일 09:00 (540분) 까지 전일 집계 완료

**면접 포인트:**
> "SLA를 코드가 아닌 테이블로 관리하여 운영 중 동적으로 SLA 기준을 변경할 수 있게 설계했습니다. 새로운 파이프라인이 추가되면 INSERT만으로 SLA 모니터링이 가능합니다."

---

## 6. 환경 변수 관리

### 6-1. .env 파일 구조
```env
# PostgreSQL (기존 인프라 연결)
POSTGRES_HOST=my-postgres
POSTGRES_PORT=5432
POSTGRES_USER=calme
POSTGRES_PASSWORD=****
POSTGRES_DB=blood_db
POSTGRES_SCHEMA=fds

# Redis (신규)
REDIS_HOST=fds-redis
REDIS_PORT=6379

# Airflow (신규)
FERNET_KEY=<generated>
SECRET_KEY=<generated>

# Part A 설정 (실험 파라미터)
PHASE=1
TPS=100
BATCH_SIZE=500

# n8n 웹훅
N8N_WEBHOOK_URL=https://n8n.calmee.store/webhook/sla-alert
```

### 6-2. 민감 정보 관리

| 항목 | 관리 방법 |
|------|----------|
| DB 비밀번호 | .env 파일 (git ignore) |
| Fernet Key | Python으로 생성, .env 저장 |
| Secret Key | Python으로 생성, .env 저장 |

**면접 포인트:**
> "민감 정보는 .env 파일로 분리하고 .gitignore에 등록하여 버전 관리에서 제외했습니다. 프로덕션에서는 AWS Secrets Manager나 HashiCorp Vault 같은 시크릿 관리 도구를 사용하는 것이 좋습니다."

---

## 7. 초기 설정 실행 기록

### 7-1. 실행한 명령어 순서
```bash
# 1. 디렉토리 구조 생성
mkdir -p ~/fds-pipeline-lab
cd ~/fds-pipeline-lab
mkdir -p part-a-pipeline/generator
mkdir -p part-a-pipeline/consumer
mkdir -p part-a-pipeline/scripts
mkdir -p part-b-sla/airflow/dags
mkdir -p database
mkdir -p analysis/data
mkdir -p docs

# 2. PostgreSQL에 fds 스키마 생성
docker exec -i my-postgres psql -U calme -d blood_db < database/init_schema.sql

# 3. 환경 변수 파일 생성
# .env 파일 생성 및 Fernet Key 자동 생성

# 4. Docker Compose, Dockerfile 생성

# 5. 네트워크 구성 및 Redis 실행
docker network create fds-network
docker network connect fds-network my-postgres
docker compose up -d redis
```

### 7-2. 검증 결과
```bash
# 스키마 확인
$ docker exec -it my-postgres psql -U calme -d blood_db -c "\dn"
      List of schemas
  Name  |       Owner       
--------+-------------------
 fds    | calme
 public | pg_database_owner

# 테이블 확인
$ docker exec -it my-postgres psql -U calme -d blood_db -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'fds';"
        table_name         
---------------------------
 transactions
 daily_transaction_summary
 pipeline_completion_log
 sla_definitions
 sla_violations

# Redis 연결 확인
$ docker exec -it fds-redis redis-cli ping
PONG
```

---

## 8. 현재 상태 (1일차 완료)

| 항목 | 상태 | 비고 |
|------|------|------|
| 프로젝트 디렉토리 | ✅ 완료 | ~/fds-pipeline-lab |
| PostgreSQL fds 스키마 | ✅ 완료 | 5개 테이블 |
| .env 파일 | ✅ 완료 | Fernet Key 포함 |
| docker-compose.yml | ✅ 완료 | 프로필 분리 |
| Generator Dockerfile | ✅ 완료 | 임시 main.py |
| Consumer Dockerfile | ✅ 완료 | 임시 main.py |
| Airflow Dockerfile | ✅ 완료 | DAG 미작성 |
| Redis | ✅ 실행 중 | 포트 6379 |
| 네트워크 | ✅ 완료 | my-postgres 연결됨 |

---

## 9. 다음 단계 예고

### 2일차: Part A - Generator/Consumer 실제 코드 작성

1. **Phase 1 (Baseline)**: 동기 방식 직접 INSERT
2. 성능 측정 및 병목 분석
3. **Phase 2**: Async + Connection Pool
4. **Phase 3**: Redis 버퍼 + Batch Consumer

### 3주차: Part B - Airflow SLA 모니터링

1. Airflow DAG 작성 (SLA Checker, Daily Aggregation)
2. n8n 웹훅 연동
3. SLA 위반 알림 테스트

---

## 10. 면접 예상 질문 및 답변

### Q1. 왜 별도 DB를 안 띄우고 기존 DB에 스키마를 추가했나요?

> "리소스 효율성 때문입니다. N100 미니 PC의 16GB RAM에서 PostgreSQL 인스턴스 하나가 약 600MB를 사용합니다. 별도 인스턴스를 띄우면 그만큼 Part A 성능 실험에 사용할 리소스가 줄어듭니다. 또한 실무에서도 단일 DB에 스키마를 분리하여 멀티 테넌트 구조로 운영하는 경우가 많기 때문에, 이 방식이 더 현실적인 경험이라고 판단했습니다."

### Q2. Docker 네트워크는 어떻게 구성했나요?

> "새로운 Docker 네트워크(fds-network)를 생성하고, 기존에 운영 중이던 my-postgres 컨테이너를 이 네트워크에 연결했습니다. `docker network connect` 명령을 사용하면 컨테이너 재시작 없이 네트워크를 추가할 수 있어서, 기존 서비스 영향 없이 연결할 수 있었습니다."

### Q3. 왜 Docker Compose 프로필을 사용했나요?

> "Part A 성능 측정과 Part B SLA 모니터링의 리소스 경합을 피하기 위해서입니다. 특히 스파이크 테스트(초당 2,000건)를 할 때 Airflow가 함께 돌면 CPU가 100%를 칠 수 있습니다. 프로필을 분리해두면 `--profile pipeline`만으로 Part A만 실행할 수 있어서 순수한 성능 측정이 가능합니다."

### Q4. SLA 정의를 왜 테이블로 관리하나요?

> "운영 유연성 때문입니다. 코드에 하드코딩하면 SLA 기준 변경 시 배포가 필요하지만, 테이블로 관리하면 UPDATE 쿼리 하나로 즉시 반영됩니다. 새로운 파이프라인이 추가될 때도 INSERT만 하면 자동으로 모니터링 대상에 포함됩니다."
