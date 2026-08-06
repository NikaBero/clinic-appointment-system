"""
საქართველოს ოფიციალური უქმე დღეების კალენდარი.

მოიცავს ფიქსირებულ თარიღებს და მოძრავ (მართლმადიდებლური აღდგომის მიხედვით
გამოთვლილ) დღესასწაულებს. აღდგომის თარიღი გამოითვლება Meeus-ის
იულიანური ალგორითმით და გადაყვანილია გრიგორიანულ კალენდარში (+13 დღე,
სწორია 1900-2099 პერიოდისთვის).

გამოიყენება ჯავშნის სისტემაში, რომ ექიმებმა ავტომატურად ვერ მიიღონ
ჯავშნები ოფიციალურ უქმე დღეებზე — მსგავსად ინდივიდუალური "დასვენების
დღის" ფუნქციონალისა, უბრალოდ ყველა ექიმისთვის ერთდროულად.
"""

from datetime import date, timedelta
from functools import lru_cache
from typing import Dict


@lru_cache(maxsize=None)
def _orthodox_easter(year: int) -> date:
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    julian_easter = date(year, month, day)
    return julian_easter + timedelta(days=13)  # Julian -> Gregorian (1900-2099)


@lru_cache(maxsize=None)
def get_holidays(year: int) -> Dict[date, str]:
    fixed = {
        date(year, 1, 1): "ახალი წელი",
        date(year, 1, 2): "ახალი წელი",
        date(year, 1, 7): "შობა",
        date(year, 1, 19): "ნათლისღება",
        date(year, 3, 3): "დედის დღე",
        date(year, 3, 8): "ქალთა საერთაშორისო დღე",
        date(year, 4, 9): "ეროვნული ერთიანობის დღე",
        date(year, 5, 9): "ფაშიზმზე გამარჯვების დღე",
        date(year, 5, 12): "წმინდა ანდრია პირველწოდებულის დღე",
        date(year, 5, 26): "დამოუკიდებლობის დღე",
        date(year, 8, 28): "მარიამობა",
        date(year, 10, 14): "მცხეთობის დღე (სვეტიცხოვლობა)",
        date(year, 11, 23): "გიორგობა",
    }
    easter = _orthodox_easter(year)
    movable = {
        easter - timedelta(days=2): "წითელი პარასკევი",
        easter - timedelta(days=1): "დიდი შაბათი",
        easter: "აღდგომა",
        easter + timedelta(days=1): "შემდეგი ორშაბათი",
    }
    return {**fixed, **movable}


def holiday_name(day: date) -> str | None:
    return get_holidays(day.year).get(day)
