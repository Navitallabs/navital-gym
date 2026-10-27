"""Static synthetic tables for Form Desk. Public identifier formats only; no real people, no Aadhaar numbers.
City/PIN pairs are well-known first-level PINs (public). The postal-zone table is a simplification (verify before any real-world claim)."""
ZONES = {"1": ["Delhi", "Haryana", "Punjab", "Himachal Pradesh", "Jammu and Kashmir", "Chandigarh"], "2": ["Uttar Pradesh", "Uttarakhand"],
         "3": ["Rajasthan", "Gujarat"], "4": ["Maharashtra", "Goa", "Madhya Pradesh", "Chhattisgarh"], "5": ["Andhra Pradesh", "Telangana", "Karnataka"],
         "6": ["Kerala", "Tamil Nadu", "Puducherry"], "7": ["West Bengal", "Odisha", "Assam"], "8": ["Bihar", "Jharkhand"]}
CITIES = {  # city (upper-case key) -> (display name, state, PIN)
    "NEW DELHI": ("New Delhi", "Delhi", "110001"), "MUMBAI": ("Mumbai", "Maharashtra", "400001"), "BENGALURU": ("Bengaluru", "Karnataka", "560001"),
    "CHENNAI": ("Chennai", "Tamil Nadu", "600001"), "KOLKATA": ("Kolkata", "West Bengal", "700001"), "JAIPUR": ("Jaipur", "Rajasthan", "302001"),
    "AHMEDABAD": ("Ahmedabad", "Gujarat", "380001"), "HYDERABAD": ("Hyderabad", "Telangana", "500001"), "PUNE": ("Pune", "Maharashtra", "411001"),
    "LUCKNOW": ("Lucknow", "Uttar Pradesh", "226001"), "PATNA": ("Patna", "Bihar", "800001"), "KOCHI": ("Kochi", "Kerala", "682001"),
    "THIRUVANANTHAPURAM": ("Thiruvananthapuram", "Kerala", "695001"), "CHANDIGARH": ("Chandigarh", "Chandigarh", "160017"),
}
STATE_ABBR = {"DL": "Delhi", "MH": "Maharashtra", "KA": "Karnataka", "TN": "Tamil Nadu", "WB": "West Bengal", "RJ": "Rajasthan", "GJ": "Gujarat", "TS": "Telangana",
              "UP": "Uttar Pradesh", "BR": "Bihar", "KL": "Kerala", "CH": "Chandigarh"}
PAN_PATTERN = r"^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$"
IFSC_PATTERN = r"^[A-Z]{4}0[A-Z0-9]{6}$"
MOBILE_PATTERN = r"^[6-9][0-9]{9}$"

def zone_of_state(state: str):
    for z, sts in ZONES.items():
        if state in sts:
            return z
    return None
