from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domains.users.schemas import NewPassword, UserRead


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: NewPassword

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return " ".join(value.split())


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    user: UserRead


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: NewPassword
