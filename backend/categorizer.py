"""Smart expense categorization engine.
Rule-based with keyword matching — handles messy merchant names.
"""
import re

CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "swiggy", "zomato", "dominos", "mcdonald", "kfc", "burger", "pizza",
        "restaurant", "cafe", "chai", "coffee", "starbucks", "barista",
        "dunzo food", "eatfit", "box8", "faasos", "dineout", "biryani",
    ],
    "Groceries": [
        "bigbasket", "blinkit", "grofers", "zepto", "dmart", "reliance fresh",
        "more", "spencer", "amazon fresh", "swiggy instamart", "jio mart", "grocery",
    ],
    "Transport": [
        "uber", "ola", "rapido", "metro", "irctc", "indian railway", "redbus",
        "petrol", "diesel", "fuel", "iocl", "bpcl", "hpcl", "fastag", "toll",
        "parking",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "tata cliq",
        "snapdeal", "shoppers stop", "lifestyle", "pantaloon", "zara", "h&m",
        "uniqlo",
    ],
    "Entertainment": [
        "netflix", "prime video", "hotstar", "disney", "spotify", "youtube premium",
        "bookmyshow", "pvr", "inox", "sonyliv", "zee5", "jiocinema",
    ],
    "Bills & Utilities": [
        "electricity", "water bill", "gas", "airtel", "jio", "vi ", "vodafone",
        "bsnl", "recharge", "broadband", "wifi", "dth", "tata power", "bescom",
    ],
    "Rent": ["rent", "nobroker", "nestaway", "zolo", "stanza", "pg ", "hostel"],
    "Education": [
        "udemy", "coursera", "byjus", "unacademy", "vedantu", "upgrad", "scaler",
        "college", "tuition", "school fee", "book", "kindle",
    ],
    "Healthcare": [
        "apollo", "pharmeasy", "1mg", "netmeds", "medlife", "practo", "cult fit",
        "cure fit", "hospital", "clinic", "doctor", "pharmacy", "medical",
    ],
    "Investments": [
        "zerodha", "groww", "upstox", "kuvera", "coin ", "sip ", "mutual fund",
        "stock", "equity", "ppf", "nps", "etmoney",
    ],
    "Transfers": ["upi", "paytm transfer", "imps", "neft", "rtgs", "gpay", "phonepe"],
    "Travel": ["makemytrip", "goibibo", "oyo", "airbnb", "cleartrip", "yatra", "indigo", "vistara", "air india", "spicejet"],
    "Personal Care": ["salon", "spa", "urban company", "gym", "fitness"],
}

ESSENTIAL_CATEGORIES = {"Groceries", "Bills & Utilities", "Rent", "Healthcare", "Transport", "Education"}


def categorize(merchant: str, notes: str = "") -> str:
    text = f"{merchant or ''} {notes or ''}".lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    best_cat = "Other"
    best_score = 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat


def is_essential(category: str) -> bool:
    return category in ESSENTIAL_CATEGORIES
