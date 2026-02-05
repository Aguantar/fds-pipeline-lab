# Phase 1: Baseline (동기 방식) 실험 결과

## 1. 실험 개요

### 목적
- 가장 기본적인 동기 방식의 성능 한계 측정
- 병목 지점 파악

### 아키텍처
```
[Generator] → [PostgreSQL]
           (psycopg2, Sync, No Pool)
```

### 특징
- 매 INSERT마다 새 Connection 생성
- Connection Pool 없음
- 동기 방식 (요청 완료까지 대기)

---

## 2. 실험 환경

| 항목 | 값 |
|------|-----|
| CPU | Intel N100 (4C/4T) |
| RAM | 16GB |
| PostgreSQL | 15 (Docker) |
| Python | 3.11 |
| Driver | psycopg2 |

---

## 3. 실험 결과

### TPS 50 테스트

| 지표 | 값 |
|------|-----|
| 목표 TPS | 50 |
| **실제 TPS** | **~50** |
| Latency (avg) | ~16ms |
| Latency (P95) | ~18.5ms |
| CPU 사용률 | ~28% |
| Memory 사용률 | ~12% |
| Error Rate | 0% |

**결과:** 목표 TPS 달성, 시스템 여유 있음

### TPS 200 테스트

| 지표 | 값 |
|------|-----|
| 목표 TPS | 200 |
| **실제 TPS** | **~65-75** |
| Latency (avg) | ~15ms |
| Latency (P95) | ~17.5ms |
| CPU 사용률 | ~35% |
| Memory 사용률 | ~12% |
| Error Rate | 0% |

**결과:** 목표 TPS 미달성, 병목 발생

---

## 4. 병목 분석

### 병목 지점: DB Connection 생성 오버헤드

| 가능한 원인 | 분석 | 결론 |
|------------|------|------|
| CPU | 35%로 여유 있음 | ❌ 원인 아님 |
| Memory | 12%로 여유 있음 | ❌ 원인 아님 |
| Network | Latency 15ms로 정상 | ❌ 원인 아님 |
| **Connection 생성** | 매번 connect/close 반복 | ⭐ **주 원인** |

### 코드 분석
```python
def insert_sync(tx: dict) -> float:
    conn = psycopg2.connect(...)  # 매번 새 연결 (비용 발생)
    cur = conn.cursor()
    cur.execute(...)
    conn.commit()
    cur.close()
    conn.close()  # 매번 연결 종료 (비용 발생)
```

**문제점:**
1. TCP 3-way handshake 매번 발생
2. PostgreSQL 인증 프로세스 매번 실행
3. Connection 객체 생성/소멸 오버헤드

### 추정 계산

- Latency ~15ms 중 실제 INSERT 시간은 ~5ms 미만
- 나머지 ~10ms는 Connection 생성/종료 오버헤드
- 이론상 최대 TPS: 1000ms / 15ms ≈ **66 TPS**
- 실측 TPS: **65-75 TPS** (추정과 일치)

---

## 5. 개선 방향

### Phase 2에서 적용할 최적화

1. **Connection Pool 도입**
   - 미리 Connection을 만들어두고 재사용
   - Connection 생성 오버헤드 제거

2. **Async I/O 도입**
   - asyncpg 사용
   - I/O 대기 시간 동안 다른 작업 처리

### 예상 개선 효과

| 최적화 | 예상 TPS |
|--------|----------|
| 현재 (Phase 1) | ~70 |
| Connection Pool | ~150-200 |
| + Async I/O | ~300-500 |

---

## 6. 메트릭 데이터

### 파일 위치
- `analysis/data/phase1_generator_metrics.csv`
- `analysis/data/phase1_generator_metrics_final.csv` (백업)

### 샘플 데이터
```csv
timestamp,tps,success_count,error_count,error_rate,latency_avg_ms,latency_p50_ms,latency_p95_ms,latency_p99_ms,cpu_percent,memory_percent,queue_length
2026-02-04T08:40:59.661721,49.76,498,0,0.0,15.99,17.09,18.64,19.15,27.7,12.1,0
2026-02-04T08:49:43.740621,67.28,673,0,0.0,14.44,15.84,17.38,18.0,36.5,12.0,0
```

---

## 7. 면접 포인트

### Q. Phase 1에서 발견한 병목은 무엇인가요?

> "매 요청마다 DB Connection을 생성하고 종료하는 방식의 한계를 발견했습니다. 
> TPS 50에서는 문제없었지만, TPS 200을 목표로 했을 때 실제로는 65-75 TPS밖에 나오지 않았습니다.
> CPU는 35%로 여유가 있었기 때문에, 병목은 Connection 생성 오버헤드라고 판단했습니다.
> Latency 15ms 중 실제 INSERT는 5ms 미만이고, 나머지 10ms가 Connection 비용입니다."

### Q. 이 문제를 어떻게 해결할 수 있나요?

> "Connection Pool을 도입하면 됩니다. 미리 Connection을 만들어두고 재사용하면 
> TCP handshake와 인증 과정을 매번 거치지 않아도 됩니다.
> 추가로 asyncpg를 사용하여 비동기 I/O를 적용하면 I/O 대기 시간에 다른 요청을 처리할 수 있어 
> TPS를 더 높일 수 있습니다. 이것이 Phase 2에서 검증할 내용입니다."

---

## 8. 총 데이터

| 항목 | 값 |
|------|-----|
| 총 트랜잭션 수 | 17,348건 |
| 실험 시간 | 약 5분 |
| 메트릭 샘플 수 | 25개 (10초 간격) |
