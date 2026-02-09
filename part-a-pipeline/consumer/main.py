import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import time
import json
import asyncio
import asyncpg
import redis.asyncio as aioredis
from config import Config
from metrics import MetricsCollector
from fds_rules import FDSRuleEngine

async def run_consumer(metrics: MetricsCollector):
    print(f"[Consumer] Starting...")
    print(f"[Consumer] Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    print(f"[Consumer] PostgreSQL: {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}")
    print(f"[Consumer] Batch Size: {Config.BATCH_SIZE}")
    sys.stdout.flush()
    
    redis_client = await aioredis.from_url(
        f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}",
        encoding="utf-8",
        decode_responses=True
    )
    print(f"[Consumer] Redis connected")
    
    pool = await asyncpg.create_pool(
        host=Config.POSTGRES_HOST,
        port=Config.POSTGRES_PORT,
        user=Config.POSTGRES_USER,
        password=Config.POSTGRES_PASSWORD,
        database=Config.POSTGRES_DB,
        min_size=10,
        max_size=50
    )
    print(f"[Consumer] PostgreSQL connected")
    sys.stdout.flush()
    
    fds_engine = FDSRuleEngine()
    
    last_metrics_time = time.time()
    batch_size = Config.BATCH_SIZE
    
    try:
        while True:
            pipe = redis_client.pipeline()
            for _ in range(batch_size):
                pipe.rpop("tx_queue")
            results = await pipe.execute()
            
            transactions = [json.loads(r) for r in results if r is not None]
            
            if not transactions:
                await asyncio.sleep(0.1)
                continue
            
            processed_txs = []
            for tx in transactions:
                is_fraud, fraud_rules = fds_engine.check(tx)
                tx['is_fraud'] = is_fraud
                # fraud_rules를 문자열로 변환
                tx['fraud_rules'] = ', '.join(fraud_rules) if fraud_rules else None
                tx['processed_at'] = time.time()
                processed_txs.append(tx)
            
            try:
                async with pool.acquire() as conn:
                    await conn.executemany(f"""
                        INSERT INTO {Config.POSTGRES_SCHEMA}.transactions 
                        (tx_id, card_number, amount, merchant, user_id, user_tier,
                         merchant_category, region, hour, day_of_week, is_weekend,
                         time_slot, is_fraud, fraud_rules, created_at, processed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 
                                to_timestamp($15), to_timestamp($16))
                    """, [
                        (
                            tx['tx_id'],
                            tx['card_number'],
                            tx['amount'],
                            tx['merchant'],
                            tx['user_id'],
                            tx['user_tier'],
                            tx['merchant_category'],
                            tx['region'],
                            tx['hour'],
                            tx['day_of_week'],
                            tx['is_weekend'],
                            tx['time_slot'],
                            tx['is_fraud'],
                            tx['fraud_rules'],
                            tx['created_at'],
                            tx['processed_at']
                        )
                        for tx in processed_txs
                    ])
                
                for tx in processed_txs:
                    e2e_latency = tx['processed_at'] - tx['created_at']
                    metrics.record_success(e2e_latency)
                
            except Exception as e:
                print(f"[Error] DB Insert failed: {e}")
                sys.stdout.flush()
                for _ in processed_txs:
                    metrics.record_error()
            
            if time.time() - last_metrics_time >= Config.METRICS_INTERVAL:
                queue_len = await redis_client.llen("tx_queue")
                fraud_count = sum(1 for tx in processed_txs if tx['is_fraud'])
                metrics.flush(queue_length=queue_len, fraud_count=fraud_count)
                last_metrics_time = time.time()
    
    finally:
        await redis_client.aclose()
        await pool.close()

def main():
    print("=" * 60)
    print("FDS Pipeline Consumer")
    print(f"Batch Size: {Config.BATCH_SIZE}")
    print("=" * 60)
    sys.stdout.flush()
    
    metrics = MetricsCollector(
        output_dir=Config.METRICS_OUTPUT_PATH,
        phase=3,
        role="consumer"
    )
    
    asyncio.run(run_consumer(metrics))

if __name__ == "__main__":
    main()
