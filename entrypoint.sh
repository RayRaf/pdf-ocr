#!/bin/sh
set -e

# Wait for Redis to be ready
python -c "
import socket, time, sys
host = '${REDIS_HOST:-redis}'
port = int('${REDIS_PORT:-6379}')
for _ in range(30):
    try:
        socket.create_connection((host, port), timeout=2)
        print('Redis is ready')
        sys.exit(0)
    except Exception:
        time.sleep(1)
print('WARNING: Redis may not be ready, continuing anyway')
sys.exit(0)
"

# Apply Django migrations
python manage.py migrate --noinput

# Collect static files (safe to run idempotently)
python manage.py collectstatic --noinput 2>/dev/null || true

# Execute the provided command
exec "$@"
