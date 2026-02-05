import os

class Config:
    # PostgreSQL
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'my-postgres')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'calme')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'blood_db')
    POSTGRES_SCHEMA = os.getenv('POSTGRES_SCHEMA', 'fds')
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'fds-redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Consumer 설정
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 500))
    
    # 메트릭 설정
    METRICS_INTERVAL = int(os.getenv('METRICS_INTERVAL', 10))
    METRICS_OUTPUT_PATH = os.getenv('METRICS_OUTPUT_PATH', '/app/data')
    
    @classmethod
    def get_postgres_dsn(cls):
        return f"host={cls.POSTGRES_HOST} port={cls.POSTGRES_PORT} dbname={cls.POSTGRES_DB} user={cls.POSTGRES_USER} password={cls.POSTGRES_PASSWORD}"
