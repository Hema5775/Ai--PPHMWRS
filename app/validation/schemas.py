from typing import Optional, Literal, Union
from datetime import date as dt_date
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    age: int = Field(..., ge=13, le=120)
    gender: Literal["male", "female", "other"]
    height_cm: float = Field(..., ge=50.0, le=260.0)
    weight_kg: float = Field(..., ge=25.0, le=350.0)
    activity_level: Literal["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"]
    dietary_preference: Literal["balanced", "vegetarian", "vegan", "keto", "mediterranean", "low_carb"]
    health_goal: Literal["weight_loss", "muscle_gain", "maintenance", "stress_reduction", "cardio_endurance", "healthy_sleep"]
    allergies: Optional[str] = Field(default="", max_length=255)
    physical_limitations: Optional[str] = Field(default="none", max_length=255)


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class OnboardingSchema(BaseModel):
    age: int = Field(..., ge=13, le=120)
    gender: Literal["male", "female", "other"]
    height_cm: float = Field(..., ge=50.0, le=260.0)
    weight_kg: float = Field(..., ge=25.0, le=350.0)
    activity_level: Literal["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"]
    dietary_preference: Literal["balanced", "vegetarian", "vegan", "keto", "mediterranean", "low_carb"]
    health_goal: Literal["weight_loss", "muscle_gain", "maintenance", "stress_reduction", "cardio_endurance", "healthy_sleep"]
    allergies: Optional[str] = Field(default="", max_length=255)
    physical_limitations: Optional[str] = Field(default="none", max_length=255)


class ProfileUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=13, le=120)
    gender: Optional[Literal["male", "female", "other"]] = None
    height_cm: Optional[float] = Field(None, ge=50.0, le=260.0)
    weight_kg: Optional[float] = Field(None, ge=25.0, le=350.0)
    activity_level: Optional[Literal["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"]] = None
    dietary_preference: Optional[Literal["balanced", "vegetarian", "vegan", "keto", "mediterranean", "low_carb"]] = None
    health_goal: Optional[Literal["weight_loss", "muscle_gain", "maintenance", "stress_reduction", "cardio_endurance", "healthy_sleep"]] = None
    allergies: Optional[str] = Field(None, max_length=255)
    physical_limitations: Optional[str] = Field(None, max_length=255)
    target_sleep_hours: Optional[float] = Field(None, ge=4.0, le=12.0)
    target_water_liters: Optional[float] = Field(None, ge=1.0, le=8.0)
    target_steps: Optional[int] = Field(None, ge=1000, le=40000)


class DailyActivitySchema(BaseModel):
    date: Optional[dt_date] = None
    steps: int = Field(..., ge=0, le=100000)
    water_liters: float = Field(..., ge=0.0, le=12.0)
    sleep_hours: float = Field(..., ge=0.0, le=24.0)
    sleep_quality: Optional[int] = Field(default=3, ge=1, le=5)
    exercise_minutes: int = Field(..., ge=0, le=720)
    exercise_type: Optional[str] = Field(default="walking", max_length=50)
    calories_burned: Optional[float] = Field(None, ge=0.0, le=10000.0)
    mood: Optional[Literal["great", "good", "neutral", "tired", "stressed"]] = "neutral"
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str):
            from datetime import datetime
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                return dt_date.today()
        return v

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: int) -> int:
        if v > 60000:
            # Extreme value check
            pass
        return v


class TaskCompleteSchema(BaseModel):
    completed: bool
    notes: Optional[str] = Field(None, max_length=255)


class AssistantQuerySchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
