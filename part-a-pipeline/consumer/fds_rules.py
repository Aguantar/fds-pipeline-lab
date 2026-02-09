"""
FDS (Fraud Detection System) 룰 엔진
이상거래 탐지 규칙 정의
"""

from collections import defaultdict
import time

class FDSRuleEngine:
    def __init__(self):
        # 사용자별 최근 거래 기록 (velocity 체크용)
        self.user_history = defaultdict(list)
        # 사용자별 평균 거래 금액 (amount spike 체크용)
        self.user_avg_amount = defaultdict(lambda: {'sum': 0, 'count': 0})
        
        # 설정값
        self.velocity_window = 60  # 60초
        self.velocity_threshold = 5  # 5회 이상
        self.amount_spike_ratio = 10  # 평소의 10배
        self.high_amount_threshold = 5000000  # 500만원 이상 고액
        self.dawn_hours = (0, 1, 2, 3, 4, 5)  # 새벽 시간
    
    def check(self, tx: dict) -> tuple:
        """
        트랜잭션 검사
        Returns: (is_fraud: bool, fraud_rules: list)
        """
        fraud_rules = []
        user_id = tx['user_id']
        amount = tx['amount']
        hour = tx.get('hour', 12)
        category = tx.get('merchant_category', '')
        current_time = tx.get('created_at', time.time())
        
        # 1. Velocity Check: 1분 내 5회 이상 결제
        self._update_history(user_id, current_time)
        recent_count = self._get_recent_count(user_id, current_time)
        if recent_count >= self.velocity_threshold:
            fraud_rules.append(f"VELOCITY: {recent_count}회/분")
        
        # 2. Amount Spike: 평소의 10배 이상
        avg_amount = self._get_avg_amount(user_id)
        if avg_amount > 0 and amount > avg_amount * self.amount_spike_ratio:
            fraud_rules.append(f"AMOUNT_SPIKE: {amount:,}원 (평균 {avg_amount:,.0f}원의 {amount/avg_amount:.1f}배)")
        self._update_avg_amount(user_id, amount)
        
        # 3. High Amount at Dawn: 새벽 고액 결제
        if hour in self.dawn_hours and amount >= self.high_amount_threshold:
            fraud_rules.append(f"DAWN_HIGH_AMOUNT: 새벽 {hour}시 {amount:,}원")
        
        # 4. Unusual Category: VIP 아닌데 명품 고액
        if category == 'luxury' and tx.get('user_tier') == 'normal' and amount >= 10000000:
            fraud_rules.append(f"UNUSUAL_CATEGORY: 일반등급 명품 {amount:,}원")
        
        is_fraud = len(fraud_rules) > 0
        return is_fraud, fraud_rules
    
    def _update_history(self, user_id: str, current_time: float):
        """사용자 거래 기록 업데이트"""
        self.user_history[user_id].append(current_time)
        # 오래된 기록 제거 (1분 이전)
        cutoff = current_time - self.velocity_window
        self.user_history[user_id] = [
            t for t in self.user_history[user_id] if t > cutoff
        ]
    
    def _get_recent_count(self, user_id: str, current_time: float) -> int:
        """최근 1분간 거래 횟수"""
        cutoff = current_time - self.velocity_window
        return sum(1 for t in self.user_history[user_id] if t > cutoff)
    
    def _get_avg_amount(self, user_id: str) -> float:
        """사용자 평균 거래 금액"""
        data = self.user_avg_amount[user_id]
        if data['count'] == 0:
            return 0
        return data['sum'] / data['count']
    
    def _update_avg_amount(self, user_id: str, amount: int):
        """평균 금액 업데이트 (최근 100건 기준)"""
        data = self.user_avg_amount[user_id]
        data['sum'] += amount
        data['count'] += 1
        # 100건 넘으면 오래된 것 제거 (이동평균)
        if data['count'] > 100:
            data['sum'] = data['sum'] * 0.99
            data['count'] = 100
