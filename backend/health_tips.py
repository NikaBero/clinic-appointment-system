"""
გარე საჯარო API-დან (Open-Meteo — უფასო, API-გასაღების გარეშე) მიმდინარე
ამინდის მონაცემების წამოღება და, მათ საფუძველზე, მარტივი rule-based
ჯანმრთელობის რჩევის გენერაცია. დემონსტრირებს გარე მონაცემთა ინტეგრაციას
კლინიკის სისტემაში (მაგ: მაღალი UV-ინდექსი → დერმატოლოგიური რჩევა მზისგან
დაცვაზე, დაბალი ტემპერატურა → გრიპის სეზონის რჩევა ოჯახის ექიმისგან).

თუ გარე სერვისთან წვდომა ვერ ხერხდება (ინტერნეტის გარეშე დემონსტრაციისას),
ფუნქცია გამჭვირვალედ აბრუნებს available=False-ს და საიტის დანარჩენი
ფუნქციონალი ხელუხლებელი რჩება.
"""

import httpx

TBILISI_LAT = 41.7151
TBILISI_LON = 44.8271

WEATHER_CODE_LABELS = {
    0: "მზიანი", 1: "ძირითადად მზიანი", 2: "ნაწილობრივ ღრუბლიანი", 3: "ღრუბლიანი",
    45: "ნისლი", 48: "ყინულოვანი ნისლი",
    51: "წვიმის წვეთები", 53: "წვიმა", 55: "ძლიერი წვიმა",
    61: "სუსტი წვიმა", 63: "წვიმა", 65: "ძლიერი წვიმა",
    71: "თოვლი", 73: "თოვლი", 75: "ძლიერი თოვლი",
    80: "წვიმის შხაპუნი", 81: "წვიმის შხაპუნი", 82: "ძლიერი წვიმის შხაპუნი",
    95: "ჭექა-ქუხილი",
}


def _generate_tip(temp_c: float, uv_index: float, weather_code: int):
    condition = WEATHER_CODE_LABELS.get(weather_code, "ცვალებადი")

    if uv_index is not None and uv_index >= 6:
        return (
            f"დღეს UV-ინდექსი მაღალია ({uv_index:.0f}) — გირჩევთ მზისგან დამცავი კრემის "
            f"გამოყენებას და პირდაპირი მზის სხივების თავიდან აცილებას შუადღისას.",
            "დერმატოლოგი",
        )
    if temp_c is not None and temp_c <= 5:
        return (
            f"დღეს ცივა ({temp_c:.0f}°C) — გრიპისა და გაციების სეზონია, გირჩევთ თბილად "
            f"ჩაცმას და ხელების ხშირად დაბანას ვირუსების პრევენციისთვის.",
            "ოჯახის ექიმი",
        )
    if temp_c is not None and temp_c >= 32:
        return (
            f"დღეს სიცხეა ({temp_c:.0f}°C) — გირჩევთ საკმარისი წყლის მიღებას და მზეზე "
            f"ხანგრძლივი ყოფნის შეზღუდვას გულ-სისხლძარღვთა სისტემის დასატვირთად.",
            "კარდიოლოგი",
        )
    return (
        f"დღეს ამინდი {condition.lower()}ა, {temp_c:.0f}°C — განსაკუთრებული რისკები არ იკვეთება, "
        f"მაგრამ ზოგადი კეთილდღეობისთვის არ დაივიწყოთ საკმარისი წყალი და დასვენება.",
        None,
    )


def fetch_health_tip() -> dict:
    try:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": TBILISI_LAT,
                "longitude": TBILISI_LON,
                "current": "temperature_2m,weather_code,uv_index",
                "timezone": "Asia/Tbilisi",
            },
            timeout=4.0,
        )
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current", {})
        temp_c = current.get("temperature_2m")
        weather_code = current.get("weather_code")
        uv_index = current.get("uv_index")

        tip_text, related_specialty = _generate_tip(temp_c, uv_index, weather_code)

        return {
            "available": True,
            "location": "თბილისი",
            "temperature_c": temp_c,
            "condition": WEATHER_CODE_LABELS.get(weather_code, "ცვალებადი"),
            "uv_index": uv_index,
            "tip": tip_text,
            "related_specialty": related_specialty,
        }
    except Exception:
        return {"available": False}


def _aqi_category(us_aqi: float):
    if us_aqi <= 50:
        return "კარგი", "#2F855A"
    if us_aqi <= 100:
        return "ზომიერი", "#B8860B"
    if us_aqi <= 150:
        return "მგრძნობიარე ჯგუფებისთვის არაჯანსაღი", "#D97757"
    if us_aqi <= 200:
        return "არაჯანსაღი", "#C0392B"
    if us_aqi <= 300:
        return "ძალიან არაჯანსაღი", "#8E1A0F"
    return "საშიში", "#5A0F0A"


def fetch_air_quality() -> dict:
    """
    საზოგადოებრივი ჯანმრთელობის საჯარო მონაცემი — თბილისის ჰაერის ხარისხის
    ინდექსი (Open-Meteo Air Quality API, უფასო, key-ის გარეშე).
    """
    try:
        resp = httpx.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": TBILISI_LAT,
                "longitude": TBILISI_LON,
                "current": "pm2_5,pm10,us_aqi",
                "timezone": "Asia/Tbilisi",
            },
            timeout=4.0,
        )
        resp.raise_for_status()
        current = resp.json().get("current", {})
        us_aqi = current.get("us_aqi")
        pm2_5 = current.get("pm2_5")
        pm10 = current.get("pm10")
        if us_aqi is None:
            return {"available": False}
        category, color = _aqi_category(us_aqi)
        advice = None
        if us_aqi > 100:
            advice = (
                "ჰაერის ხარისხი დღეს დაქვეითებულია — ასთმის, ბრონქიტის ან სხვა "
                "სასუნთქი გზების ქრონიკული პრობლემების მქონე პირებს ვურჩევთ "
                "შეზღუდონ ხანგრძლივი დროით გარეთ ყოფნა."
            )
        return {
            "available": True,
            "location": "თბილისი",
            "us_aqi": us_aqi,
            "pm2_5": pm2_5,
            "pm10": pm10,
            "category": category,
            "color": color,
            "advice": advice,
        }
    except Exception:
        return {"available": False}
