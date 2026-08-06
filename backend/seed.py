"""
საწყისი მონაცემების (seed) სკრიპტი.
გაუშვით ერთხელ, პროექტის პირველი გაშვებისას:  python seed.py
ქმნის: ერთ ადმინს, რამდენიმე ექიმს სხვადასხვა სპეციალობით და ერთ სატესტო პაციენტს.
"""

from database import SessionLocal, engine, Base
import models
from auth import get_password_hash

Base.metadata.create_all(bind=engine)

db = SessionLocal()

DEMO_ACCOUNTS = [
    {
        "email": "admin@clinic.ge",
        "password": "admin123",
        "full_name": "ადმინისტრატორი",
        "role": models.RoleEnum.admin,
    },
    {
        "email": "patient@clinic.ge",
        "password": "patient123",
        "full_name": "ლუკა მაისურაძე",
        "role": models.RoleEnum.patient,
        "phone": "555112233",
    },
]

DEMO_DOCTORS = [
    # --- კარდიოლოგი ---
    {
        "email": "cardio@clinic.ge",
        "password": "doctor123",
        "full_name": "დავით ბერიძე",
        "specialty": "კარდიოლოგი",
        "bio": "კარდიოლოგი, 12 წლიანი გამოცდილებით გულ-სისხლძარღვთა დაავადებების დიაგნოსტიკასა და მკურნალობაში.",
        "years_experience": 12,
        "consultation_fee": 80,
    },
    {
        "email": "cardio2@clinic.ge",
        "password": "doctor123",
        "full_name": "ირაკლი მუმლაძე",
        "specialty": "კარდიოლოგი",
        "bio": "კარდიოლოგი-არითმოლოგი, გულის რითმის დარღვევების დიაგნოსტიკისა და მკურნალობის სპეციალისტი.",
        "years_experience": 22,
        "consultation_fee": 140,
    },
    {
        "email": "cardio3@clinic.ge",
        "password": "doctor123",
        "full_name": "სალომე ჯავახია",
        "specialty": "კარდიოლოგი",
        "bio": "ახალგაზრდა კარდიოლოგი, ჰიპერტენზიისა და პროფილაქტიკური კარდიოლოგიის მიმართულებით.",
        "years_experience": 4,
        "consultation_fee": 45,
    },
    {
        "email": "cardio4@clinic.ge",
        "password": "doctor123",
        "full_name": "თემურ ბასილაშვილი",
        "specialty": "კარდიოლოგი",
        "bio": "ინტერვენციული კარდიოლოგი, კორონაროგრაფიისა და სტენტირების სპეციალისტი.",
        "years_experience": 18,
        "consultation_fee": 180,
    },
    {
        "email": "cardio5@clinic.ge",
        "password": "doctor123",
        "full_name": "ნინო ბოკუჩავა",
        "specialty": "კარდიოლოგი",
        "bio": "კარდიოლოგი, ეხოკარდიოგრაფიისა და გულის უკმარისობის მართვის მიმართულებით.",
        "years_experience": 9,
        "consultation_fee": 65,
    },
    # --- დერმატოლოგი ---
    {
        "email": "derma@clinic.ge",
        "password": "doctor123",
        "full_name": "ნინო კვარაცხელია",
        "specialty": "დერმატოლოგი",
        "bio": "დერმატოლოგი, სპეციალიზირებული კანის ქრონიკული დაავადებების მკურნალობაში.",
        "years_experience": 8,
        "consultation_fee": 60,
    },
    {
        "email": "derma2@clinic.ge",
        "password": "doctor123",
        "full_name": "ეკატერინე დათუნაშვილი",
        "specialty": "დერმატოლოგი",
        "bio": "დერმატო-კოსმეტოლოგი, აკნესა და კანის პიგმენტაციის პრობლემების მკურნალობაში გამოცდილი.",
        "years_experience": 16,
        "consultation_fee": 100,
    },
    {
        "email": "derma3@clinic.ge",
        "password": "doctor123",
        "full_name": "ბექა ცინცაძე",
        "specialty": "დერმატოლოგი",
        "bio": "დერმატოლოგი, ალერგიული დერმატიტისა და ფსორიაზის მართვის სპეციალისტი.",
        "years_experience": 3,
        "consultation_fee": 35,
    },
    {
        "email": "derma4@clinic.ge",
        "password": "doctor123",
        "full_name": "თინათინ მეგრელიშვილი",
        "specialty": "დერმატოლოგი",
        "bio": "დერმატო-ონკოლოგი, ხალების კონტროლისა და კანის სიმსივნური წარმონაქმნების ადრეული დიაგნოსტიკის სპეციალისტი.",
        "years_experience": 21,
        "consultation_fee": 130,
    },
    {
        "email": "derma5@clinic.ge",
        "password": "doctor123",
        "full_name": "გიგა სვანიძე",
        "specialty": "დერმატოლოგი",
        "bio": "დერმატოლოგი, სოკოვანი და ბაქტერიული კანის ინფექციების მკურნალობაში გამოცდილი.",
        "years_experience": 12,
        "consultation_fee": 55,
    },
    # --- ნევროლოგი ---
    {
        "email": "neuro@clinic.ge",
        "password": "doctor123",
        "full_name": "გიორგი წერეთელი",
        "specialty": "ნევროლოგი",
        "bio": "ნევროლოგი, თავის ტკივილისა და მიგრენის მკურნალობის სპეციალისტი.",
        "years_experience": 15,
        "consultation_fee": 90,
    },
    {
        "email": "neuro2@clinic.ge",
        "password": "doctor123",
        "full_name": "მარიამ ხუციშვილი",
        "specialty": "ნევროლოგი",
        "bio": "ნევროლოგი, ინსულტის შემდგომი რეაბილიტაციისა და ნეიროდეგენერაციული დაავადებების მიმართულებით.",
        "years_experience": 25,
        "consultation_fee": 150,
    },
    {
        "email": "neuro3@clinic.ge",
        "password": "doctor123",
        "full_name": "ლაშა ბარნაბიშვილი",
        "specialty": "ნევროლოგი",
        "bio": "ნევროლოგი, ეპილეფსიისა და ნეირომუსკულური დაავადებების დიაგნოსტიკის სპეციალისტი.",
        "years_experience": 10,
        "consultation_fee": 78,
    },
    {
        "email": "neuro4@clinic.ge",
        "password": "doctor123",
        "full_name": "ელენე ფხაკაძე",
        "specialty": "ნევროლოგი",
        "bio": "ახალგაზრდა ნევროლოგი, თავბრუსხვევისა და ძილის დარღვევების მართვის მიმართულებით.",
        "years_experience": 3,
        "consultation_fee": 30,
    },
    # --- ოჯახის ექიმი ---
    {
        "email": "family@clinic.ge",
        "password": "doctor123",
        "full_name": "თამარ ლომიძე",
        "specialty": "ოჯახის ექიმი",
        "bio": "ოჯახის ექიმი ზოგადი პროფილის დაავადებების დიაგნოსტიკისთვის.",
        "years_experience": 6,
        "consultation_fee": 40,
    },
    {
        "email": "family2@clinic.ge",
        "password": "doctor123",
        "full_name": "ვახტანგ ონიანი",
        "specialty": "ოჯახის ექიმი",
        "bio": "ოჯახის ექიმი, პრევენციული მედიცინისა და ქრონიკული დაავადებების მართვის სპეციალისტი.",
        "years_experience": 18,
        "consultation_fee": 55,
    },
    {
        "email": "family3@clinic.ge",
        "password": "doctor123",
        "full_name": "ანა კახიძე",
        "specialty": "ოჯახის ექიმი",
        "bio": "ახალგაზრდა ოჯახის ექიმი, ხელმისაწვდომი პირველადი ჯანდაცვისთვის.",
        "years_experience": 2,
        "consultation_fee": 25,
    },
    {
        "email": "family4@clinic.ge",
        "password": "doctor123",
        "full_name": "რევაზ დოლიძე",
        "specialty": "ოჯახის ექიმი",
        "bio": "ოჯახის ექიმი, მრავალწლიანი გამოცდილებით ქრონიკული პაციენტების გრძელვადიან მეთვალყურეობაში.",
        "years_experience": 27,
        "consultation_fee": 60,
    },
    {
        "email": "family5@clinic.ge",
        "password": "doctor123",
        "full_name": "მაკა წიკლაური",
        "specialty": "ოჯახის ექიმი",
        "bio": "ოჯახის ექიმი, ქალთა და მამაკაცთა პროფილაქტიკური სამედიცინო შემოწმებების სპეციალისტი.",
        "years_experience": 9,
        "consultation_fee": 42,
    },
    # --- გასტროენტეროლოგი ---
    {
        "email": "gastro@clinic.ge",
        "password": "doctor123",
        "full_name": "ლევან აბაშიძე",
        "specialty": "გასტროენტეროლოგი",
        "bio": "გასტროენტეროლოგი, კუჭ-ნაწლავის დაავადებების დიაგნოსტიკა და მკურნალობა.",
        "years_experience": 10,
        "consultation_fee": 70,
    },
    {
        "email": "gastro2@clinic.ge",
        "password": "doctor123",
        "full_name": "თეონა სიხარულიძე",
        "specialty": "გასტროენტეროლოგი",
        "bio": "გასტროენტეროლოგი-ჰეპატოლოგი, ღვიძლის დაავადებებისა და ენდოსკოპიური კვლევების სპეციალისტი.",
        "years_experience": 14,
        "consultation_fee": 95,
    },
    {
        "email": "gastro3@clinic.ge",
        "password": "doctor123",
        "full_name": "არჩილ ცერცვაძე",
        "specialty": "გასტროენტეროლოგი",
        "bio": "გასტროენტეროლოგი, წყლულოვანი კოლიტისა და კრონის დაავადების მართვის სპეციალისტი.",
        "years_experience": 19,
        "consultation_fee": 110,
    },
    {
        "email": "gastro4@clinic.ge",
        "password": "doctor123",
        "full_name": "მარიამ გაბრიჩიძე",
        "specialty": "გასტროენტეროლოგი",
        "bio": "ახალგაზრდა გასტროენტეროლოგი, გულძმარვისა და რეფლუქსური დაავადების მკურნალობაში.",
        "years_experience": 5,
        "consultation_fee": 48,
    },
    # --- პულმონოლოგი ---
    {
        "email": "pulmo@clinic.ge",
        "password": "doctor123",
        "full_name": "ზურაბ გელაშვილი",
        "specialty": "პულმონოლოგი",
        "bio": "პულმონოლოგი, ასთმისა და ქრონიკული ბრონქიტის მკურნალობის სპეციალისტი.",
        "years_experience": 11,
        "consultation_fee": 75,
    },
    {
        "email": "pulmo2@clinic.ge",
        "password": "doctor123",
        "full_name": "ნატა ბერაია",
        "specialty": "პულმონოლოგი",
        "bio": "პულმონოლოგი, სასუნთქი გზების ალერგიული დაავადებების დიაგნოსტიკისა და მკურნალობის მიმართულებით.",
        "years_experience": 5,
        "consultation_fee": 50,
    },
    {
        "email": "pulmo3@clinic.ge",
        "password": "doctor123",
        "full_name": "ავთანდილ ჟორჟოლიანი",
        "specialty": "პულმონოლოგი",
        "bio": "პულმონოლოგი, ქრონიკული ობსტრუქციული ფილტვის დაავადებისა (COPD) და ძილის აპნოეს სპეციალისტი.",
        "years_experience": 16,
        "consultation_fee": 88,
    },
    {
        "email": "pulmo4@clinic.ge",
        "password": "doctor123",
        "full_name": "ლიკა ბერიაშვილი",
        "specialty": "პულმონოლოგი",
        "bio": "ახალგაზრდა პულმონოლოგი, ხანგრძლივი ხველისა და ბრონქული ჰიპერრეაქტიულობის დიაგნოსტიკაში.",
        "years_experience": 4,
        "consultation_fee": 38,
    },
    # --- ორთოპედი ---
    {
        "email": "ortho@clinic.ge",
        "password": "doctor123",
        "full_name": "გელა ნადირაძე",
        "specialty": "ორთოპედი",
        "bio": "ორთოპედ-ტრავმატოლოგი, სახსრების დაავადებებისა და სპორტული ტრავმების სპეციალისტი.",
        "years_experience": 20,
        "consultation_fee": 120,
    },
    {
        "email": "ortho2@clinic.ge",
        "password": "doctor123",
        "full_name": "დათო ხარაზი",
        "specialty": "ორთოპედი",
        "bio": "ორთოპედი, ზურგისა და ხერხემლის დაავადებების კონსერვატიული მკურნალობის სპეციალისტი.",
        "years_experience": 7,
        "consultation_fee": 65,
    },
    {
        "email": "ortho3@clinic.ge",
        "password": "doctor123",
        "full_name": "ვაჟა კვირკველია",
        "specialty": "ორთოპედი",
        "bio": "ორთოპედ-ქირურგი, სახსრის ენდოპროთეზირებისა და მუხლის სახსრის ოპერაციების სპეციალისტი.",
        "years_experience": 24,
        "consultation_fee": 160,
    },
    {
        "email": "ortho4@clinic.ge",
        "password": "doctor123",
        "full_name": "ნინო ჩხეიძე",
        "specialty": "ორთოპედი",
        "bio": "ახალგაზრდა ორთოპედი, სპორტული დაზიანებებისა და რეაბილიტაციის მიმართულებით.",
        "years_experience": 4,
        "consultation_fee": 40,
    },
    # --- პედიატრი ---
    {
        "email": "pediatr@clinic.ge",
        "password": "doctor123",
        "full_name": "ლალი კუპრავა",
        "specialty": "პედიატრი",
        "bio": "პედიატრი, 17 წლიანი გამოცდილებით ბავშვთა ინფექციური და ალერგიული დაავადებების მკურნალობაში.",
        "years_experience": 17,
        "consultation_fee": 60,
    },
    {
        "email": "pediatr2@clinic.ge",
        "password": "doctor123",
        "full_name": "სოფო არველაძე",
        "specialty": "პედიატრი",
        "bio": "პედიატრი, ახალშობილთა და ადრეული ასაკის ბავშვების მეთვალყურეობის სპეციალისტი.",
        "years_experience": 6,
        "consultation_fee": 40,
    },
    {
        "email": "pediatr3@clinic.ge",
        "password": "doctor123",
        "full_name": "დავით მარგველაშვილი",
        "specialty": "პედიატრი",
        "bio": "პედიატრი-ალერგოლოგი, ბავშვთა კვებითი ალერგიისა და ასთმის მართვის სპეციალისტი.",
        "years_experience": 20,
        "consultation_fee": 85,
    },
    {
        "email": "pediatr4@clinic.ge",
        "password": "doctor123",
        "full_name": "ქეთევან ბენიძე",
        "specialty": "პედიატრი",
        "bio": "ახალგაზრდა პედიატრი, პროფილაქტიკური ვაქცინაციისა და ბავშვთა კვების საკითხებში.",
        "years_experience": 3,
        "consultation_fee": 28,
    },
    # --- ოტორინოლარინგოლოგი ---
    {
        "email": "ent@clinic.ge",
        "password": "doctor123",
        "full_name": "მერაბ თოფურია",
        "specialty": "ოტორინოლარინგოლოგი",
        "bio": "ოტორინოლარინგოლოგი (ყელ-ყურ-ცხვირი), სინუსიტისა და ქრონიკული ტონზილიტის მკურნალობის სპეციალისტი.",
        "years_experience": 13,
        "consultation_fee": 70,
    },
    {
        "email": "ent2@clinic.ge",
        "password": "doctor123",
        "full_name": "ხატია ლომსაძე",
        "specialty": "ოტორინოლარინგოლოგი",
        "bio": "ოტორინოლარინგოლოგი, სმენის დარღვევებისა და ვესტიბულური აპარატის დაავადებების დიაგნოსტიკაში გამოცდილი.",
        "years_experience": 9,
        "consultation_fee": 58,
    },
    {
        "email": "ent3@clinic.ge",
        "password": "doctor123",
        "full_name": "პაატა ლორთქიფანიძე",
        "specialty": "ოტორინოლარინგოლოგი",
        "bio": "ოტორინოლარინგოლოგი-ქირურგი, ცხვირის ძგიდის გამრუდებისა და სინუსების ქირურგიის სპეციალისტი.",
        "years_experience": 23,
        "consultation_fee": 145,
    },
    {
        "email": "ent4@clinic.ge",
        "password": "doctor123",
        "full_name": "ია ჩიგოგიძე",
        "specialty": "ოტორინოლარინგოლოგი",
        "bio": "ახალგაზრდა ოტორინოლარინგოლოგი, ბავშვთა და მოზრდილთა ტონზილიტის მკურნალობაში.",
        "years_experience": 5,
        "consultation_fee": 44,
    },
    {
        "email": "nikabero@gmail.com",
        "password": "nika12345",
        "full_name": "ნიკოლოზ ბერიძე",
        "specialty": "კარდიოლოგი",
        "bio": "კარდიოლოგი, სპეციალიზებულია გულ-სისხლძარღვთა სისტემის პროფილაქტიკურ დიაგნოსტიკასა და მკურნალობაში.",
        "years_experience": 15,
        "consultation_fee": 90,
    },
]


def get_or_create_user(email, password, full_name, role, phone=None):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return existing
    user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        role=role,
        phone=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main():
    for acc in DEMO_ACCOUNTS:
        get_or_create_user(
            acc["email"], acc["password"], acc["full_name"], acc["role"], acc.get("phone")
        )

    for doc in DEMO_DOCTORS:
        user = get_or_create_user(
            doc["email"], doc["password"], doc["full_name"], models.RoleEnum.doctor
        )
        existing_profile = (
            db.query(models.DoctorProfile)
            .filter(models.DoctorProfile.user_id == user.id)
            .first()
        )
        if not existing_profile:
            profile = models.DoctorProfile(
                user_id=user.id,
                specialty=doc["specialty"],
                bio=doc["bio"],
                years_experience=doc["years_experience"],
                consultation_fee=doc["consultation_fee"],
            )
            db.add(profile)
    db.commit()
    print("✅ საწყისი მონაცემები წარმატებით შეიქმნა.")
    print("\nსატესტო ანგარიშები:")
    print("  ადმინი:    admin@clinic.ge / admin123")
    print("  პაციენტი:  patient@clinic.ge / patient123")
    print("  ექიმები:   cardio@clinic.ge / doctor123  (და სხვა, იხ. seed.py)")
    print("             nikabero@gmail.com / nika12345")


if __name__ == "__main__":
    main()

