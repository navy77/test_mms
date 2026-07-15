from slowapi import Limiter
from fastapi import Request

# Initialize Limiter using request.client.host as specified by user
limiter = Limiter(key_func=lambda request: request.client.host)
