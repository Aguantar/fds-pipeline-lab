# Part B: SLA 모니터링 & 이상거래 알림 (n8n)

## 1. 개요

FDS 파이프라인의 안정적 운영을 위해 **두 가지 알림 시스템**을 구축했다.

| 알림 유형 | 목적 | 조건 |
|----------|------|------|
| SLA 위반 | 파이프라인 장애 감지 | 처리량 < 1,000건/분 |
| 이상거래 탐지 | FDS 룰 탐지 알림 | fraud_count > 0 |

---

## 2. 아키텍처
```
┌─────────────────┐
│ Schedule Trigger│ (매 1분)
└────────┬────────┘
         ▼
┌─────────────────┐
│   PostgreSQL    │ (통합 쿼리)
│  - 처리량       │
│  - 이상거래 수  │
│  - 이상거래 금액│
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│  IF   │ │  IF1  │
│ SLA   │ │ Fraud │
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
[Slack]   [Slack]
[Gmail]   이상거래 알림
SLA 알림
```

---

## 3. 모니터링 쿼리
```sql
SELECT 
    COUNT(*) as total_count,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) as fraud_count,
    ROUND(SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as fraud_rate,
    COALESCE(SUM(CASE WHEN is_fraud THEN amount ELSE 0 END), 0) as fraud_amount
FROM fds.transactions
WHERE processed_at >= NOW() - INTERVAL '1 minute'
```

---

## 4. 알림 조건

### 4-1. SLA 위반 알림

| 조건 | 알림 채널 |
|------|----------|
| total_count < 1000 | Slack + Email |

**의미:** 파이프라인이 정상 작동하지 않음 (장애 감지)

### 4-2. 이상거래 탐지 알림

| 조건 | 알림 채널 |
|------|----------|
| fraud_count > 0 | Slack |

**의미:** FDS 룰에 의해 이상거래가 탐지됨

---

## 5. 알림 메시지

### SLA 위반
```
🚨 FDS Pipeline SLA 위반

처리량: {{ $json.total_count }}건/분 (최소 1,000건)
이상거래: {{ $json.fraud_count }}건
시간: {{ $now.format('yyyy-MM-dd HH:mm:ss') }}
```

### 이상거래 탐지
```
🚨 이상거래 탐지!

최근 1분간: {{ $json.fraud_count }}건
탐지 금액: {{ $json.fraud_amount.toLocaleString() }}원
탐지율: {{ $json.fraud_rate }}%
시간: {{ $now.format('yyyy-MM-dd HH:mm:ss') }}
```

---

## 6. 구현 시 주의사항

### 타입 변환 필요

PostgreSQL에서 반환된 숫자가 문자열로 인식될 수 있음.

**해결:** IF 노드에서 "Convert types where required" 옵션 활성화

---

## 7. 면접 예상 질문

**Q. 이상거래 탐지 시 어떻게 알림을 보내나요?**

> "n8n으로 1분마다 DB를 조회해서 이상거래 건수가 0보다 크면 Slack으로 알림을 보냅니다.
> 탐지 건수, 금액, 탐지율을 포함해서 운영자가 즉시 파악할 수 있게 했습니다."

**Q. SLA 모니터링과 이상거래 알림의 차이는?**

> "SLA 모니터링은 '파이프라인이 죽었나?' 체크입니다. 처리량이 기준 미달이면 시스템 장애로 판단합니다.
> 이상거래 알림은 '의심스러운 거래가 있나?' 체크입니다. FDS 룰에 걸린 거래가 있으면 알려줍니다.
> 둘 다 필요합니다. 시스템이 정상이어도 이상거래는 발생할 수 있고, 시스템이 죽으면 이상거래 탐지 자체가 안 되니까요."
