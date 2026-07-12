import logging
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from database import get_ch_client, format_result

logger = logging.getLogger("DashboardBackend.Auth")

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    role: str
    username: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, client = Depends(get_ch_client)):
    """
    Authenticate user against PostgreSQL user_register_tb.
    Compares plain-text username and password (matching existing data schema).
    """
    try:
        result = client.query(
            """
            SELECT "user", password, role
            FROM user_register_tb
            WHERE "user" = %(username)s
            LIMIT 1
            """,
            parameters={"username": body.username},
        )
        rows = format_result(result)
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        row = rows[0]
        db_user = row["user"]
        db_password = row["password"]
        db_role = row["role"]
        if db_password != body.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        logger.info(f"User '{db_user}' logged in successfully (role={db_role})")
        return LoginResponse(success=True, role=db_role, username=db_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during login",
        )
