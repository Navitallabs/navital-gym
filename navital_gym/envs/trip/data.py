"""Static, synthetic world facts for env #1 (Indian trip planning). Hand-written structure (which cities connect,
which sights exist, real closing days); prices, timetables and seat counts are generated from the seed in world.py.

THESE ARE ENV RULES, NOT CLAIMS ABOUT TODAY'S REAL WORLD. Distances and durations follow public knowledge to a
rough approximation; every fare, price, train id, hotel and seat count is synthetic. No customer data, no scraped
or licensed dataset, no real booking system.
"""
import datetime as dt

DEFAULT_SNAPSHOT = "2026-11-15"
PEAK_FROM, PEAK_TO = "12-24", "01-02"        # peak surcharge window, inclusive (month-day)

# city -> (region, altitude_m, hill_roads, price_factor)
CITIES = {
    "Delhi": ("north", 220, False, 1.15), "Agra": ("north", 170, False, 0.9), "Jaipur": ("rajasthan", 430, False, 1.0),
    "Jodhpur": ("rajasthan", 230, False, 0.95), "Udaipur": ("rajasthan", 600, False, 1.05),
    "Varanasi": ("north", 80, False, 0.9), "Ayodhya": ("north", 93, False, 0.85), "Lucknow": ("north", 120, False, 0.9),
    "Mumbai": ("west", 14, False, 1.3), "Pune": ("west", 560, False, 1.0), "Goa": ("west", 20, False, 1.2),
    "Bengaluru": ("south", 920, False, 1.15), "Chennai": ("south", 10, False, 1.05),
    "Kochi": ("kerala", 5, False, 1.0), "Munnar": ("kerala", 1500, True, 1.05), "Alleppey": ("kerala", 2, False, 1.0),
    "Chandigarh": ("north", 330, False, 0.95), "Shimla": ("himachal", 2200, True, 1.0), "Manali": ("himachal", 2050, True, 1.05),
    "Guwahati": ("northeast", 55, False, 0.9), "Shillong": ("northeast", 1500, True, 0.95), "Kaziranga": ("northeast", 80, False, 0.9),
    "Leh": ("ladakh", 3500, True, 1.3), "Nubra": ("ladakh", 3100, True, 1.15), "Pangong": ("ladakh", 4250, True, 1.2),
}

# (a, b, km, modes). Rail/road edges work both ways. "hill" comes from either end city.
EDGES = [
    ("Delhi", "Agra", 200, "rail road"), ("Agra", "Jaipur", 240, "rail road"), ("Delhi", "Jaipur", 300, "rail road"),
    ("Jaipur", "Udaipur", 400, "rail road"), ("Jaipur", "Jodhpur", 340, "rail road"), ("Jodhpur", "Udaipur", 250, "rail road"),
    ("Delhi", "Udaipur", 650, "rail"), ("Delhi", "Jodhpur", 600, "rail"),
    ("Delhi", "Lucknow", 500, "rail road"), ("Lucknow", "Varanasi", 300, "rail road"), ("Lucknow", "Ayodhya", 135, "rail road"),
    ("Varanasi", "Ayodhya", 210, "rail road"), ("Delhi", "Varanasi", 800, "rail air"), ("Delhi", "Ayodhya", 680, "rail"),
    ("Delhi", "Chandigarh", 245, "rail road"), ("Chandigarh", "Shimla", 115, "road"), ("Shimla", "Manali", 250, "road"),
    ("Chandigarh", "Manali", 300, "road"),
    ("Mumbai", "Pune", 150, "rail road"), ("Mumbai", "Goa", 590, "rail road air"), ("Bengaluru", "Goa", 560, "rail road air"),
    ("Chennai", "Bengaluru", 350, "rail road air"), ("Kochi", "Alleppey", 60, "rail road"), ("Kochi", "Munnar", 130, "road"),
    ("Munnar", "Alleppey", 140, "road"), ("Mumbai", "Kochi", 1300, "rail air"), ("Bengaluru", "Kochi", 540, "rail air"),
    ("Guwahati", "Shillong", 100, "road"), ("Shillong", "Kaziranga", 250, "road"), ("Guwahati", "Kaziranga", 190, "road"),
    ("Delhi", "Leh", 700, "air"), ("Leh", "Nubra", 120, "road"), ("Leh", "Pangong", 160, "road"), ("Nubra", "Pangong", 200, "road"),
    ("Manali", "Leh", 480, "road"), ("Delhi", "Goa", 1900, "air"), ("Delhi", "Guwahati", 1500, "air"), ("Delhi", "Kochi", 2200, "air"),
    ("Delhi", "Mumbai", 1400, "rail air"), ("Mumbai", "Chennai", 1300, "air"), ("Guwahati", "Leh", 2200, "air"),
]

# Road links closed outside these (month, day) windows (inclusive). Winter closure of Manali-Leh is the classic.
ROAD_SEASON = {("Manali", "Leh"): ("06-01", "10-31")}

# Explicit sold-out train corridors (every train and class shows WL on these dates for general quota).
SOLD_OUT = {("Mumbai", "Goa"): ["2026-11-16", "2026-12-30", "2026-12-31", "2027-01-01"], ("Goa", "Mumbai"): ["2027-01-01", "2027-01-02"], ("Mumbai", "Pune"): ["2026-12-04"]}

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# attraction id -> dict(city, name, closed (weekdays), open, close, minutes, adult_inr, season (month-day window the sight is open) or None,
#                       wheelchair, permit, sunrise (has an early slot), kind)
def A(city, name, closed="", open="09:00", close="17:30", minutes=120, adult=300, season=None, wheelchair=True, permit=False, sunrise=False, kind="sight"):
    return dict(city=city, name=name, closed=closed.split(), open=open, close=close, minutes=minutes, adult_inr=adult,
                season=season, wheelchair=wheelchair, permit=permit, sunrise=sunrise, kind=kind)

ATTRACTIONS = {a["name"]: a for a in [
    A("Delhi", "Red Fort", closed="Mon", open="09:30", close="16:30", adult=600), A("Delhi", "Humayun's Tomb", open="06:00", close="18:00", adult=600, minutes=90),
    A("Delhi", "Chandni Chowk food walk", open="10:00", close="20:00", adult=900, minutes=150, kind="walk"),
    A("Agra", "Taj Mahal", closed="Fri", open="06:00", close="18:30", adult=1100, minutes=150, sunrise=True), A("Agra", "Agra Fort", open="06:00", close="18:00", adult=650, minutes=120),
    A("Jaipur", "Amber Fort", open="08:00", close="17:30", adult=500, minutes=150, wheelchair=False), A("Jaipur", "City Palace", open="09:30", close="17:00", adult=700, minutes=120),
    A("Jaipur", "Hawa Mahal", open="09:00", close="16:30", adult=200, minutes=60),
    A("Jodhpur", "Mehrangarh Fort", open="09:00", close="17:30", adult=600, minutes=150), A("Jodhpur", "Jaswant Thada", open="09:00", close="17:00", adult=100, minutes=60),
    A("Udaipur", "City Palace Udaipur", open="09:30", close="17:30", adult=500, minutes=120), A("Udaipur", "Lake Pichola boat ride", open="10:00", close="18:00", adult=600, minutes=60),
    A("Varanasi", "Ganga Aarti", open="18:30", close="19:45", adult=0, minutes=75, kind="evening"), A("Varanasi", "Kashi Vishwanath darshan", open="05:00", close="12:00", adult=0, minutes=90),
    A("Varanasi", "Sarnath", closed="", open="09:00", close="17:00", adult=200, minutes=120),
    A("Ayodhya", "Ram Mandir darshan", open="07:00", close="11:30", adult=0, minutes=120), A("Ayodhya", "Hanuman Garhi", open="05:00", close="21:00", adult=0, minutes=45),
    A("Lucknow", "Bara Imambara", open="09:00", close="17:00", adult=300, minutes=90), A("Lucknow", "Chowk food walk", open="11:00", close="21:00", adult=700, minutes=120, kind="walk"),
    A("Mumbai", "Gateway of India", open="00:00", close="23:59", adult=0, minutes=45), A("Mumbai", "Elephanta Caves", closed="Mon", open="09:00", close="17:00", adult=500, minutes=240),
    A("Pune", "Shaniwar Wada", open="08:00", close="18:00", adult=200, minutes=75),
    A("Goa", "Basilica of Bom Jesus", open="09:00", close="18:30", adult=0, minutes=60), A("Goa", "Fort Aguada", open="09:30", close="18:00", adult=50, minutes=60),
    A("Goa", "Beach day Palolem", open="00:00", close="23:59", adult=0, minutes=240, kind="beach"),
    A("Bengaluru", "Lalbagh Garden", open="06:00", close="19:00", adult=40, minutes=90), A("Chennai", "Marina Beach", open="00:00", close="23:59", adult=0, minutes=60),
    A("Kochi", "Fort Kochi walk", open="08:00", close="19:00", adult=0, minutes=120, kind="walk"), A("Kochi", "Kathakali show", open="18:00", close="20:00", adult=400, minutes=90, kind="evening"),
    A("Munnar", "Tea Museum", closed="Mon", open="09:00", close="16:00", adult=125, minutes=75), A("Munnar", "Eravikulam viewpoint", open="08:00", close="16:00", adult=200, minutes=150, wheelchair=False),
    A("Alleppey", "Backwater cruise", open="08:00", close="17:00", adult=700, minutes=180), A("Alleppey", "Houseboat evening cruise", open="16:00", close="19:00", adult=0, minutes=120, kind="evening"),
    A("Chandigarh", "Rock Garden", open="09:00", close="19:00", adult=50, minutes=90),
    A("Shimla", "The Ridge and Mall Road", open="00:00", close="23:59", adult=0, minutes=120, kind="walk"), A("Shimla", "Kufri", open="09:00", close="17:00", adult=100, minutes=180, wheelchair=False),
    A("Manali", "Hadimba Temple", open="08:00", close="17:00", adult=0, minutes=60), A("Manali", "Solang Valley", open="09:00", close="16:30", adult=300, minutes=180, wheelchair=False),
    A("Manali", "Rohtang Pass", open="07:00", close="15:00", adult=550, minutes=360, season=("05-15", "11-15"), wheelchair=False),
    A("Guwahati", "Kamakhya Temple", open="08:00", close="17:30", adult=0, minutes=120), A("Shillong", "Umiam Lake", open="08:00", close="17:00", adult=100, minutes=90),
    A("Shillong", "Cherrapunji day trip", open="08:00", close="16:30", adult=200, minutes=300, wheelchair=False),
    A("Kaziranga", "Kaziranga Jeep Safari", open="06:00", close="15:30", adult=1800, minutes=180, season=("11-01", "04-30"), kind="safari", wheelchair=False),
    A("Kaziranga", "Kaziranga Elephant Safari", open="05:30", close="07:30", adult=1300, minutes=60, season=("11-01", "04-30"), kind="safari", wheelchair=False),
    A("Leh", "Leh Palace", open="08:00", close="17:00", adult=200, minutes=90, wheelchair=False), A("Leh", "Shanti Stupa", open="05:00", close="21:00", adult=0, minutes=60, wheelchair=False),
    A("Nubra", "Diskit Monastery and Hunder dunes", open="08:00", close="17:00", adult=300, minutes=240, permit=True, wheelchair=False),
    A("Pangong", "Pangong Lake", open="07:00", close="17:00", adult=0, minutes=240, permit=True, wheelchair=False),
]}

def city_of(attraction: str) -> str:
    return ATTRACTIONS[attraction]["city"]

def in_window(date: dt.date, window) -> bool:
    """window = (MM-DD, MM-DD) inclusive, may wrap around new year."""
    a, b = window
    md = date.strftime("%m-%d")
    return (a <= md <= b) if a <= b else (md >= a or md <= b)

def is_peak(date: dt.date) -> bool:
    return in_window(date, (PEAK_FROM, PEAK_TO))

def is_winter(date: dt.date) -> bool:
    return date.month in (11, 12, 1, 2, 3)
