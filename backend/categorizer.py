"""Smart expense categorization engine.
Bank-statement-aware: strips UPI/IMPS/NEFT/POS prefixes before matching, and
falls back to 'Transfers' only when no concrete category is detected.
"""
import re

CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "swiggy", "zomato", "dominos", "mcdonald", "kfc", "burger", "pizza",
        "restaurant", "cafe", "chai", "coffee", "starbucks", "barista",
        "dunzo food", "eatfit", "box8", "faasos", "dineout", "biryani",
        "haldiram", "bikanervala", "subway", "wow momo", "chaayos",
    ],
    "Groceries": [
        "bigbasket", "blinkit", "grofers", "zepto", "dmart", "reliance fresh",
        "spencer", "amazon fresh", "instamart", "jiomart", "grocery",
        "natures basket", "more retail",
    ],
    "Transport": [
        "uber", "ola", "rapido", "metro", "irctc", "railway", "redbus",
        "petrol", "diesel", "fuel", "iocl", "bpcl", "hpcl", "fastag", "toll",
        "parking", "indian oil", "bharat petroleum", "hindustan petroleum",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "tata cliq",
        "snapdeal", "shoppers stop", "lifestyle", "pantaloon", "zara", "h&m",
        "uniqlo", "decathlon", "ikea", "urban ladder", "pepperfry",
    ],
    "Entertainment": [
        "netflix", "prime video", "hotstar", "disney", "spotify", "youtube premium",
        "bookmyshow", "pvr", "inox", "sonyliv", "zee5", "jiocinema", "jio saavn",
        "gaana", "wynk",
    ],
    "Bills & Utilities": [
        "electricity", "water bill", "gas bill", "airtel", "jio recharge", "vi postpaid",
        "vodafone", "bsnl", "recharge", "broadband", "wifi", "dth", "tata power",
        "bescom", "adani electricity", "mahadiscom", "tneb", "torrent power",
    ],
    "Rent": ["rent payment", "nobroker", "nestaway", "zolo", "stanza", "housing.com", "magicbricks"],
    "Education": [
        "udemy", "coursera", "byjus", "unacademy", "vedantu", "upgrad", "scaler",
        "college fee", "tuition", "school fee", "kindle", "testbook",
    ],
    "Healthcare": [
        "apollo", "pharmeasy", "1mg", "netmeds", "medlife", "practo", "cult fit",
        "curefit", "hospital", "clinic", "doctor", "pharmacy", "medical", "lenskart",
    ],
    "Investments": [
        "zerodha", "groww", "upstox", "kuvera", "coin ", "sip ", "mutual fund",
        "etmoney", "paytm money", "kite", "angelone",
    ],
    "Travel": [
        "makemytrip", "goibibo", "oyo", "airbnb", "cleartrip", "yatra",
        "indigo", "vistara", "air india", "spicejet", "akasa", "ixigo",
    ],
    "Personal Care": ["salon", "spa", "urban company", "gym", "fitness", "cultsport"],
    "Transfers": [
        # Explicit person-to-person / self transfers only
        "self transfer", "transfer to", "p2p", "to account", "atm withdraw",
        "cash withdraw", "self ", "wife", "husband", "mother", "father",
    ],
}

ESSENTIAL_CATEGORIES = {"Groceries", "Bills & Utilities", "Rent", "Healthcare", "Transport", "Education"}

# Bank statement remark prefixes to strip before matching
RAIL_PREFIXES = [
    "upi/", "upi-", "imps/", "imps-", "neft/", "neft-", "rtgs/", "rtgs-",
    "pos/", "pos ", "ach-", "ach/", "ecs/", "ecs-", "vps/", "billdesk/",
    "bill pay/", "billpay-", "iconnect-", "mmt/",
]


def _preprocess(text: str) -> str:
    t = (text or "").lower()
    # Replace common separators with spaces so tokens are visible
    t = re.sub(r"[/\\\-_|:*]+", " ", t)
    # Strip leftover rail words (upi, imps, neft etc.) that convey no category
    for rail in ["upi", "imps", "neft", "rtgs", "pos", "ach", "ecs", "vps", "ecom", "ref no", "refno", "inb"]:
        t = re.sub(rf"\b{rail}\b", " ", t)
    # Remove digits / long alphanumeric reference codes
    t = re.sub(r"\b[a-z0-9]{10,}\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"[^a-z ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def categorize(merchant: str, notes: str = "") -> str:
    raw = f"{merchant or ''} {notes or ''}"
    text = _preprocess(raw)
    if not text:
        # Empty/unreadable remark — default to Other (not Transfers)
        return "Other"

    best_cat, best_score = None, 0
    # First pass: skip Transfers so it never wins a tie against a real category
    for cat, kws in CATEGORY_KEYWORDS.items():
        if cat == "Transfers":
            continue
        score = sum(1 for kw in kws if kw in text)
        if score > best_score:
            best_cat, best_score = cat, score
    if best_cat:
        return best_cat

    # Last resort: explicit transfer keywords
    for kw in CATEGORY_KEYWORDS["Transfers"]:
        if kw in text:
            return "Transfers"
    return "Other"


def is_essential(category: str) -> bool:
    return category in ESSENTIAL_CATEGORIES
