import os

class Config:
    # PostgreSQL
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'calme')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'blood_db')
    POSTGRES_SCHEMA = os.getenv('POSTGRES_SCHEMA', 'fds')
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Consumer 설정
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 500))
    
    # Metrics
    METRICS_OUTPUT_PATH = os.getenv('METRICS_OUTPUT_PATH', '/app/metrics')
    METRICS_INTERVAL = int(os.getenv('METRICS_INTERVAL', 10))
    
    @classmethod
    def get_postgres_dsn(cls):
        return f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
