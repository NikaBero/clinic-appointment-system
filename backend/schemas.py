from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, EmailStr

from models import RoleEnum, AppointmentStatus


# ---------- Auth / Users ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: RoleEnum = RoleEnum.patient
    # Only used when role == doctor
    specialty: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = 0
    consultation_fee: Optional[float] = 0.0


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: RoleEnum
    phone: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum
    full_name: str
    user_id: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordOut(BaseModel):
    message: str
    demo_reset_token: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ---------- Doctors ----------
class DoctorOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    specialty: str
    bio: Optional[str] = None
    years_experience: int
    consultation_fee: float
    work_start_hour: int
    work_end_hour: int
    slot_minutes: int
    is_active: bool = True
    avg_rating: Optional[float] = None
    review_count: int = 0
    is_favorite: bool = False
    next_available: Optional[str] = None

    class Config:
        from_attributes = True


class DoctorScheduleUpdate(BaseModel):
    work_start_hour: Optional[int] = None
    work_end_hour: Optional[int] = None
    slot_minutes: Optional[int] = None


class TimeOffCreate(BaseModel):
    date: date
    reason: Optional[str] = None


class TimeOffOut(BaseModel):
    id: int
    date: date
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class AdminDoctorCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    specialty: str
    bio: Optional[str] = None
    years_experience: Optional[int] = 0
    consultation_fee: Optional[float] = 0.0


class AdminDoctorUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    consultation_fee: Optional[float] = None
    is_active: Optional[bool] = None


# ---------- Appointments ----------
class AppointmentCreate(BaseModel):
    doctor_id: int
    start_time: datetime
    symptoms: Optional[str] = None
    family_member_id: Optional[int] = None


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    symptoms: Optional[str] = None
    notes: Optional[str] = None
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    specialty: Optional[str] = None
    diagnosis: Optional[str] = None
    medication: Optional[str] = None
    dosage: Optional[str] = None
    instructions: Optional[str] = None
    review_rating: Optional[int] = None
    review_comment: Optional[str] = None
    family_member_name: Optional[str] = None
    rescheduled_count: int = 0
    urgency_level: Optional[str] = None
    urgency_advice: Optional[str] = None

    class Config:
        from_attributes = True


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    notes: Optional[str] = None


class AppointmentRescheduleRequest(BaseModel):
    start_time: datetime


# ---------- Favorites ----------
class FavoriteOut(BaseModel):
    doctor_id: int


# ---------- Family members ----------
class FamilyMemberCreate(BaseModel):
    full_name: str
    relation: Optional[str] = None
    date_of_birth: Optional[date] = None


class FamilyMemberOut(BaseModel):
    id: int
    full_name: str
    relation: Optional[str] = None
    date_of_birth: Optional[date] = None

    class Config:
        from_attributes = True


# ---------- Prescriptions ----------
class PrescriptionCreate(BaseModel):
    diagnosis: Optional[str] = None
    medication: str
    dosage: Optional[str] = None
    instructions: Optional[str] = None


class PrescriptionOut(BaseModel):
    id: int
    appointment_id: int
    diagnosis: Optional[str]
    medication: str
    dosage: Optional[str]
    instructions: Optional[str]

    class Config:
        from_attributes = True


# ---------- Reviews ----------
class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    appointment_id: int
    doctor_id: int
    patient_name: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Notifications ----------
class NotificationOut(BaseModel):
    id: int
    message: str
    type: str
    appointment_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- AI recommendation ----------
class SymptomRequest(BaseModel):
    text: str


class RecommendationOut(BaseModel):
    specialty: str
    confidence: float
    reason: str
    matched_keywords: List[str]
    doctors: List[DoctorOut]
    urgency_level: str = "routine"
    urgency_advice: str = ""
    alternative_specialties: List[str] = []


class SymptomOption(BaseModel):
    label: str
    text: str


class HealthTipOut(BaseModel):
    available: bool
    location: Optional[str] = None
    temperature_c: Optional[float] = None
    condition: Optional[str] = None
    uv_index: Optional[float] = None
    tip: Optional[str] = None
    related_specialty: Optional[str] = None
    debug_error: Optional[str] = None


class AirQualityOut(BaseModel):
    available: bool
    location: Optional[str] = None
    us_aqi: Optional[float] = None
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    category: Optional[str] = None
    color: Optional[str] = None
    advice: Optional[str] = None


class HolidayOut(BaseModel):
    date: date
    name: str


# ---------- Analytics ----------
class AnalyticsOut(BaseModel):
    total_users: int
    total_patients: int
    total_doctors: int
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    appointments_per_specialty: dict
    appointments_last_7_days: dict
    review_sentiment: dict = {}
    avg_platform_rating: Optional[float] = None
    total_revenue: float = 0.0
    revenue_last_7_days: dict = {}


class ActivityItem(BaseModel):
    type: str
    message: str
    timestamp: datetime


class TopDoctorOut(BaseModel):
    doctor_id: int
    full_name: str
    specialty: str
    avg_rating: Optional[float] = None
    review_count: int = 0
    appointment_count: int = 0


class UserStatusUpdate(BaseModel):
    is_active: bool
