import secrets
from collections import defaultdict
from datetime import datetime, timedelta, date

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func

import models
import schemas
from database import engine, get_db, Base
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from ai_recommend import (
    recommend_specialty,
    build_reason,
    assess_urgency,
    classify_review_sentiment,
    rank_specialties,
    SYMPTOM_CHECKLIST,
)
from health_tips import fetch_health_tip, fetch_air_quality
from holidays import get_holidays, holiday_name
from pdf_gen import generate_prescription_pdf

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Clinic Appointment System API",
    description="საბაკალავრო პრაქტიკული პროექტი — კლინიკის ჩაწერის სისტემა",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def doctor_to_out(doc: models.DoctorProfile, favorite_doctor_ids: set | None = None) -> schemas.DoctorOut:
    ratings = [r.rating for r in doc.reviews]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    return schemas.DoctorOut(
        id=doc.id,
        user_id=doc.user_id,
        full_name=doc.user.full_name,
        specialty=doc.specialty,
        bio=doc.bio,
        years_experience=doc.years_experience,
        consultation_fee=doc.consultation_fee,
        work_start_hour=doc.work_start_hour,
        work_end_hour=doc.work_end_hour,
        slot_minutes=doc.slot_minutes,
        is_active=doc.user.is_active if doc.user else True,
        avg_rating=avg_rating,
        review_count=len(ratings),
        is_favorite=bool(favorite_doctor_ids and doc.id in favorite_doctor_ids),
    )


def appointment_to_out(appt: models.Appointment) -> schemas.AppointmentOut:
    rx = appt.prescription
    review = appt.review
    urgency_level = urgency_advice = None
    if appt.status == models.AppointmentStatus.scheduled and appt.symptoms:
        urgency_level, urgency_advice = assess_urgency(appt.symptoms)
    return schemas.AppointmentOut(
        id=appt.id,
        patient_id=appt.patient_id,
        doctor_id=appt.doctor_id,
        start_time=appt.start_time,
        end_time=appt.end_time,
        status=appt.status,
        symptoms=appt.symptoms,
        notes=appt.notes,
        patient_name=appt.patient.full_name if appt.patient else None,
        doctor_name=appt.doctor.user.full_name if appt.doctor else None,
        specialty=appt.doctor.specialty if appt.doctor else None,
        diagnosis=rx.diagnosis if rx else None,
        medication=rx.medication if rx else None,
        dosage=rx.dosage if rx else None,
        instructions=rx.instructions if rx else None,
        review_rating=review.rating if review else None,
        review_comment=review.comment if review else None,
        family_member_name=appt.family_member.full_name if appt.family_member else None,
        rescheduled_count=appt.rescheduled_count or 0,
        urgency_level=urgency_level,
        urgency_advice=urgency_advice,
    )


def notify(db: Session, user_id: int, message: str, ntype: str = "info", appointment_id=None):
    n = models.Notification(
        user_id=user_id, message=message, type=ntype, appointment_id=appointment_id
    )
    db.add(n)
    db.commit()


def generate_due_reminders(db: Session, user: models.User):
    """
    ვიზიტამდე შეხსენების სიმულაცია: შემოწმდება მომხმარებლის დაგეგმილი ვიზიტები
    და თუ რომელიმე იწყება მომდევნო 24 საათში და შეხსენება ჯერ არ გაგზავნილა,
    გენერირდება in-app შეტყობინება. რეალურ გარემოში აქ SMS/Email API გამოძახება
    ჩაანაცვლებდა notify() ფუნქციას.
    """
    now = datetime.utcnow()
    window_end = now + timedelta(hours=24)
    if user.role == models.RoleEnum.patient:
        due = (
            db.query(models.Appointment)
            .filter(
                models.Appointment.patient_id == user.id,
                models.Appointment.status == models.AppointmentStatus.scheduled,
                models.Appointment.reminder_sent == False,  # noqa: E712
                models.Appointment.start_time >= now,
                models.Appointment.start_time <= window_end,
            )
            .all()
        )
        for appt in due:
            notify(
                db,
                user.id,
                f"შეხსენება: ვიზიტი ექიმთან {appt.doctor.user.full_name} "
                f"დაგეგმილია {appt.start_time.strftime('%d.%m.%Y %H:%M')}-ზე.",
                "reminder",
                appt.id,
            )
            appt.reminder_sent = True
        if due:
            db.commit()


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.post("/auth/register", response_model=schemas.Token, tags=["Auth"])
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="ეს ელ-ფოსტა უკვე რეგისტრირებულია")

    if payload.phone:
        existing_phone = db.query(models.User).filter(
            models.User.phone == payload.phone
        ).first()
        if existing_phone:
            raise HTTPException(
                status_code=400, detail="ეს ტელეფონის ნომერი უკვე რეგისტრირებულია"
            )

    user = models.User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if payload.role == models.RoleEnum.doctor:
        profile = models.DoctorProfile(
            user_id=user.id,
            specialty=payload.specialty or "ოჯახის ექიმი",
            bio=payload.bio,
            years_experience=payload.years_experience or 0,
            consultation_fee=payload.consultation_fee or 0.0,
        )
        db.add(profile)
        db.commit()

    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token, role=user.role, full_name=user.full_name, user_id=user.id
    )


@app.post("/auth/login", response_model=schemas.Token, tags=["Auth"])
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="არასწორი ელ-ფოსტა ან პაროლი")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="ეს ანგარიში დეაქტივირებულია")
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token, role=user.role, full_name=user.full_name, user_id=user.id
    )


@app.get("/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/auth/forgot-password", response_model=schemas.ForgotPasswordOut, tags=["Auth"])
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    პაროლის აღდგენის მოთხოვნა — სიმულირებული რეჟიმი.

    რეალურ სისტემაში აქ გენერირებული ტოკენი გაეგზავნებოდა მომხმარებელს
    ელ-ფოსტით (SMTP სერვისის საშუალებით — SendGrid, Gmail SMTP და ა.შ.),
    ამ აკადემიური დემო-პროექტისთვის კი ტოკენი პირდაპირ ბრუნდება პასუხში,
    რომ ფუნქციონალის სრული ციკლი (მოთხოვნა → აღდგენა) ტესტირებადი იყოს
    რეალური საფოსტო ინფრასტრუქტურის გარეშე. იგივე შეტყობინება ბრუნდება
    მიუხედავად იმისა, დარეგისტრირებულია თუ არა ეს ელ-ფოსტა — რომ არ
    გავამხილოთ რომელი ანგარიშები არსებობს სისტემაში.
    """
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    generic_message = (
        "თუ ეს ელ-ფოსტა რეგისტრირებულია სისტემაში, აღდგენის ბმული გამოგზავნილია "
        "(დემო რეჟიმში — იხილეთ ქვემოთ)."
    )
    if not user:
        return schemas.ForgotPasswordOut(message=generic_message, demo_reset_token=None)

    token = secrets.token_urlsafe(24)
    reset = models.PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(reset)
    db.commit()
    return schemas.ForgotPasswordOut(message=generic_message, demo_reset_token=token)


@app.post("/auth/reset-password", tags=["Auth"])
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == payload.token
    ).first()
    if (
        not reset
        or reset.used
        or reset.expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="ბმულის ვადა ამოიწურა ან არასწორია — მოითხოვეთ ახალი")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="პაროლი უნდა შეიცავდეს მინიმუმ 6 სიმბოლოს")

    reset.user.hashed_password = get_password_hash(payload.new_password)
    reset.used = True
    db.commit()
    return {"ok": True}


@app.put("/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def update_profile(
    payload: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.full_name:
        current_user.full_name = payload.full_name
    if payload.phone is not None and payload.phone != current_user.phone:
        if payload.phone:
            existing_phone = db.query(models.User).filter(
                models.User.phone == payload.phone,
                models.User.id != current_user.id,
            ).first()
            if existing_phone:
                raise HTTPException(
                    status_code=400, detail="ეს ტელეფონის ნომერი უკვე გამოყენებულია"
                )
        current_user.phone = payload.phone
    if payload.new_password:
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(status_code=400, detail="მიმდინარე პაროლი არასწორია")
        current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user


# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------
@app.get("/doctors", response_model=list[schemas.DoctorOut], tags=["Doctors"])
def list_doctors(
    specialty: str | None = None,
    name: str | None = None,
    min_fee: float | None = None,
    max_fee: float | None = None,
    min_experience: int | None = None,
    include_inactive: bool = False,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    query = db.query(models.DoctorProfile).join(models.User)
    if specialty:
        query = query.filter(models.DoctorProfile.specialty == specialty)
    if name:
        query = query.filter(models.User.full_name.ilike(f"%{name}%"))
    if min_fee is not None:
        query = query.filter(models.DoctorProfile.consultation_fee >= min_fee)
    if max_fee is not None:
        query = query.filter(models.DoctorProfile.consultation_fee <= max_fee)
    if min_experience is not None:
        query = query.filter(models.DoctorProfile.years_experience >= min_experience)
    if not include_inactive:
        query = query.filter(models.User.is_active == True)  # noqa: E712

    favorite_ids = set()
    if current_user:
        favorite_ids = {
            f.doctor_id for f in db.query(models.FavoriteDoctor).filter(
                models.FavoriteDoctor.patient_id == current_user.id
            ).all()
        }
    if favorites_only:
        if not favorite_ids:
            return []
        query = query.filter(models.DoctorProfile.id.in_(favorite_ids))

    return [doctor_to_out(d, favorite_ids) for d in query.all()]


@app.get("/doctors/{doctor_id}/reviews", response_model=list[schemas.ReviewOut], tags=["Doctors"])
def list_doctor_reviews(doctor_id: int, db: Session = Depends(get_db)):
    reviews = (
        db.query(models.DoctorReview)
        .filter(models.DoctorReview.doctor_id == doctor_id)
        .order_by(models.DoctorReview.created_at.desc())
        .all()
    )
    return [
        schemas.ReviewOut(
            id=r.id,
            appointment_id=r.appointment_id,
            doctor_id=r.doctor_id,
            patient_name=r.patient.full_name if r.patient else None,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in reviews
    ]


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------
@app.get("/favorites/me", response_model=list[schemas.FavoriteOut], tags=["Favorites"])
def my_favorites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    rows = db.query(models.FavoriteDoctor).filter(
        models.FavoriteDoctor.patient_id == current_user.id
    ).all()
    return [schemas.FavoriteOut(doctor_id=r.doctor_id) for r in rows]


@app.post("/favorites/{doctor_id}", tags=["Favorites"])
def add_favorite(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    doctor = db.query(models.DoctorProfile).filter(models.DoctorProfile.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="ექიმი ვერ მოიძებნა")
    existing = db.query(models.FavoriteDoctor).filter(
        models.FavoriteDoctor.patient_id == current_user.id,
        models.FavoriteDoctor.doctor_id == doctor_id,
    ).first()
    if not existing:
        db.add(models.FavoriteDoctor(patient_id=current_user.id, doctor_id=doctor_id))
        db.commit()
    return {"ok": True}


@app.delete("/favorites/{doctor_id}", tags=["Favorites"])
def remove_favorite(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    db.query(models.FavoriteDoctor).filter(
        models.FavoriteDoctor.patient_id == current_user.id,
        models.FavoriteDoctor.doctor_id == doctor_id,
    ).delete()
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Family members
# ---------------------------------------------------------------------------
@app.get("/family-members", response_model=list[schemas.FamilyMemberOut], tags=["Family"])
def list_family_members(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    return db.query(models.FamilyMember).filter(
        models.FamilyMember.owner_id == current_user.id
    ).order_by(models.FamilyMember.full_name).all()


@app.post("/family-members", response_model=schemas.FamilyMemberOut, tags=["Family"])
def add_family_member(
    payload: schemas.FamilyMemberCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    member = models.FamilyMember(
        owner_id=current_user.id,
        full_name=payload.full_name,
        relation=payload.relation,
        date_of_birth=payload.date_of_birth,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@app.delete("/family-members/{member_id}", tags=["Family"])
def delete_family_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    member = db.query(models.FamilyMember).filter(
        models.FamilyMember.id == member_id,
        models.FamilyMember.owner_id == current_user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="ჩანაწერი ვერ მოიძებნა")
    db.delete(member)
    db.commit()
    return {"ok": True}


@app.get("/doctors/specialties", tags=["Doctors"])
def list_specialties(db: Session = Depends(get_db)):
    rows = db.query(models.DoctorProfile.specialty).distinct().all()
    return sorted({r[0] for r in rows})


@app.get("/doctors/{doctor_id}/availability", tags=["Doctors"])
def doctor_availability(
    doctor_id: int, day: str, db: Session = Depends(get_db)
):
    """
    აბრუნებს თავისუფალ სლოტებს კონკრეტული ექიმისთვის მითითებულ დღეს.
    day ფორმატი: YYYY-MM-DD
    """
    doctor = db.query(models.DoctorProfile).filter(
        models.DoctorProfile.id == doctor_id
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="ექიმი ვერ მოიძებნა")

    try:
        target_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="თარიღის ფორმატი უნდა იყოს YYYY-MM-DD")

    day_off = (
        db.query(models.DoctorTimeOff)
        .filter(
            models.DoctorTimeOff.doctor_id == doctor_id,
            models.DoctorTimeOff.date == target_day,
        )
        .first()
    )
    if day_off:
        return {"doctor_id": doctor_id, "day": day, "available_slots": [], "day_off": True}

    holiday = holiday_name(target_day)
    if holiday:
        return {
            "doctor_id": doctor_id, "day": day, "available_slots": [],
            "day_off": True, "holiday_name": holiday,
        }

    slot_delta = timedelta(minutes=doctor.slot_minutes)
    day_start = datetime.combine(target_day, datetime.min.time()) + timedelta(
        hours=doctor.work_start_hour
    )
    day_end = datetime.combine(target_day, datetime.min.time()) + timedelta(
        hours=doctor.work_end_hour
    )

    existing = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.status != models.AppointmentStatus.cancelled,
            models.Appointment.start_time >= day_start,
            models.Appointment.start_time < day_end,
        )
        .all()
    )
    taken = {a.start_time for a in existing}

    slots = []
    cursor = day_start
    now = datetime.utcnow()
    while cursor + slot_delta <= day_end:
        if cursor not in taken and cursor > now:
            slots.append(cursor.strftime("%Y-%m-%dT%H:%M"))
        cursor += slot_delta

    return {"doctor_id": doctor_id, "day": day, "available_slots": slots, "day_off": False}


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------
@app.post(
    "/appointments",
    response_model=schemas.AppointmentOut,
    tags=["Appointments"],
)
def create_appointment(
    payload: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient", "admin")),
):
    doctor = db.query(models.DoctorProfile).filter(
        models.DoctorProfile.id == payload.doctor_id
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="ექიმი ვერ მოიძებნა")

    end_time = payload.start_time + timedelta(minutes=doctor.slot_minutes)

    day_off = (
        db.query(models.DoctorTimeOff)
        .filter(
            models.DoctorTimeOff.doctor_id == payload.doctor_id,
            models.DoctorTimeOff.date == payload.start_time.date(),
        )
        .first()
    )
    if day_off:
        raise HTTPException(
            status_code=409, detail="ექიმი ამ დღეს არ იღებს პაციენტებს (შვებულება/დასვენება)"
        )

    holiday = holiday_name(payload.start_time.date())
    if holiday:
        raise HTTPException(
            status_code=409,
            detail=f"{payload.start_time.date().isoformat()} უქმე დღეა ({holiday}) — ჯავშნის გაკეთება ამ დღეს შეუძლებელია",
        )

    # კონფლიქტის შემოწმება — არსებობს თუ არა უკვე ჯავშანი ამ დროისთვის
    conflict = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.doctor_id == payload.doctor_id,
            models.Appointment.status != models.AppointmentStatus.cancelled,
            models.Appointment.start_time == payload.start_time,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=409,
            detail="სამწუხაროდ, ეს დროის სლოტი უკვე დაკავებულია — გთხოვთ აირჩიოთ სხვა დრო",
        )

    family_member = None
    if payload.family_member_id:
        family_member = db.query(models.FamilyMember).filter(
            models.FamilyMember.id == payload.family_member_id,
            models.FamilyMember.owner_id == current_user.id,
        ).first()
        if not family_member:
            raise HTTPException(status_code=404, detail="ოჯახის წევრი ვერ მოიძებნა")

    appt = models.Appointment(
        patient_id=current_user.id,
        doctor_id=payload.doctor_id,
        start_time=payload.start_time,
        end_time=end_time,
        symptoms=payload.symptoms,
        status=models.AppointmentStatus.scheduled,
        family_member_id=payload.family_member_id,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    when = appt.start_time.strftime("%d.%m.%Y %H:%M")
    for_whom = f" ({family_member.full_name}-სთვის)" if family_member else ""
    notify(
        db, current_user.id,
        f"თქვენი ჯავშანი ექიმთან {doctor.user.full_name} დადასტურებულია{for_whom} — {when}.",
        "appointment_confirmed", appt.id,
    )
    notify(
        db, doctor.user_id,
        f"ახალი ჯავშანი პაციენტისგან {current_user.full_name} — {when}.",
        "appointment_confirmed", appt.id,
    )
    return appointment_to_out(appt)


@app.put(
    "/appointments/{appointment_id}/reschedule",
    response_model=schemas.AppointmentOut,
    tags=["Appointments"],
)
def reschedule_appointment(
    appointment_id: int,
    payload: schemas.AppointmentRescheduleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="ჯავშანი ვერ მოიძებნა")

    is_owner_patient = appt.patient_id == current_user.id
    is_owner_doctor = (
        current_user.doctor_profile and appt.doctor_id == current_user.doctor_profile.id
    )
    is_admin = current_user.role == models.RoleEnum.admin
    if not (is_owner_patient or is_owner_doctor or is_admin):
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    if appt.status != models.AppointmentStatus.scheduled:
        raise HTTPException(
            status_code=400, detail="მხოლოდ დაგეგმილი ჯავშნის გადატანაა შესაძლებელი"
        )

    doctor = appt.doctor
    new_start = payload.start_time
    new_end = new_start + timedelta(minutes=doctor.slot_minutes)

    day_off = db.query(models.DoctorTimeOff).filter(
        models.DoctorTimeOff.doctor_id == doctor.id,
        models.DoctorTimeOff.date == new_start.date(),
    ).first()
    if day_off:
        raise HTTPException(status_code=409, detail="ექიმი ამ დღეს არ იღებს პაციენტებს")

    if holiday_name(new_start.date()):
        raise HTTPException(status_code=409, detail="ეს დღე უქმეა — ჯავშნის გადატანა შეუძლებელია")

    conflict = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor.id,
        models.Appointment.id != appt.id,
        models.Appointment.status != models.AppointmentStatus.cancelled,
        models.Appointment.start_time == new_start,
    ).first()
    if conflict:
        raise HTTPException(status_code=409, detail="ეს დროის სლოტი უკვე დაკავებულია")

    old_when = appt.start_time.strftime("%d.%m.%Y %H:%M")
    new_when = new_start.strftime("%d.%m.%Y %H:%M")
    appt.start_time = new_start
    appt.end_time = new_end
    appt.reminder_sent = False
    appt.rescheduled_count = (appt.rescheduled_count or 0) + 1
    db.commit()
    db.refresh(appt)

    if is_owner_patient:
        notify(
            db, doctor.user_id,
            f"პაციენტმა {appt.patient.full_name} გადაიტანა ჯავშანი {old_when}-დან {new_when}-ზე.",
            "appointment_confirmed", appt.id,
        )
    else:
        notify(
            db, appt.patient_id,
            f"ექიმმა {doctor.user.full_name} გადაგიტანათ ჯავშანი {old_when}-დან {new_when}-ზე.",
            "appointment_confirmed", appt.id,
        )
    return appointment_to_out(appt)


@app.get(
    "/appointments/me",
    response_model=list[schemas.AppointmentOut],
    tags=["Appointments"],
)
def my_appointments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role == models.RoleEnum.doctor:
        appts = (
            db.query(models.Appointment)
            .filter(models.Appointment.doctor_id == current_user.doctor_profile.id)
            .order_by(models.Appointment.start_time.desc())
            .all()
        )
    elif current_user.role == models.RoleEnum.admin:
        appts = db.query(models.Appointment).order_by(
            models.Appointment.start_time.desc()
        ).all()
    else:
        appts = (
            db.query(models.Appointment)
            .filter(models.Appointment.patient_id == current_user.id)
            .order_by(models.Appointment.start_time.desc())
            .all()
        )
    return [appointment_to_out(a) for a in appts]


@app.put(
    "/appointments/{appointment_id}/status",
    response_model=schemas.AppointmentOut,
    tags=["Appointments"],
)
def update_appointment_status(
    appointment_id: int,
    payload: schemas.AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="ჯავშანი ვერ მოიძებნა")

    is_owner_doctor = (
        current_user.role == models.RoleEnum.doctor
        and current_user.doctor_profile
        and appt.doctor_id == current_user.doctor_profile.id
    )
    is_owner_patient = (
        current_user.role == models.RoleEnum.patient
        and appt.patient_id == current_user.id
    )
    is_admin = current_user.role == models.RoleEnum.admin

    if not (is_owner_doctor or is_owner_patient or is_admin):
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    # პაციენტს მხოლოდ გაუქმების უფლება აქვს
    if is_owner_patient and payload.status != models.AppointmentStatus.cancelled:
        raise HTTPException(
            status_code=403, detail="პაციენტს მხოლოდ ჯავშნის გაუქმება შეუძლია"
        )

    appt.status = payload.status
    if payload.notes is not None:
        appt.notes = payload.notes
    db.commit()
    db.refresh(appt)

    if payload.status == models.AppointmentStatus.cancelled:
        when = appt.start_time.strftime("%d.%m.%Y %H:%M")
        if is_owner_patient:
            notify(
                db, appt.doctor.user_id,
                f"პაციენტმა {appt.patient.full_name} გააუქმა ჯავშანი — {when}.",
                "appointment_cancelled", appt.id,
            )
        else:
            notify(
                db, appt.patient_id,
                f"თქვენი ჯავშანი ექიმთან {appt.doctor.user.full_name} გაუქმდა — {when}.",
                "appointment_cancelled", appt.id,
            )
    return appointment_to_out(appt)


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@app.post(
    "/appointments/{appointment_id}/review",
    response_model=schemas.ReviewOut,
    tags=["Reviews"],
)
def create_review(
    appointment_id: int,
    payload: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("patient")),
):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="ჯავშანი ვერ მოიძებნა")
    if appt.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")
    if appt.status != models.AppointmentStatus.completed:
        raise HTTPException(
            status_code=400, detail="შეფასების დატოვება შესაძლებელია მხოლოდ დასრულებული ვიზიტისთვის"
        )
    if appt.review:
        raise HTTPException(status_code=400, detail="ამ ვიზიტისთვის შეფასება უკვე დატოვებულია")
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="შეფასება უნდა იყოს 1-დან 5-მდე")

    review = models.DoctorReview(
        appointment_id=appointment_id,
        doctor_id=appt.doctor_id,
        patient_id=current_user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    notify(
        db, appt.doctor.user_id,
        f"პაციენტმა {current_user.full_name} დაგიტოვათ შეფასება: {payload.rating}/5.",
        "review_added", appt.id,
    )
    return schemas.ReviewOut(
        id=review.id,
        appointment_id=review.appointment_id,
        doctor_id=review.doctor_id,
        patient_name=current_user.full_name,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


# ---------------------------------------------------------------------------
# Doctor schedule & time off
# ---------------------------------------------------------------------------
@app.get("/doctor/me", response_model=schemas.DoctorOut, tags=["Doctor"])
def my_doctor_profile(
    current_user: models.User = Depends(require_role("doctor")),
):
    return doctor_to_out(current_user.doctor_profile)


@app.put("/doctor/schedule", response_model=schemas.DoctorOut, tags=["Doctor"])
def update_schedule(
    payload: schemas.DoctorScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("doctor")),
):
    profile = current_user.doctor_profile
    if payload.work_start_hour is not None:
        profile.work_start_hour = payload.work_start_hour
    if payload.work_end_hour is not None:
        profile.work_end_hour = payload.work_end_hour
    if payload.slot_minutes is not None:
        profile.slot_minutes = payload.slot_minutes
    if profile.work_start_hour >= profile.work_end_hour:
        raise HTTPException(
            status_code=400, detail="დაწყების საათი უნდა იყოს დასრულების საათზე ადრე"
        )
    db.commit()
    db.refresh(profile)
    return doctor_to_out(profile)


@app.get("/doctor/timeoff", response_model=list[schemas.TimeOffOut], tags=["Doctor"])
def list_time_off(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("doctor")),
):
    return (
        db.query(models.DoctorTimeOff)
        .filter(models.DoctorTimeOff.doctor_id == current_user.doctor_profile.id)
        .order_by(models.DoctorTimeOff.date)
        .all()
    )


@app.post("/doctor/timeoff", response_model=schemas.TimeOffOut, tags=["Doctor"])
def add_time_off(
    payload: schemas.TimeOffCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("doctor")),
):
    existing = (
        db.query(models.DoctorTimeOff)
        .filter(
            models.DoctorTimeOff.doctor_id == current_user.doctor_profile.id,
            models.DoctorTimeOff.date == payload.date,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="ეს თარიღი უკვე მონიშნულია დასვენების დღედ")
    time_off = models.DoctorTimeOff(
        doctor_id=current_user.doctor_profile.id,
        date=payload.date,
        reason=payload.reason,
    )
    db.add(time_off)
    db.commit()
    db.refresh(time_off)
    return time_off


@app.delete("/doctor/timeoff/{time_off_id}", tags=["Doctor"])
def delete_time_off(
    time_off_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("doctor")),
):
    time_off = db.query(models.DoctorTimeOff).filter(
        models.DoctorTimeOff.id == time_off_id,
        models.DoctorTimeOff.doctor_id == current_user.doctor_profile.id,
    ).first()
    if not time_off:
        raise HTTPException(status_code=404, detail="ჩანაწერი ვერ მოიძებნა")
    db.delete(time_off)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@app.get("/notifications/me", response_model=list[schemas.NotificationOut], tags=["Notifications"])
def my_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    generate_due_reminders(db, current_user)
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .limit(50)
        .all()
    )


@app.put("/notifications/{notification_id}/read", tags=["Notifications"])
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    n = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="შეტყობინება ვერ მოიძებნა")
    n.is_read = True
    db.commit()
    return {"ok": True}


@app.put("/notifications/read-all", tags=["Notifications"])
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,  # noqa: E712
    ).update({models.Notification.is_read: True})
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------
@app.post(
    "/appointments/{appointment_id}/prescription",
    response_model=schemas.PrescriptionOut,
    tags=["Prescriptions"],
)
def create_prescription(
    appointment_id: int,
    payload: schemas.PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("doctor", "admin")),
):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="ჯავშანი ვერ მოიძებნა")

    if (
        current_user.role == models.RoleEnum.doctor
        and appt.doctor_id != current_user.doctor_profile.id
    ):
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    existing = db.query(models.Prescription).filter(
        models.Prescription.appointment_id == appointment_id
    ).first()
    if existing:
        existing.diagnosis = payload.diagnosis
        existing.medication = payload.medication
        existing.dosage = payload.dosage
        existing.instructions = payload.instructions
        db.commit()
        db.refresh(existing)
        return existing

    prescription = models.Prescription(
        appointment_id=appointment_id,
        diagnosis=payload.diagnosis,
        medication=payload.medication,
        dosage=payload.dosage,
        instructions=payload.instructions,
    )
    db.add(prescription)
    appt.status = models.AppointmentStatus.completed
    db.commit()
    db.refresh(prescription)

    notify(
        db, appt.patient_id,
        f"ვიზიტი ექიმთან {appt.doctor.user.full_name} დასრულდა და დაემატა რეცეპტი. "
        f"შეგიძლიათ დატოვოთ შეფასება.",
        "prescription_added", appt.id,
    )
    return prescription


@app.get("/appointments/{appointment_id}/prescription/pdf", tags=["Prescriptions"])
def download_prescription_pdf(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()
    if not appt or not appt.prescription:
        raise HTTPException(status_code=404, detail="რეცეპტი ვერ მოიძებნა")

    is_owner_patient = appt.patient_id == current_user.id
    is_owner_doctor = (
        current_user.doctor_profile and appt.doctor_id == current_user.doctor_profile.id
    )
    is_admin = current_user.role == models.RoleEnum.admin
    if not (is_owner_patient or is_owner_doctor or is_admin):
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    pdf_bytes = generate_prescription_pdf(
        patient_name=appt.patient.full_name,
        doctor_name=appt.doctor.user.full_name,
        specialty=appt.doctor.specialty,
        appointment_date=appt.start_time,
        diagnosis=appt.prescription.diagnosis or "",
        medication=appt.prescription.medication,
        dosage=appt.prescription.dosage or "",
        instructions=appt.prescription.instructions or "",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=prescription_{appointment_id}.pdf"
        },
    )


# ---------------------------------------------------------------------------
# AI recommendation
# ---------------------------------------------------------------------------
@app.post(
    "/ai/recommend", response_model=schemas.RecommendationOut, tags=["AI"]
)
def ai_recommend(payload: schemas.SymptomRequest, db: Session = Depends(get_db)):
    specialty, confidence, matched = recommend_specialty(payload.text)
    reason = build_reason(specialty, matched)
    urgency_level, urgency_advice = assess_urgency(payload.text)
    doctors = (
        db.query(models.DoctorProfile)
        .join(models.User)
        .filter(
            models.DoctorProfile.specialty == specialty,
            models.User.is_active == True,  # noqa: E712
        )
        .all()
    )
    doctors_out = [doctor_to_out(d) for d in doctors]
    # ჭკვიანი დალაგება: რეიტინგი + გამოცდილება მაღალ ადგილას, ფასი კი
    # ოდნავ ამცირებს ქულას — ასე პაციენტს ვთავაზობთ საუკეთესო თანაფარდობას
    # ხარისხსა და ღირებულებას შორის ("საუკეთესო არჩევანი" ბეიჯი frontend-ზე).
    def match_score(d: schemas.DoctorOut) -> float:
        rating_score = (d.avg_rating or 3.5) * 2
        experience_score = min(d.years_experience, 20) * 0.15
        price_penalty = min(d.consultation_fee, 200) * 0.01
        return rating_score + experience_score - price_penalty

    doctors_out.sort(key=match_score, reverse=True)

    ranked = rank_specialties(payload.text, limit=3)
    alternatives = [s for s, _ in ranked if s != specialty][:2]

    return schemas.RecommendationOut(
        specialty=specialty,
        confidence=confidence,
        reason=reason,
        matched_keywords=matched,
        doctors=doctors_out,
        urgency_level=urgency_level,
        urgency_advice=urgency_advice,
        alternative_specialties=alternatives,
    )


@app.get("/ai/symptoms", response_model=list[schemas.SymptomOption], tags=["AI"])
def ai_symptom_checklist():
    return SYMPTOM_CHECKLIST


@app.get("/health-tip", response_model=schemas.HealthTipOut, tags=["AI"])
def health_tip():
    """
    გარე საჯარო ამინდის API-დან (Open-Meteo) რეალურ დროში მიღებული
    მონაცემების საფუძველზე გენერირებული ჯანმრთელობის რჩევა დღისთვის.
    """
    return fetch_health_tip()


@app.get("/air-quality", response_model=schemas.AirQualityOut, tags=["AI"])
def air_quality():
    """
    საზოგადოებრივი ჯანმრთელობის საჯარო მონაცემი — თბილისის ჰაერის
    ხარისხის ინდექსი (Open-Meteo Air Quality API).
    """
    return fetch_air_quality()


@app.get("/holidays", response_model=list[schemas.HolidayOut], tags=["System"])
def list_holidays(year: int | None = None):
    year = year or datetime.utcnow().year
    holidays = get_holidays(year)
    return [
        schemas.HolidayOut(date=d, name=name)
        for d, name in sorted(holidays.items())
    ]


# ---------------------------------------------------------------------------
# Admin analytics
# ---------------------------------------------------------------------------
@app.get(
    "/admin/analytics", response_model=schemas.AnalyticsOut, tags=["Admin"]
)
def analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    total_users = db.query(models.User).count()
    total_patients = db.query(models.User).filter(
        models.User.role == models.RoleEnum.patient
    ).count()
    total_doctors = db.query(models.User).filter(
        models.User.role == models.RoleEnum.doctor
    ).count()
    total_appointments = db.query(models.Appointment).count()
    completed = db.query(models.Appointment).filter(
        models.Appointment.status == models.AppointmentStatus.completed
    ).count()
    cancelled = db.query(models.Appointment).filter(
        models.Appointment.status == models.AppointmentStatus.cancelled
    ).count()

    per_specialty = defaultdict(int)
    rows = (
        db.query(models.DoctorProfile.specialty, func.count(models.Appointment.id))
        .join(models.Appointment, models.Appointment.doctor_id == models.DoctorProfile.id)
        .group_by(models.DoctorProfile.specialty)
        .all()
    )
    for specialty, count in rows:
        per_specialty[specialty] = count

    last_7_days = defaultdict(int)
    today = date.today()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = (
            db.query(models.Appointment)
            .filter(func.date(models.Appointment.start_time) == day.isoformat())
            .count()
        )
        last_7_days[day.isoformat()] = count

    all_reviews = db.query(models.DoctorReview).all()
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for r in all_reviews:
        sentiment_counts[classify_review_sentiment(r.rating, r.comment)] += 1
    avg_platform_rating = (
        round(sum(r.rating for r in all_reviews) / len(all_reviews), 2)
        if all_reviews else None
    )

    completed_appts = (
        db.query(models.Appointment)
        .join(models.DoctorProfile, models.Appointment.doctor_id == models.DoctorProfile.id)
        .filter(models.Appointment.status == models.AppointmentStatus.completed)
        .all()
    )
    total_revenue = sum(a.doctor.consultation_fee for a in completed_appts if a.doctor)

    revenue_last_7_days = defaultdict(float)
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        revenue_last_7_days[day.isoformat()] = 0.0
    for a in completed_appts:
        day_key = a.start_time.date().isoformat()
        if day_key in revenue_last_7_days:
            revenue_last_7_days[day_key] += a.doctor.consultation_fee if a.doctor else 0

    return schemas.AnalyticsOut(
        total_users=total_users,
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        completed_appointments=completed,
        cancelled_appointments=cancelled,
        appointments_per_specialty=dict(per_specialty),
        appointments_last_7_days=dict(last_7_days),
        review_sentiment=sentiment_counts,
        avg_platform_rating=avg_platform_rating,
        total_revenue=round(total_revenue, 2),
        revenue_last_7_days=dict(revenue_last_7_days),
    )


@app.get("/admin/activity", response_model=list[schemas.ActivityItem], tags=["Admin"])
def admin_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    items = []
    for a in db.query(models.Appointment).order_by(models.Appointment.created_at.desc()).limit(limit).all():
        items.append(schemas.ActivityItem(
            type="appointment_created",
            message=f"{a.patient.full_name if a.patient else '?'} დაჯავშნა ვიზიტი ექიმთან {a.doctor.user.full_name if a.doctor else '?'}",
            timestamp=a.created_at,
        ))
    for r in db.query(models.DoctorReview).order_by(models.DoctorReview.created_at.desc()).limit(limit).all():
        items.append(schemas.ActivityItem(
            type="review_added",
            message=f"{r.patient.full_name if r.patient else '?'} დაწერა შეფასება ({r.rating}/5) ექიმისთვის {r.doctor.user.full_name if r.doctor else '?'}",
            timestamp=r.created_at,
        ))
    role_labels = {"patient": "პაციენტი", "doctor": "ექიმი", "admin": "ადმინი"}
    for u in db.query(models.User).order_by(models.User.created_at.desc()).limit(limit).all():
        items.append(schemas.ActivityItem(
            type="user_registered",
            message=f"ახალი მომხმარებელი დარეგისტრირდა: {u.full_name} ({role_labels.get(u.role.value, u.role.value)})",
            timestamp=u.created_at,
        ))
    items.sort(key=lambda i: i.timestamp, reverse=True)
    return items[:limit]


@app.get("/admin/top-doctors", response_model=list[schemas.TopDoctorOut], tags=["Admin"])
def top_doctors(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    doctors = db.query(models.DoctorProfile).all()
    results = []
    for d in doctors:
        ratings = [r.rating for r in d.reviews]
        appt_count = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == d.id,
            models.Appointment.status == models.AppointmentStatus.completed,
        ).count()
        results.append(schemas.TopDoctorOut(
            doctor_id=d.id,
            full_name=d.user.full_name if d.user else "?",
            specialty=d.specialty,
            avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
            review_count=len(ratings),
            appointment_count=appt_count,
        ))
    results.sort(key=lambda r: (r.avg_rating or 0, r.review_count), reverse=True)
    return results[:limit]


@app.get("/admin/users", response_model=list[schemas.UserOut], tags=["Admin"])
def list_users(
    search: str | None = None,
    role: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    query = db.query(models.User)
    if search:
        query = query.filter(
            (models.User.full_name.ilike(f"%{search}%"))
            | (models.User.email.ilike(f"%{search}%"))
        )
    if role:
        query = query.filter(models.User.role == role)
    return query.order_by(models.User.created_at.desc()).all()


@app.put("/admin/users/{user_id}/status", response_model=schemas.UserOut, tags=["Admin"])
def update_user_status(
    user_id: int,
    payload: schemas.UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="საკუთარი ანგარიშის დეაქტივაცია არ შეიძლება")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი ვერ მოიძებნა")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@app.post("/admin/doctors", response_model=schemas.DoctorOut, tags=["Admin"])
def admin_create_doctor(
    payload: schemas.AdminDoctorCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="ეს ელ-ფოსტა უკვე რეგისტრირებულია")
    if payload.phone:
        existing_phone = db.query(models.User).filter(
            models.User.phone == payload.phone
        ).first()
        if existing_phone:
            raise HTTPException(
                status_code=400, detail="ეს ტელეფონის ნომერი უკვე რეგისტრირებულია"
            )
    user = models.User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=models.RoleEnum.doctor,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    profile = models.DoctorProfile(
        user_id=user.id,
        specialty=payload.specialty,
        bio=payload.bio,
        years_experience=payload.years_experience or 0,
        consultation_fee=payload.consultation_fee or 0.0,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return doctor_to_out(profile)


@app.put("/admin/doctors/{doctor_id}", response_model=schemas.DoctorOut, tags=["Admin"])
def admin_update_doctor(
    doctor_id: int,
    payload: schemas.AdminDoctorUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    profile = db.query(models.DoctorProfile).filter(
        models.DoctorProfile.id == doctor_id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="ექიმი ვერ მოიძებნა")

    if payload.full_name:
        profile.user.full_name = payload.full_name
    if payload.phone is not None:
        profile.user.phone = payload.phone
    if payload.specialty:
        profile.specialty = payload.specialty
    if payload.bio is not None:
        profile.bio = payload.bio
    if payload.years_experience is not None:
        profile.years_experience = payload.years_experience
    if payload.consultation_fee is not None:
        profile.consultation_fee = payload.consultation_fee
    if payload.is_active is not None:
        profile.user.is_active = payload.is_active

    db.commit()
    db.refresh(profile)
    return doctor_to_out(profile)


# ---------------------------------------------------------------------------
# Health check + static frontend
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
