# Part B: SLA 모니터링 (n8n)

## 1. 개요

FDS 파이프라인의 안정적 운영을 위해 SLA 모니터링 시스템을 구축했다.

### 기술 선택: n8n

| 선택 이유 |
|-----------|
| 단순 모니터링 (1분마다 DB 조회 → 조건 체크 → 알림) |
| 기존 인프라 활용 가능 |
| GUI 기반 빠른 구축 |
| 복잡한 DAG 의존성 불필요 |

---

## 2. 아키텍처
```
┌─────────────────┐
│ Schedule Trigger│ (매 1분)
└────────┬────────┘
         ▼
┌─────────────────┐
│   PostgreSQL    │ (SLA 체크 쿼리)
│  - 처리량 확인   │
│  - 이상거래 비율 │
└────────┬────────┘
         ▼
┌─────────────────┐
│       IF        │ (처리량 < 1,000건?)
└────────┬────────┘
         ▼ True
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│ Slack │ │ Gmail │
│ 알림  │ │ 알림  │
└───────┘ └───────┘
```

---

## 3. SLA 정의

| SLA | 조건 | 알림 |
|-----|------|------|
| Consumer 처리량 | 1분간 처리량 < 1,000건 | ⚠️ Slack + Email |

---

## 4. 모니터링 쿼리
```sql
SELECT 
    COUNT(*) as total_count,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) as fraud_count,
    ROUND(SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as fraud_rate
FROM fds.transactions
WHERE processed_at >= NOW() - INTERVAL '1 minute'
```

---

## 5. 알림 메시지

### Slack
```
🚨 FDS Pipeline SLA 위반

처리량: {{ $json.total_count }}건/분 (최소 1,000건)
이상거래: {{ $json.fraud_count }}건
시간: {{ $now.format('yyyy-MM-dd HH:mm:ss') }}
```

### Email
- 제목: 🚨 FDS Pipeline SLA 위반 알림
- 내용: Slack과 동일

---

## 6. 구현 상세

### 6-1. 네트워크 연결

n8n과 FDS 파이프라인이 다른 Docker 네트워크에 있어 연결 필요:
```bash
docker network connect fds-network n8n-n8n-1
docker network connect fds-network n8n-worker-1
```

### 6-2. Slack 연동

1. Slack App 생성 (https://api.slack.com/apps)
2. Bot Token Scopes: `chat:write`, `chat:write.public`
3. Bot User OAuth Token → n8n Credential
4. 봇을 채널에 초대

### 6-3. Gmail 연동

1. Google Cloud Console → OAuth 클라이언트 생성
2. Gmail API 활성화
3. 테스트 사용자 추가
4. n8n Gmail OAuth2 Credential 설정

---

## 7. 면접 예상 질문

**Q. SLA 모니터링을 어떻게 구현했나요?**

> "n8n으로 1분마다 DB를 조회해서 처리량이 기준 미달이면 Slack과 Email로 알림을 보냅니다.
> 복잡한 워크플로우가 아니라 단순 모니터링이라서 Airflow 같은 무거운 도구 대신
> 기존에 운영 중인 n8n을 활용했습니다."

**Q. SLA 기준은 어떻게 정했나요?**

> "파이프라인 정상 운영 시 TPS 약 100, 즉 분당 6,000건 처리합니다.
> 1,000건 미만이면 심각한 장애 상황이라 판단해서 이 기준을 설정했습니다."
