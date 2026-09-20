from fastapi import APIRouter, Depends, HTTPException

from ..models import LoginRequest, TokenResponse, UserOut
from ..security import authenticate, create_token, current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = authenticate(payload.email, payload.password)
    if not user:
        # Same message for unknown email and wrong password — distinguishing
        # them tells an attacker which accounts exist.
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token, minutes = create_token(user, payload.remember_me)
    return TokenResponse(access_token=token, expires_in_minutes=minutes, user=user)


@router.get("/me", response_model=UserOut)
def me(user: UserOut = Depends(current_user)):
    return user
