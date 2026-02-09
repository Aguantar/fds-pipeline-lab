import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import time
import uuid
import random
import asyncio
import json
import psycopg2
import asyncpg
import redis.asyncio as aioredis
from datetime import datetime
from config import Config
from metrics import MetricsCollector

# ============================================
# 현실적 데이터 생성기 (sample_data_generator 기반)
# ============================================

NUM_USERS = 500
random.seed(None)  # 매번 다른 시드

USER_IDS = [f"user_{i:05d}" for i in range(NUM_USERS)]

USER_CARDS = {
    user_id: f"4532-****-****-{random.randint(1000, 9999)}"
    for user_id in USER_IDS
}

USER_TIERS = {}
for user_id in USER_IDS:
    rand = random.random()
    if rand < 0.02:
        USER_TIERS[user_id] = 'vip'
    elif rand < 0.15:
        USER_TIERS[user_id] = 'premium'
    else:
        USER_TIERS[user_id] = 'normal'

REGIONS = ['서울', '경기', '인천', '부산', '대구', '광주', '대전', '울산', '세종', '제주']
REGION_WEIGHTS = [30, 25, 10, 8, 5, 4, 4, 3, 1, 10]

USER_REGIONS = {
    user_id: random.choices(REGIONS, weights=REGION_WEIGHTS, k=1)[0]
    for user_id in USER_IDS
}

MERCHANTS = {
    'convenience': {
        'names': ['CU', 'GS25', '세븐일레븐', '이마트24', '미니스톱'],
        'amount_range': (1000, 30000),
        'weight': 25,
        'hours': (0, 24)
    },
    'coffee': {
        'names': ['스타벅스', '투썸플레이스', '이디야', '메가커피', '빽다방'],
        'amount_range': (3000, 15000),
        'weight': 20,
        'hours': (7, 22)
    },
    'restaurant': {
        'names': ['맥도날드', '버거킹', '교촌치킨', '피자헛', '본죽', '한신포차', '새마을식당'],
        'amount_range': (5000, 300000),
        'weight': 20,
        'hours': (6, 24)
    },
    'delivery': {
        'names': ['배달의민족', '쿠팡이츠', '요기요'],
        'amount_range': (15000, 100000),
        'weight': 12,
        'hours': (10, 2)
    },
    'online_shopping': {
        'names': ['쿠팡', '네이버쇼핑', 'SSG닷컴', '11번가', '무신사'],
        'amount_range': (10000, 500000),
        'weight': 10,
        'hours': (0, 24)
    },
    'supermarket': {
        'names': ['이마트', '홈플러스', '롯데마트', '코스트코', '트레이더스'],
        'amount_range': (30000, 300000),
        'weight': 5,
        'hours': (10, 22)
    },
    'fashion': {
        'names': ['자라', 'H&M', '유니클로', '나이키', '아디다스'],
        'amount_range': (30000, 500000),
        'weight': 4,
        'hours': (10, 21)
    },
    'electronics': {
        'names': ['삼성스토어', '애플스토어', '하이마트', '롯데하이마트'],
        'amount_range': (50000, 3000000),
        'weight': 2,
        'hours': (10, 21)
    },
    'luxury': {
        'names': ['루이비통', '샤넬', '구찌', '에르메스', '롤렉스'],
        'amount_range': (500000, 50000000),
        'weight': 1,
        'hours': (10, 20)
    },
    'travel': {
        'names': ['대한항공', '아시아나항공', '야놀자', '여기어때', '마이리얼트립'],
        'amount_range': (50000, 5000000),
        'weight': 1,
        'hours': (0, 24)
    }
}

CATEGORIES = list(MERCHANTS.keys())
CATEGORY_WEIGHTS = [MERCHANTS[cat]['weight'] for cat in CATEGORIES]

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

def generate_amount(user_id: str, category: str) -> int:
    tier = USER_TIERS[user_id]
    min_amt, max_amt = MERCHANTS[category]['amount_range']
    
    if tier == 'vip':
        max_amt = min(max_amt * 3, 100000000)
    elif tier == 'premium':
        max_amt = min(int(max_amt * 1.5), 20000000)
    
    if category == 'restaurant':
        rand = random.random()
        if rand < 0.80:
            amount = random.randint(min_amt, 30000)
        elif rand < 0.95:
            amount = random.randint(30000, 80000)
        else:
            amount = random.randint(80000, max_amt)
    elif category in ['luxury', 'electronics', 'travel']:
        rand = random.random()
        if rand < 0.50:
            amount = random.randint(min_amt, min_amt + (max_amt - min_amt) // 3)
        elif rand < 0.80:
            amount = random.randint(min_amt + (max_amt - min_amt) // 3, min_amt + 2 * (max_amt - min_amt) // 3)
        else:
            amount = random.randint(min_amt + 2 * (max_amt - min_amt) // 3, max_amt)
    else:
        rand = random.random()
        if rand < 0.70:
            amount = random.randint(min_amt, min_amt + (max_amt - min_amt) // 3)
        elif rand < 0.95:
            amount = random.randint(min_amt + (max_amt - min_amt) // 3, min_amt + 2 * (max_amt - min_amt) // 3)
        else:
            amount = random.randint(min_amt + 2 * (max_amt - min_amt) // 3, max_amt)
    
    if amount >= 10000:
        amount = (amount // 1000) * 1000
    elif amount >= 1000:
        amount = (amount // 100) * 100
    
    return amount

def generate_transaction() -> dict:
    """현실적인 트랜잭션 생성"""
    user_id = random.choices(
        USER_IDS,
        weights=[3 if USER_TIERS[u] == 'vip' else 2 if USER_TIERS[u] == 'premium' else 1 for u in USER_IDS],
        k=1
    )[0]
    
    category = random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]
    amount = generate_amount(user_id, category)
    merchant = random.choice(MERCHANTS[category]['names'])
    region = USER_REGIONS[user_id]
    
    now = datetime.now()
    
    return {
        'tx_id': str(uuid.uuid4()),
        'user_id': user_id,
        'user_tier': USER_TIERS[user_id],
        'card_number': USER_CARDS[user_id],
        'amount': amount,
        'merchant': merchant,
        'merchant_category': category,
        'region': region,
        'hour': now.hour,
        'day_of_week': now.weekday(),
        'is_weekend': now.weekday() >= 5,
        'time_slot': get_time_slot(now.hour),
        'created_at': time.time()
    }

# ============================================
# Phase 1: 동기 방식 (Baseline)
# ============================================

def insert_sync(tx: dict) -> float:
    start = time.time()
    conn = psycopg2.connect(Config.get_postgres_dsn())
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO {Config.POSTGRES_SCHEMA}.transactions 
        (tx_id, card_number, amount, merchant, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, (tx['tx_id'], tx['card_number'], tx['amount'], tx['merchant']))
    conn.commit()
    cur.close()
    conn.close()
    return time.time() - start

def run_phase1(tps: int, metrics: MetricsCollector):
    print(f"[Phase 1] Starting generator with target TPS: {tps}")
    sys.stdout.flush()
    
    interval = 1.0 / tps
    last_metrics_time = time.time()
    
    while True:
        loop_start = time.time()
        try:
            tx = generate_transaction()
            latency = insert_sync(tx)
            metrics.record_success(latency)
        except Exception as e:
            metrics.record_error()
            print(f"[Error] {e}")
        
        if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
            metrics.flush()
            last_metrics_time = time.time()
        
        elapsed = time.time() - loop_start
        if elapsed < interval:
            time.sleep(interval - elapsed)

# ============================================
# Phase 2: Async + Connection Pool
# ============================================

async def run_phase2(tps: int, metrics: MetricsCollector):
    print(f"[Phase 2] Pool size: 10-50")
    sys.stdout.flush()
    
    pool = await asyncpg.create_pool(
        host=Config.POSTGRES_HOST, port=Config.POSTGRES_PORT,
        user=Config.POSTGRES_USER, password=Config.POSTGRES_PASSWORD,
        database=Config.POSTGRES_DB, min_size=10, max_size=50
    )
    
    interval = 1.0 / tps
    last_metrics_time = time.time()
    
    async def insert_one():
        tx = generate_transaction()
        start = time.time()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {Config.POSTGRES_SCHEMA}.transactions 
                (tx_id, card_number, amount, merchant, created_at)
                VALUES ($1, $2, $3, $4, NOW())
            """, tx['tx_id'], tx['card_number'], tx['amount'], tx['merchant'])
        return time.time() - start
    
    try:
        while True:
            loop_start = time.time()
            try:
                latency = await insert_one()
                metrics.record_success(latency)
            except Exception as e:
                metrics.record_error()
            
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                metrics.flush()
                last_metrics_time = time.time()
            
            elapsed = time.time() - loop_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
    finally:
        await pool.close()

# ============================================
# Phase 2-B: Concurrent Requests
# ============================================

async def run_phase2_concurrent(tps: int, metrics: MetricsCollector):
    print(f"[Phase 2-B] Concurrent batch mode (Pool: 50)")
    sys.stdout.flush()
    
    pool = await asyncpg.create_pool(
        host=Config.POSTGRES_HOST, port=Config.POSTGRES_PORT,
        user=Config.POSTGRES_USER, password=Config.POSTGRES_PASSWORD,
        database=Config.POSTGRES_DB, min_size=10, max_size=50
    )
    
    last_metrics_time = time.time()
    batch_size = min(tps // 10, 50)
    
    async def insert_one():
        tx = generate_transaction()
        start = time.time()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {Config.POSTGRES_SCHEMA}.transactions 
                (tx_id, card_number, amount, merchant, created_at)
                VALUES ($1, $2, $3, $4, NOW())
            """, tx['tx_id'], tx['card_number'], tx['amount'], tx['merchant'])
        return time.time() - start
    
    try:
        while True:
            loop_start = time.time()
            tasks = [insert_one() for _ in range(batch_size)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    metrics.record_error()
                else:
                    metrics.record_success(result)
            
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                metrics.flush()
                last_metrics_time = time.time()
            
            elapsed = time.time() - loop_start
            expected_time = batch_size / tps
            if elapsed < expected_time:
                await asyncio.sleep(expected_time - elapsed)
    finally:
        await pool.close()

# ============================================
# Phase 2-C: Pool 100 + Batch 100
# ============================================

async def run_phase2_optimized(tps: int, metrics: MetricsCollector):
    print(f"[Phase 2-C] Pool(100) + Batch(100) mode")
    sys.stdout.flush()
    
    pool = await asyncpg.create_pool(
        host=Config.POSTGRES_HOST, port=Config.POSTGRES_PORT,
        user=Config.POSTGRES_USER, password=Config.POSTGRES_PASSWORD,
        database=Config.POSTGRES_DB, min_size=20, max_size=100
    )
    
    last_metrics_time = time.time()
    batch_size = 100
    
    async def insert_batch():
        transactions = [generate_transaction() for _ in range(batch_size)]
        start = time.time()
        async with pool.acquire() as conn:
            await conn.executemany(f"""
                INSERT INTO {Config.POSTGRES_SCHEMA}.transactions 
                (tx_id, card_number, amount, merchant, created_at)
                VALUES ($1, $2, $3, $4, NOW())
            """, [(tx['tx_id'], tx['card_number'], tx['amount'], tx['merchant']) for tx in transactions])
        return time.time() - start, batch_size
    
    try:
        while True:
            loop_start = time.time()
            concurrent_batches = max(tps // (batch_size * 10), 1)
            tasks = [insert_batch() for _ in range(concurrent_batches)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    for _ in range(batch_size):
                        metrics.record_error()
                else:
                    latency, count = result
                    for _ in range(count):
                        metrics.record_success(latency / count)
            
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                metrics.flush()
                last_metrics_time = time.time()
            
            total_inserted = concurrent_batches * batch_size
            elapsed = time.time() - loop_start
            expected_time = total_inserted / tps
            if elapsed < expected_time:
                await asyncio.sleep(expected_time - elapsed)
    finally:
        await pool.close()

# ============================================
# Phase 2-D: Pool 200 + Batch 500
# ============================================

async def run_phase2_max(tps: int, metrics: MetricsCollector):
    print(f"[Phase 2-D] Pool(200) + Batch(500) mode")
    sys.stdout.flush()
    
    pool = await asyncpg.create_pool(
        host=Config.POSTGRES_HOST, port=Config.POSTGRES_PORT,
        user=Config.POSTGRES_USER, password=Config.POSTGRES_PASSWORD,
        database=Config.POSTGRES_DB, min_size=50, max_size=200
    )
    
    last_metrics_time = time.time()
    batch_size = 500
    
    async def insert_batch():
        transactions = [generate_transaction() for _ in range(batch_size)]
        start = time.time()
        async with pool.acquire() as conn:
            await conn.executemany(f"""
                INSERT INTO {Config.POSTGRES_SCHEMA}.transactions 
                (tx_id, card_number, amount, merchant, created_at)
                VALUES ($1, $2, $3, $4, NOW())
            """, [(tx['tx_id'], tx['card_number'], tx['amount'], tx['merchant']) for tx in transactions])
        return time.time() - start, batch_size
    
    try:
        while True:
            loop_start = time.time()
            concurrent_batches = max(tps // (batch_size * 5), 1)
            tasks = [insert_batch() for _ in range(concurrent_batches)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    for _ in range(batch_size):
                        metrics.record_error()
                else:
                    latency, count = result
                    for _ in range(count):
                        metrics.record_success(latency / count)
            
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                metrics.flush()
                last_metrics_time = time.time()
            
            total_inserted = concurrent_batches * batch_size
            elapsed = time.time() - loop_start
            expected_time = total_inserted / tps
            if elapsed < expected_time:
                await asyncio.sleep(expected_time - elapsed)
    finally:
        await pool.close()

# ============================================
# Phase 3: Redis Buffer
# ============================================

async def run_phase3(tps: int, metrics: MetricsCollector):
    print(f"[Phase 3] Redis Buffer mode")
    print(f"[Phase 3] Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    sys.stdout.flush()
    
    redis_client = await aioredis.from_url(
        f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}",
        encoding="utf-8",
        decode_responses=True
    )
    
    print(f"[Phase 3] Redis connected")
    sys.stdout.flush()
    
    last_metrics_time = time.time()
    batch_size = 100
    
    async def push_batch():
        transactions = [generate_transaction() for _ in range(batch_size)]
        start = time.time()
        
        pipe = redis_client.pipeline()
        for tx in transactions:
            pipe.lpush("tx_queue", json.dumps(tx))
        await pipe.execute()
        
        return time.time() - start, batch_size
    
    try:
        while True:
            loop_start = time.time()
            
            concurrent_batches = max(tps // (batch_size * 10), 1)
            tasks = [push_batch() for _ in range(concurrent_batches)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    for _ in range(batch_size):
                        metrics.record_error()
                    print(f"[Error] {result}")
                else:
                    latency, count = result
                    for _ in range(count):
                        metrics.record_success(latency / count)
            
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                queue_len = await redis_client.llen("tx_queue")
                metrics.flush(queue_length=queue_len)
                last_metrics_time = time.time()
            
            total_pushed = concurrent_batches * batch_size
            elapsed = time.time() - loop_start
            expected_time = total_pushed / tps
            if elapsed < expected_time:
                await asyncio.sleep(expected_time - elapsed)
    
    finally:
        await redis_client.close()

# ============================================
# Main
# ============================================

def main():
    print("=" * 60)
    print("FDS Pipeline Generator (Realistic Data)")
    print(f"Phase: {Config.PHASE}")
    print(f"Target TPS: {Config.TPS}")
    print(f"Users: {NUM_USERS}, Categories: {len(CATEGORIES)}")
    print("=" * 60)
    sys.stdout.flush()
    
    metrics = MetricsCollector(
        output_dir=Config.METRICS_OUTPUT_PATH,
        phase=Config.PHASE,
        role="generator"
    )
    
    if Config.PHASE == 1:
        run_phase1(Config.TPS, metrics)
    elif Config.PHASE == 2:
        asyncio.run(run_phase2(Config.TPS, metrics))
    elif Config.PHASE == 22:
        asyncio.run(run_phase2_concurrent(Config.TPS, metrics))
    elif Config.PHASE == 23:
        asyncio.run(run_phase2_optimized(Config.TPS, metrics))
    elif Config.PHASE == 24:
        asyncio.run(run_phase2_max(Config.TPS, metrics))
    elif Config.PHASE == 3:
        asyncio.run(run_phase3(Config.TPS, metrics))
    else:
        print(f"[Error] Phase {Config.PHASE} not implemented yet")

if __name__ == "__main__":
    main()
