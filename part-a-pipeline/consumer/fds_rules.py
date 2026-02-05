import redis
from typing import Optional

class FDSRules:
    """
    이상거래탐지(FDS) 룰 엔진
    - Velocity Check: 동일 카드 1분 내 5회 이상 결제
    - Amount Anomaly: 평균 금액의 10배 초과
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.VELOCITY_THRESHOLD = 5
        self.VELOCITY_WINDOW = 60  # seconds
        self.AMOUNT_MULTIPLIER = 10
    
    def velocity_check(self, card_number: str) -> bool:
        """
        동일 카드로 1분 내 5회 이상 결제 시 의심
        Redis INCR + EXPIRE 활용
        """
        key = f"velocity:{card_number}"
        
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, self.VELOCITY_WINDOW)
        
        return count >= self.VELOCITY_THRESHOLD
    
    def amount_anomaly(self, card_number: str, amount: int) -> bool:
        """
        해당 카드의 최근 평균 금액의 10배 초과 시 의심
        Redis Hash로 이동평균 관리
        """
        key = f"amount_avg:{card_number}"
        
        data = self.redis.hgetall(key)
        
        if not data:
            # 첫 거래: 기준값 설정
            self.redis.hset(key, mapping={'sum': amount, 'count': 1})
            self.redis.expire(key, 86400)  # 24시간 유지
            return False
        
        # 평균 계산
        total_sum = int(data.get(b'sum', 0))
        total_count = int(data.get(b'count', 0))
        
        if total_count == 0:
            return False
        
        avg = total_sum / total_count
        
        # 통계 업데이트
        self.redis.hincrby(key, 'sum', amount)
        self.redis.hincrby(key, 'count', 1)
        
        return amount > avg * self.AMOUNT_MULTIPLIER
    
    def check(self, card_number: str, amount: int) -> dict:
        """
        모든 룰 체크 실행
        """
        result = {
            'is_fraud': False,
            'rules_triggered': []
        }
        
        if self.velocity_check(card_number):
            result['is_fraud'] = True
            result['rules_triggered'].append('velocity')
        
        if self.amount_anomaly(card_number, amount):
            result['is_fraud'] = True
            result['rules_triggered'].append('amount_anomaly')
        
        return result
