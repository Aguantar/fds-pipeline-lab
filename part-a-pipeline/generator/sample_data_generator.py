import uuid
import random
import time
import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================
# 사용자 풀 (500명으로 축소)
# ============================================

NUM_USERS = 500
random.seed(42)

USER_IDS = [f"user_{i:05d}" for i in range(NUM_USERS)]

USER_CARDS = {
    user_id: f"4532-****-****-{random.randint(1000, 9999)}"
    for user_id in USER_IDS
}

USER_TIERS = {}
for user_id in USER_IDS:
    rand = random.random()
    if rand < 0.02:      # 2% VIP (10명)
        USER_TIERS[user_id] = 'vip'
    elif rand < 0.15:    # 13% Premium (65명)
        USER_TIERS[user_id] = 'premium'
    else:                # 85% Normal (425명)
        USER_TIERS[user_id] = 'normal'

REGIONS = ['서울', '경기', '인천', '부산', '대구', '광주', '대전', '울산', '세종', '제주']
REGION_WEIGHTS = [30, 25, 10, 8, 5, 4, 4, 3, 1, 10]

USER_REGIONS = {
    user_id: random.choices(REGIONS, weights=REGION_WEIGHTS, k=1)[0]
    for user_id in USER_IDS
}

# ============================================
# 가맹점 데이터 (지점명 제거, 영업시간 추가)
# ============================================

MERCHANTS = {
    'convenience': {
        'names': ['CU', 'GS25', '세븐일레븐', '이마트24', '미니스톱'],
        'amount_range': (1000, 30000),
        'weight': 25,
        'hours': (0, 24)  # 24시간
    },
    'coffee': {
        'names': ['스타벅스', '투썸플레이스', '이디야', '메가커피', '빽다방'],
        'amount_range': (3000, 15000),
        'weight': 20,
        'hours': (7, 22)  # 7시~22시
    },
    'restaurant': {
        'names': ['맥도날드', '버거킹', '교촌치킨', '피자헛', '본죽', '한신포차', '새마을식당'],
        'amount_range': (5000, 300000),  # 회식 반영
        'weight': 20,
        'hours': (6, 24)  # 6시~24시
    },
    'delivery': {
        'names': ['배달의민족', '쿠팡이츠', '요기요'],
        'amount_range': (15000, 100000),
        'weight': 12,
        'hours': (10, 2)  # 10시~새벽2시
    },
    'online_shopping': {
        'names': ['쿠팡', '네이버쇼핑', 'SSG닷컴', '11번가', '무신사'],
        'amount_range': (10000, 500000),
        'weight': 10,
        'hours': (0, 24)  # 24시간
    },
    'supermarket': {
        'names': ['이마트', '홈플러스', '롯데마트', '코스트코', '트레이더스'],
        'amount_range': (30000, 300000),
        'weight': 5,
        'hours': (10, 22)  # 10시~22시
    },
    'fashion': {
        'names': ['자라', 'H&M', '유니클로', '나이키', '아디다스'],
        'amount_range': (30000, 500000),
        'weight': 4,
        'hours': (10, 21)  # 10시~21시
    },
    'electronics': {
        'names': ['삼성스토어', '애플스토어', '하이마트', '롯데하이마트'],
        'amount_range': (50000, 3000000),
        'weight': 2,
        'hours': (10, 21)  # 10시~21시
    },
    'luxury': {
        'names': ['루이비통', '샤넬', '구찌', '에르메스', '롤렉스'],
        'amount_range': (500000, 50000000),
        'weight': 1,
        'hours': (10, 20)  # 10시~20시
    },
    'travel': {
        'names': ['대한항공', '아시아나항공', '야놀자', '여기어때', '마이리얼트립'],
        'amount_range': (50000, 5000000),
        'weight': 1,
        'hours': (0, 24)  # 24시간 (온라인)
    }
}

CATEGORIES = list(MERCHANTS.keys())
CATEGORY_WEIGHTS = [MERCHANTS[cat]['weight'] for cat in CATEGORIES]

# ============================================
# 시간 생성 (영업시간 반영)
# ============================================

def is_valid_hour(category: str, hour: int) -> bool:
    """해당 카테고리가 영업 중인 시간인지 확인"""
    open_hour, close_hour = MERCHANTS[category]['hours']
    
    if open_hour < close_hour:
        # 일반적인 경우 (10시~21시)
        return open_hour <= hour < close_hour
    else:
        # 자정을 넘기는 경우 (10시~새벽2시)
        return hour >= open_hour or hour < close_hour

def generate_valid_hour(category: str) -> int:
    """영업시간 내의 랜덤 시간 생성"""
    open_hour, close_hour = MERCHANTS[category]['hours']
    
    if open_hour == 0 and close_hour == 24:
        # 24시간 영업
        hour_weights = [
            1, 1, 1, 1, 1, 2,      # 0-5: 새벽
            4, 8, 10, 8,           # 6-9: 오전
            6, 8,                  # 10-11
            15, 12,                # 12-13: 점심 피크
            8, 6, 6, 8,            # 14-17
            12, 15, 12, 10,        # 18-21: 저녁 피크
            6, 3                   # 22-23
        ]
        return random.choices(range(24), weights=hour_weights, k=1)[0]
    
    elif open_hour < close_hour:
        # 일반적인 경우
        valid_hours = list(range(open_hour, close_hour))
    else:
        # 자정을 넘기는 경우
        valid_hours = list(range(open_hour, 24)) + list(range(0, close_hour))
    
    return random.choice(valid_hours)

def get_time_slot(hour: int) -> str:
    if 0 <= hour < 6:
        return 'dawn'
    elif 6 <= hour < 11:
        return 'morning'
    elif 11 <= hour < 14:
        return 'lunch'
    elif 14 <= hour < 18:
        return 'afternoon'
    elif 18 <= hour < 22:
        return 'evening'
    else:
        return 'night'

# ============================================
# 금액 생성 (회식 반영)
# ============================================

def generate_amount(user_id: str, category: str) -> int:
    tier = USER_TIERS[user_id]
    min_amt, max_amt = MERCHANTS[category]['amount_range']
    
    # 등급별 최대 금액 조정
    if tier == 'vip':
        max_amt = min(max_amt * 3, 100000000)  # VIP: 최대 1억
    elif tier == 'premium':
        max_amt = min(int(max_amt * 1.5), 20000000)  # Premium: 최대 2천만
    
    # 카테고리별 금액 분포
    if category == 'restaurant':
        # 회식 반영: 5% 확률로 10만원 이상
        rand = random.random()
        if rand < 0.80:
            amount = random.randint(min_amt, 30000)  # 일반 식사
        elif rand < 0.95:
            amount = random.randint(30000, 80000)   # 외식
        else:
            amount = random.randint(80000, max_amt)  # 회식
    
    elif category in ['luxury', 'electronics', 'travel']:
        # 고가 카테고리: 상위 금액 비중 높음
        rand = random.random()
        if rand < 0.50:
            amount = random.randint(min_amt, min_amt + (max_amt - min_amt) // 3)
        elif rand < 0.80:
            amount = random.randint(min_amt + (max_amt - min_amt) // 3, min_amt + 2 * (max_amt - min_amt) // 3)
        else:
            amount = random.randint(min_amt + 2 * (max_amt - min_amt) // 3, max_amt)
    
    else:
        # 일반 카테고리: 소액 비중 높음
        rand = random.random()
        if rand < 0.70:
            amount = random.randint(min_amt, min_amt + (max_amt - min_amt) // 3)
        elif rand < 0.95:
            amount = random.randint(min_amt + (max_amt - min_amt) // 3, min_amt + 2 * (max_amt - min_amt) // 3)
        else:
            amount = random.randint(min_amt + 2 * (max_amt - min_amt) // 3, max_amt)
    
    # 1000원 단위로 반올림
    if amount >= 10000:
        amount = (amount // 1000) * 1000
    elif amount >= 1000:
        amount = (amount // 100) * 100
    
    return amount

# ============================================
# 이상거래 패턴 (실제 데이터 생성)
# ============================================

class FraudPatternManager:
    """실제 이상거래 패턴을 데이터에 삽입"""
    
    def __init__(self):
        self.velocity_queue = []  # (user_id, remaining_count, base_datetime)
        self.amount_spike_users = set()
    
    def schedule_velocity_fraud(self, user_id: str, base_datetime: datetime):
        """1분 내 5회 결제 패턴 예약"""
        self.velocity_queue.append({
            'user_id': user_id,
            'remaining': 5,
            'base_datetime': base_datetime,
            'category': 'online_shopping'  # 온라인이 연속 결제 가능
        })
    
    def get_velocity_transaction(self) -> dict:
        """예약된 velocity 패턴 트랜잭션 반환"""
        if not self.velocity_queue:
            return None
        
        pattern = self.velocity_queue[0]
        if pattern['remaining'] <= 0:
            self.velocity_queue.pop(0)
            return None
        
        pattern['remaining'] -= 1
        
        # 1분 내 랜덤 시간
        seconds_offset = random.randint(0, 50)
        tx_datetime = pattern['base_datetime'] + timedelta(seconds=seconds_offset)
        
        if pattern['remaining'] == 0:
            self.velocity_queue.pop(0)
        
        return {
            'user_id': pattern['user_id'],
            'datetime': tx_datetime,
            'category': pattern['category'],
            'fraud_type': 'velocity',
            'fraud_reason': '1분 내 5회 이상 결제'
        }
    
    def schedule_amount_spike(self, user_id: str):
        """평소의 10배 이상 금액 패턴 예약"""
        self.amount_spike_users.add(user_id)
    
    def is_amount_spike_user(self, user_id: str) -> bool:
        if user_id in self.amount_spike_users:
            self.amount_spike_users.discard(user_id)
            return True
        return False

fraud_manager = FraudPatternManager()

# ============================================
# 트랜잭션 생성
# ============================================

def generate_transaction(tx_datetime: datetime, force_user: str = None, 
                         force_fraud: dict = None) -> dict:
    """단일 트랜잭션 생성"""
    
    if force_user:
        user_id = force_user
    else:
        # 특정 사용자가 더 자주 결제하도록 가중치 적용
        user_id = random.choices(
            USER_IDS, 
            weights=[3 if USER_TIERS[u] == 'vip' else 2 if USER_TIERS[u] == 'premium' else 1 for u in USER_IDS],
            k=1
        )[0]
    
    if force_fraud:
        category = force_fraud.get('category', random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0])
    else:
        category = random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]
    
    # 영업시간에 맞는 시간 생성
    hour = generate_valid_hour(category)
    tx_datetime = tx_datetime.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
    
    # 금액 생성
    if force_fraud and force_fraud.get('fraud_type') == 'amount_spike':
        # 평소의 10배
        base_amount = generate_amount(user_id, category)
        amount = base_amount * 10
    else:
        amount = generate_amount(user_id, category)
    
    merchant = random.choice(MERCHANTS[category]['names'])
    region = USER_REGIONS[user_id]  # 가맹점 지점명 없으니 사용자 지역 사용
    
    # 이상거래 여부
    is_fraud = force_fraud is not None
    fraud_type = force_fraud.get('fraud_type') if force_fraud else None
    fraud_reason = force_fraud.get('fraud_reason') if force_fraud else None
    
    return {
        'tx_id': str(uuid.uuid4())[:8],
        'user_id': user_id,
        'user_tier': USER_TIERS[user_id],
        'card_number': USER_CARDS[user_id],
        'amount': amount,
        'merchant': merchant,
        'merchant_category': category,
        'region': region,
        'datetime': tx_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        'date': tx_datetime.strftime('%Y-%m-%d'),
        'hour': tx_datetime.hour,
        'day_of_week': tx_datetime.weekday(),
        'day_name': ['월', '화', '수', '목', '금', '토', '일'][tx_datetime.weekday()],
        'is_weekend': tx_datetime.weekday() >= 5,
        'time_slot': get_time_slot(tx_datetime.hour),
        'is_suspected_fraud': is_fraud,
        'fraud_type': fraud_type,
        'fraud_reason': fraud_reason
    }

# ============================================
# CSV 생성
# ============================================

def generate_sample_csv(num_records: int = 1000, output_path: str = 'sample_transactions.csv'):
    base_date = datetime(2026, 2, 5)
    
    transactions = []
    
    # 이상거래 패턴 스케줄 (0.5% = 5건)
    fraud_count = max(int(num_records * 0.005), 3)
    
    # Velocity 패턴 2건 (각 5회 = 10건)
    for i in range(2):
        fraud_user = random.choice(USER_IDS)
        fraud_date = base_date - timedelta(days=random.randint(0, 6))
        fraud_datetime = fraud_date.replace(hour=random.randint(10, 20), minute=random.randint(0, 59))
        fraud_manager.schedule_velocity_fraud(fraud_user, fraud_datetime)
    
    # Amount Spike 패턴 3건
    for i in range(3):
        fraud_manager.schedule_amount_spike(random.choice(USER_IDS))
    
    # 일반 트랜잭션 생성
    for i in range(num_records - 10):  # velocity 10건 제외
        day_offset = random.randint(0, 6)
        tx_date = base_date - timedelta(days=day_offset)
        tx_datetime = tx_date.replace(hour=12)  # 임시, generate_transaction에서 재설정
        
        # Amount Spike 체크
        user_id = random.choices(
            USER_IDS,
            weights=[3 if USER_TIERS[u] == 'vip' else 2 if USER_TIERS[u] == 'premium' else 1 for u in USER_IDS],
            k=1
        )[0]
        
        if fraud_manager.is_amount_spike_user(user_id):
            tx = generate_transaction(tx_datetime, force_user=user_id, force_fraud={
                'fraud_type': 'amount_spike',
                'fraud_reason': '평소의 10배 이상 금액'
            })
        else:
            tx = generate_transaction(tx_datetime)
        
        transactions.append(tx)
    
    # Velocity 패턴 삽입
    while fraud_manager.velocity_queue:
        velocity_info = fraud_manager.get_velocity_transaction()
        if velocity_info:
            tx = generate_transaction(
                velocity_info['datetime'],
                force_user=velocity_info['user_id'],
                force_fraud={
                    'fraud_type': velocity_info['fraud_type'],
                    'fraud_reason': velocity_info['fraud_reason'],
                    'category': velocity_info['category']
                }
            )
            transactions.append(tx)
    
    # 시간순 정렬
    transactions.sort(key=lambda x: x['datetime'])
    
    # CSV 저장
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=transactions[0].keys())
        writer.writeheader()
        writer.writerows(transactions)
    
    print(f"✅ {len(transactions)}건 생성 완료: {output_path}")
    
    # 통계
    print("\n" + "=" * 50)
    print("데이터 통계")
    print("=" * 50)
    
    # 유저별 결제 횟수
    user_counts = defaultdict(int)
    for tx in transactions:
        user_counts[tx['user_id']] += 1
    
    unique_users = len(user_counts)
    avg_tx_per_user = len(transactions) / unique_users
    max_tx_user = max(user_counts.items(), key=lambda x: x[1])
    
    print(f"\n[유저 통계]")
    print(f"  고유 유저 수: {unique_users}명")
    print(f"  인당 평균 결제: {avg_tx_per_user:.1f}건")
    print(f"  최다 결제 유저: {max_tx_user[0]} ({max_tx_user[1]}건)")
    
    # 등급별
    tier_counts = {'normal': 0, 'premium': 0, 'vip': 0}
    tier_amounts = {'normal': 0, 'premium': 0, 'vip': 0}
    for tx in transactions:
        tier = tx['user_tier']
        tier_counts[tier] += 1
        tier_amounts[tier] += tx['amount']
    
    print(f"\n[등급별 통계]")
    for tier in ['normal', 'premium', 'vip']:
        count = tier_counts[tier]
        avg_amt = tier_amounts[tier] / count if count > 0 else 0
        print(f"  {tier:8}: {count:4}건, 평균 {avg_amt:>12,.0f}원")
    
    # 카테고리별
    cat_counts = defaultdict(int)
    cat_amounts = defaultdict(int)
    for tx in transactions:
        cat = tx['merchant_category']
        cat_counts[cat] += 1
        cat_amounts[cat] += tx['amount']
    
    print(f"\n[카테고리 TOP 5]")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1])[:5]:
        avg = cat_amounts[cat] / count
        print(f"  {cat:15}: {count:4}건, 평균 {avg:>10,.0f}원")
    
    # 시간대별
    slot_counts = defaultdict(int)
    for tx in transactions:
        slot_counts[tx['time_slot']] += 1
    
    print(f"\n[시간대별]")
    for slot in ['dawn', 'morning', 'lunch', 'afternoon', 'evening', 'night']:
        count = slot_counts[slot]
        pct = count / len(transactions) * 100
        print(f"  {slot:10}: {count:4}건 ({pct:5.1f}%)")
    
    # 이상거래
    fraud_txs = [tx for tx in transactions if tx['is_suspected_fraud']]
    print(f"\n[이상거래]")
    print(f"  총 {len(fraud_txs)}건 ({len(fraud_txs)/len(transactions)*100:.2f}%)")
    
    fraud_types = defaultdict(int)
    for tx in fraud_txs:
        fraud_types[tx['fraud_type']] += 1
    
    for ftype, count in fraud_types.items():
        print(f"    - {ftype}: {count}건")
    
    # Velocity 패턴 검증
    print(f"\n[Velocity 패턴 검증]")
    velocity_txs = [tx for tx in fraud_txs if tx['fraud_type'] == 'velocity']
    velocity_users = set(tx['user_id'] for tx in velocity_txs)
    for user in velocity_users:
        user_velocity_txs = [tx for tx in velocity_txs if tx['user_id'] == user]
        print(f"  {user}: {len(user_velocity_txs)}건 연속 결제")

if __name__ == "__main__":
    os.makedirs('analysis/data', exist_ok=True)
    generate_sample_csv(10000, 'analysis/data/sample_transactions.csv')
