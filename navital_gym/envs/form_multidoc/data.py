"""Static synthetic tables for Form Desk: hard. Public identifier formats only; no real people, no Aadhaar numbers. Simplified env tables, not live systems."""
ZONES = {"1": ["Delhi", "Haryana", "Punjab", "Himachal Pradesh", "Jammu and Kashmir", "Chandigarh"], "2": ["Uttar Pradesh", "Uttarakhand"], "3": ["Rajasthan", "Gujarat"],
         "4": ["Maharashtra", "Goa", "Madhya Pradesh", "Chhattisgarh"], "5": ["Andhra Pradesh", "Telangana", "Karnataka"], "6": ["Kerala", "Tamil Nadu", "Puducherry"],
         "7": ["West Bengal", "Odisha", "Assam"], "8": ["Bihar", "Jharkhand"]}
BANKS = {"HDFC": "HDFC Bank", "SBIN": "State Bank of India", "ICIC": "ICICI Bank", "UTIB": "Axis Bank", "KKBK": "Kotak Mahindra Bank", "PUNB": "Punjab National Bank"}
HOLDER = {"Individual": "P", "Company": "C", "Firm": "F", "Trust": "T"}
PAN_PATTERN = r"^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$"
IFSC_PATTERN = r"^[A-Z]{4}0[A-Z0-9]{6}$"
HOLDER_TYPES = "ABCFGHLJPT"
TO_DIGIT = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"}   # OCR look-alikes, letter -> digit
TO_LETTER = {v: k for k, v in TO_DIGIT.items()}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
