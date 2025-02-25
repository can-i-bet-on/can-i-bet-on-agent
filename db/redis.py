import os
import redis

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT', '25061'))
REDIS_USERNAME = os.getenv('REDIS_USERNAME')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
REDIS_USE_TLS = os.getenv('REDIS_USE_TLS', 'true').lower() == 'true'

def get_redis_client():
	return redis.Redis(
		host=REDIS_HOST,
		port=REDIS_PORT,
		username=REDIS_USERNAME,
		password=REDIS_PASSWORD,
		ssl=REDIS_USE_TLS,
		ssl_cert_reqs=None,
		decode_responses=True
	)

