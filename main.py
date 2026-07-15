from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Initialize Limiter
limiter = Limiter(key_func=lambda request: request.client.host)

app = FastAPI()

# Register the error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply rate limiting
@app.get("/items")
@limiter.limit("1/minute")
async def get_items(request: Request):
    pass
    # return {"message": "You can access this up to 5 times per minute"}

