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
from faker import Faker
from config import Config
from metrics import MetricsCollector

fake = Faker('ko_KR')

def generate_transaction() -> dict:
    return {
        'tx_id': str(uuid.uuid4()),
        'card_number': fake.credit_card_number(),
        'amount': random.randint(1000, 1000000),
        'merchant': fake.company(),
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
    print(f"[Phase 2] Starting generator with target TPS: {tps}")
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
    """Phase 3: Generator → Redis (LPUSH)"""
    print(f"[Phase 3] Starting generator with target TPS: {tps}")
    print(f"[Phase 3] Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    print(f"[Phase 3] Mode: Redis Buffer (LPUSH)")
    sys.stdout.flush()
    
    # Redis 연결
    redis_client = await aioredis.from_url(
        f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}",
        encoding="utf-8",
        decode_responses=True
    )
    
    print(f"[Phase 3] Redis connected")
    sys.stdout.flush()
    
    last_metrics_time = time.time()
    batch_size = 100  # 한 번에 100건씩 Redis에 푸시
    
    async def push_batch():
        """Batch로 Redis에 푸시"""
        transactions = [generate_transaction() for _ in range(batch_size)]
        start = time.time()
        
        # Pipeline으로 한번에 푸시
        pipe = redis_client.pipeline()
        for tx in transactions:
            pipe.lpush("tx_queue", json.dumps(tx))
        await pipe.execute()
        
        return time.time() - start, batch_size
    
    try:
        while True:
            loop_start = time.time()
            
            # 동시에 여러 배치 푸시
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
            
            # 메트릭 출력 (Queue 길이 포함)
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                queue_len = await redis_client.llen("tx_queue")
                metrics.flush(queue_length=queue_len)
                last_metrics_time = time.time()
            
            # TPS 조절
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
    print("FDS Pipeline Generator")
    print(f"Phase: {Config.PHASE}")
    print(f"Target TPS: {Config.TPS}")
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
