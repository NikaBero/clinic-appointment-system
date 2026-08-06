import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
    Enum,
    Text,
    Float,
    Boolean,
)
from sqlalchemy.orm import relationship

from database import Base


class RoleEnum(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.patient)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    doctor_profile = relationship(
        "DoctorProfile", back_populates="user", uselist=False
    )
    appointments_as_patient = relationship(
        "Appointment",
        back_populates="patient",
        foreign_keys="Appointment.patient_id",
    )
    notifications = relationship(
        "Notification", back_populates="user", order_by="Notification.created_at.desc()"
    )
    family_members = relationship(
        "FamilyMember", back_populates="owner", cascade="all, delete-orphan"
    )


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    specialty = Column(String, nullable=False, index=True)
    bio = Column(Text, nullable=True)
    years_experience = Column(Integer, default=0)
    consultation_fee = Column(Float, default=0.0)
    work_start_hour = Column(Integer, default=9)  # 09:00
    work_end_hour = Column(Integer, default=17)  # 17:00
    slot_minutes = Column(Integer, default=30)

    user = relationship("User", back_populates="doctor_profile")
    appointments = relationship("Appointment", back_populates="doctor")
    reviews = relationship("DoctorReview", back_populates="doctor")
    time_off = relationship(
        "DoctorTimeOff", back_populates="doctor", cascade="all, delete-orphan"
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("doctor_profiles.id"))
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    status = Column(
        Enum(AppointmentStatus), default=AppointmentStatus.scheduled
    )
    symptoms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    reminder_sent = Column(Boolean, default=False)
    family_member_id = Column(Integer, ForeignKey("family_members.id"), nullable=True)
    rescheduled_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship(
        "User", back_populates="appointments_as_patient", foreign_keys=[patient_id]
    )
    doctor = relationship("DoctorProfile", back_populates="appointments")
    family_member = relationship("FamilyMember")
    prescription = relationship(
        "Prescription", back_populates="appointment", uselist=False
    )
    review = relationship(
        "DoctorReview", back_populates="appointment", uselist=False
    )


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True)
    diagnosis = Column(String, nullable=True)
    medication = Column(Text, nullable=False)
    dosage = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="prescription")


class DoctorReview(Base):
    __tablename__ = "doctor_reviews"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True)
    doctor_id = Column(Integer, ForeignKey("doctor_profiles.id"), index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="review")
    doctor = relationship("DoctorProfile", back_populates="reviews")
    patient = relationship("User")


class DoctorTimeOff(Base):
    __tablename__ = "doctor_time_off"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctor_profiles.id"), index=True)
    date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    doctor = relationship("DoctorProfile", back_populates="time_off")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class FavoriteDoctor(Base):
    __tablename__ = "favorite_doctors"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    doctor_id = Column(Integer, ForeignKey("doctor_profiles.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    full_name = Column(String, nullable=False)
    relation = Column(String, nullable=True)  # მაგ: შვილი, მშობელი, მეუღლე
    date_of_birth = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="family_members")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    message = Column(Text, nullable=False)
    type = Column(String, default="info")
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")
