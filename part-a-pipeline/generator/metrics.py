import time
import csv
import os
import psutil
import numpy as np
from datetime import datetime
from typing import Optional
import redis

class MetricsCollector:
    def __init__(self, output_dir: str, phase: int, role: str = "generator"):
        self.output_dir = output_dir
        self.phase = phase
        self.role = role
        self.output_path = os.path.join(
            output_dir, 
            f"phase{phase}_{role}_metrics.csv"
        )
        
        # 메트릭 버퍼
        self.latencies = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # CSV 헤더 작성
        self._write_header()
    
    def _write_header(self):
        """CSV 파일에 헤더 작성"""
        if not os.path.exists(self.output_path):
            with open(self.output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'tps',
                    'success_count',
                    'error_count',
                    'error_rate',
                    'latency_avg_ms',
                    'latency_p50_ms',
                    'latency_p95_ms',
                    'latency_p99_ms',
                    'cpu_percent',
                    'memory_percent',
                    'queue_length'
                ])
    
    def record_success(self, latency: float):
        """성공한 요청 기록"""
        self.latencies.append(latency)
        self.success_count += 1
    
    def record_error(self):
        """실패한 요청 기록"""
        self.error_count += 1
    
    def flush(self, redis_client: Optional[redis.Redis] = None) -> dict:
        """메트릭을 CSV에 저장하고 버퍼 초기화"""
        elapsed = time.time() - self.start_time
        total_count = self.success_count + self.error_count
        
        # 메트릭 계산
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'tps': round(self.success_count / elapsed, 2) if elapsed > 0 else 0,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'error_rate': round(self.error_count / total_count, 4) if total_count > 0 else 0,
            'latency_avg_ms': round(np.mean(self.latencies) * 1000, 2) if self.latencies else 0,
            'latency_p50_ms': round(np.percentile(self.latencies, 50) * 1000, 2) if self.latencies else 0,
            'latency_p95_ms': round(np.percentile(self.latencies, 95) * 1000, 2) if len(self.latencies) >= 20 else 0,
            'latency_p99_ms': round(np.percentile(self.latencies, 99) * 1000, 2) if len(self.latencies) >= 100 else 0,
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': round(psutil.virtual_memory().percent, 1),
            'queue_length': redis_client.llen('tx_queue') if redis_client else 0
        }
        
        # CSV에 저장
        with open(self.output_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(metrics.values())
        
        # 콘솔 출력
        print(f"[{metrics['timestamp']}] TPS: {metrics['tps']}, "
              f"Latency(avg): {metrics['latency_avg_ms']}ms, "
              f"Errors: {metrics['error_count']}, "
              f"CPU: {metrics['cpu_percent']}%")
        
        # 버퍼 초기화
        self.latencies = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        return metrics
