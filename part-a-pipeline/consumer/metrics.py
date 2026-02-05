import time
import csv
import os
import psutil
import numpy as np
from datetime import datetime
from typing import Optional
import redis

class MetricsCollector:
    def __init__(self, output_dir: str, phase: int, role: str = "consumer"):
        self.output_dir = output_dir
        self.phase = phase
        self.role = role
        self.output_path = os.path.join(
            output_dir, 
            f"phase{phase}_{role}_metrics.csv"
        )
        
        self.latencies = []
        self.success_count = 0
        self.error_count = 0
        self.fraud_count = 0
        self.start_time = time.time()
        
        os.makedirs(output_dir, exist_ok=True)
        self._write_header()
    
    def _write_header(self):
        if not os.path.exists(self.output_path):
            with open(self.output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'tps',
                    'success_count',
                    'error_count',
                    'fraud_count',
                    'latency_avg_ms',
                    'latency_p95_ms',
                    'latency_p99_ms',
                    'cpu_percent',
                    'memory_percent',
                    'queue_length'
                ])
    
    def record_success(self, latency: float, is_fraud: bool = False):
        self.latencies.append(latency)
        self.success_count += 1
        if is_fraud:
            self.fraud_count += 1
    
    def record_error(self):
        self.error_count += 1
    
    def flush(self, redis_client: Optional[redis.Redis] = None) -> dict:
        elapsed = time.time() - self.start_time
        total_count = self.success_count + self.error_count
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'tps': round(self.success_count / elapsed, 2) if elapsed > 0 else 0,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'fraud_count': self.fraud_count,
            'latency_avg_ms': round(np.mean(self.latencies) * 1000, 2) if self.latencies else 0,
            'latency_p95_ms': round(np.percentile(self.latencies, 95) * 1000, 2) if len(self.latencies) >= 20 else 0,
            'latency_p99_ms': round(np.percentile(self.latencies, 99) * 1000, 2) if len(self.latencies) >= 100 else 0,
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': round(psutil.virtual_memory().percent, 1),
            'queue_length': redis_client.llen('tx_queue') if redis_client else 0
        }
        
        with open(self.output_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(metrics.values())
        
        print(f"[{metrics['timestamp']}] TPS: {metrics['tps']}, "
              f"Fraud: {metrics['fraud_count']}, "
              f"Latency(avg): {metrics['latency_avg_ms']}ms, "
              f"CPU: {metrics['cpu_percent']}%")
        
        self.latencies = []
        self.success_count = 0
        self.error_count = 0
        self.fraud_count = 0
        self.start_time = time.time()
        
        return metrics
