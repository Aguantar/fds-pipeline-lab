# Part B: SLA 모니터링 (n8n)

## 1. 개요

### 왜 n8n을 선택했는가?

처음에는 Airflow로 설계했으나, 실제 구현 단계에서 재검토한 결과:

| 도구 | 장점 | 단점 |
|------|------|------|
| Airflow | 복잡한 DAG, 배치 작업에 적합 | 단순 모니터링에는 오버스펙 |
| n8n | 기존 인프라 활용, GUI, 빠른 구축 | 복잡한 의존성 처리 어려움 |

**결론:** 단순 SLA 모니터링에는 n8n이 더 적합

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
- 동일한 내용

---

## 6. 설정 과정

### 6-1. n8n-PostgreSQL 네트워크 연결

n8n과 FDS 파이프라인이 다른 Docker 네트워크에 있어서 연결 필요:
```bash
# n8n 컨테이너를 fds-network에 연결
docker network connect fds-network n8n-n8n-1
docker network connect fds-network n8n-worker-1
```

### 6-2. Slack 연동

1. Slack App 생성 (https://api.slack.com/apps)
2. OAuth & Permissions에서 Bot Token Scopes 추가:
   - `chat:write`
   - `chat:write.public`
3. Bot User OAuth Token 복사
4. n8n Slack Credential에 토큰 입력
5. 봇을 채널에 초대

### 6-3. Gmail 연동

1. Google Cloud Console에서 OAuth 클라이언트 생성
2. Gmail API 활성화
3. 테스트 사용자 추가
4. n8n Gmail OAuth2 Credential 설정

---

## 7. 면접 예상 질문

### Q1. 왜 Airflow 대신 n8n을 선택했나요?

> "처음에는 Airflow로 설계했습니다. 하지만 이 프로젝트의 모니터링 요구사항은 단순합니다.
> 1분마다 DB 조회 후 조건 체크하고 알림 보내는 게 전부예요.
> 복잡한 DAG 의존성이나 재처리 기능이 필요 없어서, 이미 운영 중인 n8n을 활용하는 게
> 리소스도 절약되고 유지보수도 쉽다고 판단했습니다."

### Q2. Airflow가 더 적합한 경우는?

> "배치 작업이 복잡한 경우입니다. 예를 들어:
> - 일별 데이터 집계 → 주간 리포트 생성 → S3 업로드
> - 실패 시 특정 날짜만 재처리
> - 여러 데이터 소스 간 의존성 관리
> 이런 경우에는 Airflow의 DAG, 백필, 태스크 의존성 기능이 필요합니다."

---

## 8. 다음 단계

- [ ] 데이터 분석 & 시각화
- [ ] SLA 확장 (Queue 길이, Fraud 비율 등)
