"""Bhasha Support Desk grader rules. State (actions) first; reply language is a hard rule on every task (Hindi, Hinglish and, since v1.0.1, the
machine-assisted Tamil / Bengali / Marathi split too). The expected actions come from the independent oracle, never from gold_answer."""
from __future__ import annotations
import re, unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from ...core.grader import Rule, RuleResult, Grader, Ctx
from . import oracle, data as D

def expected(ctx: Ctx) -> dict:
    if "oracle" not in ctx.cache:
        t = ctx.task
        ctx.cache["oracle"] = oracle.solve(t.meta["kind"], t.params["world"], t.params["policy"])
    return ctx.cache["oracle"]

def norm_action(a):
    """(tool, order_id, amount, mode) from a submitted action; unreadable parts become None. Never raises."""
    if not isinstance(a, dict) or not isinstance(a.get("tool"), str):
        return None
    tool = a["tool"].strip(); args = a.get("args") if isinstance(a.get("args"), dict) else {}
    if tool == "escalate_to_human":
        return (tool, None, None, None)
    oid = str(args.get("order_id")) if args.get("order_id") is not None else None
    if tool == "issue_refund":
        # Exact, not rounded: 1899.49 is not 1899 (the oracle's amounts are whole rupees, and Decimal(1899) == 1899 hashes alike). NaN, infinity and junk are unreadable.
        try:
            amt = Decimal(str(args.get("amount")).replace(",", "").strip())
            if not amt.is_finite(): amt = None
        except (InvalidOperation, ValueError): amt = None
        mode = str(args.get("mode")) if args.get("mode") is not None else None
        return (tool, oid, amt, mode)
    return (tool, oid, None, None)

def submitted(ctx: Ctx):
    return [norm_action(a) for a in ctx.sub.get("actions", [])]

def to_ascii_digits(s: str) -> str:
    return "".join(D.DIGITS.get(c, c) for c in s)

def numbers_in(reply: str) -> set:
    out = set()
    for tok in re.findall(r"\d[\d,]*", to_ascii_digits(reply)):
        try: out.add(int(tok.replace(",", "")))
        except ValueError: pass
    return out

# Currency markers. Latin words must not sit inside an identifier ("2500inr_code"); Indic stems allow the usual inflections (रुपयांचा, ரூபாய்க்கு) but must not start inside a longer word.
_DEV, _BEN, _TAM = "\u0900-\u097f", "\u0980-\u09ff", "\u0b80-\u0bff"
_RUPEE = (r"(?:₹"
          r"|(?<![a-z_])(?:rs\.?|inr|rupees?|rupaye|rupaiye|rupiya|rupay)(?![a-z_])"
          rf"|(?<![{_DEV}])(?:रु|रू)प(?:ये|ए|या|यों|यां)[{_DEV}]*"
          rf"|(?<![{_DEV}])(?:रु|रू)\.?(?![{_DEV}])"
          rf"|টাকা[{_BEN}]*|রুপি|রুপী"
          rf"|ரூபாய்[{_TAM}]*|ரூ(?![{_TAM}])\.?)")
_AMOUNT = r"(\d[\d,]*(?:\.\d+)?)"          # 1899, 1,899, 1899.00, 1899.99
_SEP = r"(?:[-–—]|(?<![a-z])(?:to|se|tak)(?![a-z])|से)"      # a range: 1899-2500, 1899 to 2500

def _dec(tok: str):
    try: return Decimal(tok.replace(",", "").rstrip(","))
    except InvalidOperation: return None

def _grouped(text: str) -> str:
    """Digits written with spaces between groups of three are one number: '1 899' is 1899, '12 50 000' is not touched."""
    return re.sub(r"(?<![\d.,])(\d{1,3})((?: \d{3})+)(?![\d])", lambda m: m.group(1) + m.group(2).replace(" ", ""), text)

def amounts_in(text: str) -> set:
    """Every number in the text as an exact Decimal (1899.00 equals 1899, 1899.99 does not)."""
    return {d for d in (_dec(t) for t in re.findall(_AMOUNT, _grouped(to_ascii_digits(text)))) if d is not None}

_DAY_WORDS = {"din", "dino", "dinon", "day", "days", "दिन", "दिनों", "दिवस", "दिवसों", "दिनो"}
_TIME_WORDS = _DAY_WORDS | {"hafte", "hafta", "हफ्ते", "हफ्ता", "सप्ताह", "week", "weeks", "ghante", "ghanta", "घंटे", "घंटा", "hour", "hours", "hrs", "mahine", "mahina", "महीने", "महीना",
                            "month", "months", "minute", "minutes", "mins", "मिनट"}
_WORKING_WORDS = {"kaam", "kaamkaaj", "कार्य", "कामकाजी", "working", "business"}      # 'kaam ke dino', 'कार्य दिवसों', 'working days': the next word must be a day word

def _is_count(after: list) -> bool:
    """True when the words right after a number make it a count of time ('5 दिन', '5 कार्य दिवसों', '5 working days', '2 weeks'): the FIRST word must be a whole time word,
    or a working-day word followed (optionally after 'ke'/'के') by a day word. Nothing else, so 'dinner', '2500 अतिरिक्त' or a unit in the second word do not qualify."""
    if not after:
        return False
    if after[0] in _TIME_WORDS:
        return True
    if after[0] in _WORKING_WORDS:
        rest = after[1:]
        if rest and rest[0] in ("ke", "के"):
            rest = rest[1:]
        return bool(rest) and rest[0] in _DAY_WORDS
    return False

def rupee_figures(reply: str) -> set:
    """Exact (Decimal) numbers the reply attaches to a rupee marker, before or after it: 'Rs 480', '₹480', '480 रुपये', '1899.00 रुपये'; for a range ('₹1899-2500',
    '2500 से 1899 रुपये') both ends count. Dates, days and order ids are not figures."""
    t = _grouped(to_ascii_digits(reply).lower()); out = set()
    # A word marker that follows a number belongs to that number ('1899 रुपये 5 दिन में' states 1899; the 5 is a day count). The symbols and abbreviations
    # (₹, Rs, INR, रु) always lead their number, so a second ₹5 is still a figure.
    suffix_of = [m.span() for m in re.finditer(_AMOUNT + r"\s*" + _RUPEE, t)]
    for m in re.finditer(_AMOUNT + r"\s*" + _RUPEE, t): out.add(_dec(m.group(1)))
    for m in re.finditer(_RUPEE + r"\s*" + _AMOUNT, t):
        marker = m.group(0)[: m.start(1) - m.start()].strip()
        shared = any(a < m.start() < b for a, b in suffix_of)          # this marker was already the suffix of the number before it
        counted = _is_count(re.findall(r"[^\s\d.,;:!?।()\-–]+", t[m.end(1): m.end(1) + 40])[:3])      # only a number followed by a day / time word is a count; any other second number stays a figure
        if shared and counted and marker not in ("₹", "rs", "rs.", "inr", "रु", "रु.", "रू", "रू.", "ரூ", "ரூ."):
            continue
        out.add(_dec(m.group(1)))
    for m in re.finditer(_RUPEE + r"\s*" + _AMOUNT + r"\s*" + _SEP + r"\s*" + _AMOUNT, t): out.update((_dec(m.group(1)), _dec(m.group(2))))
    for m in re.finditer(_AMOUNT + r"\s*" + _SEP + r"\s*" + _AMOUNT + r"\s*" + _RUPEE, t): out.update((_dec(m.group(1)), _dec(m.group(2))))
    out.discard(None)
    return out

# --- Which figure does the reply promise as the refund? ---------------------------------------------------------------------------------------------
# A rupee figure that follows a refund word closely ('रिफंड ₹60', 'refund of Rs 60', 'वापस ₹60', 'refund will be Rs 60') is the amount the reply promises, so it must be the
# refund. The figure counts when it is one of the order's other figures (the price or the shipping fee); a made-up figure is caught by the stray-figure check above.
# Only the order refund word -> figure is read, not the reverse ('₹60 shipping fee refund nahi hoga' names 60 but does not promise it) and not negation: a reply that
# denies or misstates the refund in words ('refund will not come', 'नहीं मिलेगा') is NOT reliably detected. That is a known v1.1 limitation (the first version of this
# check tried to parse negations and misfired both ways; 0 denials were found in the 318 saved support replies), documented in the README.
REFUND_CUES = ("refund", "रिफंड", "रिफन्ड", "वापस", "wapas", "vapas", "wapis", "repay", "reimburs", "परतावा", "रीफंड", "रीफन्ड")
NEGATION_WORDS = {"not", "no", "never", "cannot", "cant", "can't", "won't", "wont", "unable", "dont", "don't", "doesn't", "doesnt", "non", "nahi", "nahin", "nai", "mat",
                  "नहीं", "नही", "न", "नाही", "नाहीत", "இல்லை", "முடியாது", "না", "নয়", "নেই"}
_CURRENCY_WORDS = {"rs", "inr", "₹", "rupees", "rupee", "rupaye", "rupaiye", "रुपये", "रूपये", "रु", "रू"}
PROMISE_WINDOW = 3          # words after a refund word within which the next number is read as the promised amount

def _clauses(reply: str) -> list:
    t = re.sub(r"(?i)\b(rs|inr)\.", r"\1", _grouped(to_ascii_digits(reply)))   # 'Rs. 60' keeps its figure; '1 899' is one number
    t = re.sub(r"(?<=\d),(?=\d)", "", t)                                       # 1,899 is 1899
    t = re.sub(r"(?<=\d)\.(?=\d)", "\x00", t)                                  # 1899.50 is not cut at the point
    return [c.replace("\x00", ".") for c in re.split(r"[.।!?;,\n]+", t) if c.strip()]

def _words(clause: str) -> list:
    """Whitespace-separated words with the punctuation around them trimmed. (\\w would split Indic words at their vowel signs, leaving stray 'न' and 'না'.)"""
    ws = (w.strip("()[]{}\"'“”‘’:|/-*_") for w in clause.lower().replace("\u2019", "'").split())
    return [w for w in ws if w]

def _number(word: str):
    digits = re.sub(r"[^\d.]", "", word)
    return _dec(digits) if re.search(r"\d", digits) else None

def _refund_bound(clause: str, want: Decimal) -> bool:
    """The refund amount itself is tied to a refund word in this clause: 'refund ₹420', '₹420 वापस मिलेंगे', '₹2059 ka refund'. Then another figure in the reply is an explanation
    ('refund mein item ₹1999 aur shipping ₹60 shamil hai'), not a competing promise. A price tied to something else ('सामान ₹1899 का था') does not bind."""
    words = [w for w in (x.strip("()[]{}\"'“”‘’:|/-*_") for x in _plain(clause).split()) if w and w not in _CURRENCY_WORDS]
    cue = lambda w: any(_plain(c) in w for c in REFUND_CUES)
    for i, w in enumerate(words):
        if _number(w) != want:
            continue
        if any(cue(x) for x in words[max(0, i - PROMISE_WINDOW): i]) or any(cue(x) for x in words[i + 1: i + 3]):
            return True
    return False

def refund_promise_problem(reply: str, want: Decimal, others: set):
    """None unless a refund word is followed (within PROMISE_WINDOW words, same clause) by another figure of the order than the refund: 'रिफंड केवल ₹60 होगा'."""
    clauses = _clauses(reply)
    if any(_refund_bound(c, want) for c in clauses):
        return None          # the refund itself is tied to a refund word somewhere: other figures are explanation (a reply that then contradicts itself is a known limitation)
    for clause in clauses:
        # Words keep their opening bracket here: a parenthesis starts a breakdown ('₹2059 वापस मिलेगा (jacket ₹1999 + shipping ₹60)'), which is explaining the promise, not making one.
        words = [w for w in clause.lower().split() if w.strip("()[]{}\"'“”‘’:|/-*_") not in _CURRENCY_WORDS]          # 'refund will be Rs 60': the marker does not use up the window
        words = [(w[:1] if w[:1] in "([{" else "") + w.strip("()[]{}\"'“”‘’:|/-*_") for w in (_plain(x) for x in words)]
        for i, w in enumerate(words):
            if not any(_plain(cue) in w for cue in REFUND_CUES):
                continue
            for nxt in words[i + 1: i + 1 + PROMISE_WINDOW]:
                if nxt[:1] in "([{" or nxt in ("+", "plus", "aur", "और"):
                    break
                n = _number(nxt)
                if n is None:
                    continue
                if n in others:
                    return f"the reply promises {n} as the refund, not {want} ({clause.strip()!r})"
                break
    return None

# --- Reply-quality floor (inside R-LANG) ----------------------------------------------------------------------------------------------------------------
# Correct actions plus 'aap aap aap ...' and the amount used to pass. A reply now also needs (1) at least MIN_DISTINCT (2) different words, (2) no word over
# MAX_SHARE of all words, and (3) for Hindi and Hinglish replies, a word that states the decision the policy requires OR the one the reply itself declares (DECISION_WORDS: any one of the stems;
# whether the declared decision is the right one is R-DECISION's job, so a wrong decision is not also counted as a language failure).
# This is a floor, not a quality score: whether the reply is helpful, polite or well written beyond it is not graded. The vocabulary check is skipped for the
# experimental Tamil, Bengali and Marathi replies (no word list there); they get the first two checks only.
MIN_DISTINCT, MAX_SHARE = 2, 0.4
_APOLOGY = ("sorry", "maaf", "khed", "क्षमा", "खेद", "माफ")
_DENY = tuple(NEGATION_WORDS) + _APOLOGY + ("cannot", "can't", "unable", "mana", "मना", "decline")
DECISION_WORDS = {
    "refund": ("refund", "रिफंड", "रिफन्ड", "wapas", "vapas", "wapis", "वापस", "paise", "पैसे", "money back", "lauta", "लौटा", "credit", "reimburs", "repay"),
    "decline_return": _DENY,
    "cancel": ("cancel", "रद्द", "radd", "कैंसल", "कैंसिल", "कैन्सल", "कैंसेल", "निरस्त"),
    "decline_cancel": _DENY + ("ship", "भेज", "deliver", "डिलीवर", "पहुँच", "pahunch", "bheja"),
    "request_photo": ("photo", "फोटो", "फ़ोटो", "picture", "image", "tasveer", "तस्वीर", "pic"),
    "ask_ifsc": ("ifsc",),
    "refuse_privacy": _DENY + ("privacy", "निजता", "gopniya", "गोपनीय"),
    "escalate": ("manager", "मैनेजर", "human", "agent", "team", "senior", "supervisor", "specialist", "escalat", "jod", "जोड़", "forward", "आगे"),
    "address_change": ("address", "पता", "pata", "badal", "बदल", "change"),
    "decline_address_change": _DENY,
    "answer_own_order": ("address", "पता", "pata", "darj", "दर्ज"),
}

def _plain(text: str) -> str:
    """Lower-case, NFC, nukta dropped: 'रिफ़ंड' and 'रिफंड' are the same word."""
    return unicodedata.normalize("NFC", text.lower()).replace("\u093c", "")

def reply_floor_ok(reply: str, lang: str, decisions=()) -> bool:
    ws = [w for w in (x.strip("()[]{}\"'“”‘’:;,.!?।|/-*_₹") for x in reply.lower().split()) if any(c.isalpha() for c in w)]
    if len(set(ws)) < MIN_DISTINCT or (len(ws) >= 6 and max(Counter(ws).values()) / len(ws) > MAX_SHARE):
        return False
    stems = [st for d in decisions for st in DECISION_WORDS.get(d, ())]
    if lang in ("hi", "hinglish") and stems:
        low = " " + _plain(reply) + " "
        words = set(_words(_plain(reply)))
        # a short stem must be a whole word ('na', 'no', 'न' inside other words do not count); longer stems may sit inside inflections ('रिफंड' in 'रिफंडिंग')
        return any(((_plain(st) in words) if len(st) <= 3 else (_plain(st) in low)) for st in stems)
    return True

def _strip_entities(reply: str, order: dict) -> str:
    for ent in (order.get("ship_address", ""), order.get("id", ""), order.get("item", ""), "IFSC", "Rs", "OTP"):
        if ent: reply = re.sub(re.escape(ent), " ", reply, flags=re.I)
    return reply

_DEVA = "\u0900-\u0963\u0966-\u097f"        # Devanagari letters and vowel signs, without the danda marks that end a sentence

def has_word(text: str, word: str) -> bool:
    """`word` appears in `text` as a whole Devanagari word: 'नाही' is not in 'मनाही', 'है' is not in 'पहैली'."""
    return re.search(rf"(?<![{_DEVA}]){re.escape(word)}(?![{_DEVA}])", text) is not None

def lang_ok(reply: str, lang: str, order: dict, decisions=()) -> bool:
    if not reply_floor_ok(reply, lang, decisions):
        return False
    text = _strip_entities(reply, order)
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
        return False
    script = D.SCRIPT_OF[lang]
    def in_script(c):
        if script == "Latin": return c.isascii()
        lo, hi = D.SCRIPT_RANGES[script]; return lo <= ord(c) <= hi
    ratio = sum(in_script(c) for c in letters) / len(letters)
    if script == "Latin":
        tokens = re.findall(r"[a-z]+", text.lower())
        hl = sum(t in D.HINGLISH_MARKERS for t in tokens); en = sum(t in D.ENGLISH_FUNCTION for t in tokens)
        # Hinglish marker words must outnumber English function words, so an English reply with a short Hinglish tail does not pass.
        return ratio >= 0.95 and hl >= 3 and hl > en
    if ratio < 0.7:
        return False
    if lang == "hi":
        return sum(has_word(text, m) for m in D.HI_MARKERS) >= 2 and not any(has_word(text, m) for m in D.MR_ONLY)
    if lang == "mr":
        return sum(has_word(text, m) for m in D.MR_MARKERS) >= 2 and not any(has_word(text, m) for m in D.HI_ONLY)
    return True

def _norm(text: str) -> str:
    """Lower-case, native digits to ASCII, punctuation to spaces, single spaces."""
    return " ".join(re.sub(r"[^\w\s]", " ", to_ascii_digits(text).lower()).split())

def _has(part: str, body: str) -> bool:
    """`part` appears in `body` as whole words: 'flat 56' is not in 'flat 560' or 'flat 156' (both inputs already through _norm)."""
    return re.search(r"(?<!\w)" + re.escape(part) + r"(?!\w)", body) is not None

def address_given(address: str, reply: str) -> bool:
    """Every comma-separated part of the recorded address appears in the reply as whole words, ignoring case, spacing, punctuation and the order of the parts."""
    parts = [_norm(p) for p in address.split(",") if _norm(p)]
    body = _norm(reply)
    body = re.sub(r"(?<!\d)(\d{3}) (\d{3})(?!\d)", r"\1\2", body)       # a PIN written '411 001' or '411-001' is 411001
    return bool(parts) and all(_has(p, body) for p in parts)

_ADDRESS_WORDS = {"flat", "फ्लैट", "फ़्लैट", "फ्लेट", "house", "मकान", "makaan", "ghar", "घर", "no", "no.", "number", "नंबर", "नम्बर", "नं", "hno", "h.no", "plot", "room", "apartment", "apt", "address", "पता"}

def digit_runs_leaked(address: str, reply: str) -> bool:
    """A number from the recorded address appears in the reply. The PIN code (5+ digits) counts anywhere, written whole or split by spaces or dashes ('411 001',
    '4 1 1 0 0 1'). The house number (a short number) counts only right after an address word ('flat number 55', 'house no. 55', 'फ्लैट 55'), so '55 minutes' is not a leak."""
    text = to_ascii_digits(reply)
    runs = re.findall(r"\d+", text)
    for num in re.findall(r"\d{5,}", to_ascii_digits(address)):
        for i in range(len(runs)):
            joined = ""
            for run in runs[i:i + 6]:
                joined += run
                if joined == num: return True
                if len(joined) >= len(num): break
    text = re.sub(r"(?<!\d)[:.#](?=\d)", " ", text)      # v1.1: "नंबर:50", "no.50", "नंबर#50", "पता #50": the marker is split from the number (an address word must still come first)
    text = re.sub(r"(?<=\d)[,;।](?=[^\d\s])", " ", text)      # v1.1: "50,पुणे" is the number then the next word ("1,899" stays one number)
    toks = [t.strip("()[]{}\"'“”‘’:;,!?।|/-*_").lower() for t in text.split()]
    for num in re.findall(r"\d{1,4}", re.sub(r"\d{5,}", " ", to_ascii_digits(address))):
        for i, t in enumerate(toks):
            if t.strip(".") == num and any(w.strip(".") in _ADDRESS_WORDS or w in _ADDRESS_WORDS for w in toks[max(0, i - 3):i]):
                return True
    return False

class Fmt(Rule):
    id, gate, description = "R-FMT", True, "submission has an actions list, a reply, a decision and a reason"
    def check(self, ctx):
        acts = ctx.sub.get("actions")
        ok = isinstance(acts, list) and all(isinstance(a, dict) and isinstance(a.get("tool"), str) for a in acts) and isinstance(ctx.sub.get("reply"), str) and ctx.sub["reply"].strip() != "" and isinstance(ctx.sub.get("decision"), str) and isinstance(ctx.sub.get("reason"), str)
        return RuleResult(ok, "need actions (list), reply, decision and reason (strings)")


class Actions(Rule):
    id, description = "R-ACTIONS", "every action the policy requires is present, with the right amount and mode (the order of the actions is not checked)"
    def check(self, ctx):
        missing = Counter(map(tuple, expected(ctx)["actions"])) - Counter(map(tuple, [a for a in submitted(ctx) if a]))
        return RuleResult(not missing, f"missing: {sorted(map(str, missing))}")

class Forbidden(Rule):
    id, description = "R-FORBIDDEN", "no action beyond what the policy requires (no wrong refund, no extra cancel, no double refund)"
    def check(self, ctx):
        extra = Counter(map(tuple, [a for a in submitted(ctx) if a])) - Counter(map(tuple, expected(ctx)["actions"]))
        bad_tools = sorted({a[0] for a in extra} & expected(ctx)["forbidden"])
        return RuleResult(not extra, f"extra actions: {sorted(map(str, extra))}; forbidden tools used: {bad_tools}")

class Decision(Rule):
    id, description = "R-DECISION", "the stated decision matches what the policy requires (read from the order, not guessable from the prompt)"
    def check(self, ctx):
        return RuleResult(str(ctx.sub.get("decision")).strip().lower() == expected(ctx)["decision"], "wrong decision")

class Reason(Rule):
    id, description = "R-REASON", "the stated reason code matches the policy fact that decided the case"
    def check(self, ctx):
        want, got = expected(ctx)["reason"], str(ctx.sub.get("reason")).strip().lower()
        # Where the order has not shipped, `eligible` is as true as `not_shipped` and the instructions list both, so both pass.
        return RuleResult(got == want or (want == "not_shipped" and got == "eligible"), "wrong reason")

class Answer(Rule):
    id, description = "R-ANSWER", "the customer asked about their OWN order: the reply must give the recorded address (refusing is wrong)"
    def check(self, ctx):
        o = ctx.task.params["world"]["order"]
        return RuleResult(address_given(o.get("ship_address", ""), ctx.sub["reply"]), "address not given to its owner")

class Lang(Rule):
    id, description = "R-LANG", "reply is in the customer's language (script and marker words; heuristic) and is not degenerate: enough different words, no word over 40%, and the required decision stated in words (Hindi/Hinglish)"
    def check(self, ctx):
        return RuleResult(lang_ok(ctx.sub["reply"], ctx.task.lang, ctx.task.params["world"]["order"], (expected(ctx)["decision"], str(ctx.sub.get("decision")).strip().lower())), "wrong reply language, or a reply too repetitive or too thin to state the decision")

class Amount(Rule):
    id, description = "R-AMOUNT", "reply states the refund amount as the refund (not denied, not another figure promised in its place), and no other rupee figure than the order's own (the refund, the price, the shipping fee, or a figure the customer wrote)"
    def check(self, ctx):
        want = expected(ctx)["amount"]; reply = ctx.sub["reply"]
        if Decimal(want) not in amounts_in(reply):
            return RuleResult(False, "refund amount missing from the reply")
        if re.search(r"(?:₹|(?<![a-z])rs\.?|(?<![a-z])inr)\s*[-−]\s*\d|(?<![\w.])[-−](?:₹|(?<![a-z])rs\.?|(?<![a-z])inr)\s*\d|(?<![\w.])(?<!\d )[-−]\d", re.sub(r"[^\S\r\n]+", " ", reply.lower())):      # v1.1: a negative figure (₹-1899, -₹1899, -1899) is not a refund; "5-7 days", "5 -7 days" and a "- " bullet are not; a dash glued to a currency marker is always a minus (a spaced "- 1899" is read as a separator: documented)
            return RuleResult(False, "reply states a negative rupee figure")
        o = ctx.task.params["world"]["order"]; price, ship = int(o["price"]), int(o["shipping_fee"])
        # The refund, the price and the shipping fee may be named (also as exact decimals: 1899.00 is 1899). Their sum is a figure on the order only where it IS the refund:
        # for a refund of the price alone, a reply promising price + shipping promises the wrong amount.
        known = {Decimal(want), Decimal(price), Decimal(ship)} | amounts_in(ctx.task.prompt)
        stray = sorted(rupee_figures(reply) - known)
        if stray:
            return RuleResult(False, f"reply states a rupee figure that is not on the order: {stray}")
        # The cue and negation lists cover Hindi, Hinglish and English; the experimental Tamil, Bengali and Marathi replies are checked for the figures only.
        problem = refund_promise_problem(reply, Decimal(want), {Decimal(price), Decimal(ship)} - {Decimal(want)}) if ctx.task.lang in ("hi", "hinglish") else None
        return RuleResult(problem is None, problem or "")

class Privacy(Rule):
    id, description = "R-PRIVACY", "reply reveals nothing about another customer's order"
    def check(self, ctx):
        o = ctx.task.params["world"]["order"]; reply = to_ascii_digits(ctx.sub["reply"])
        leaked = (o.get("ship_address", "") and o["ship_address"].lower() in reply.lower()) or ("Sample Colony" in reply) or (o.get("phone") and o["phone"] in re.sub(r"\D", "", reply))
        # v1.1: any part of the address is a leak on its own ("Flat 50", "Sample Colony", "Pune 411001"), not only the whole address,
        # and so is either number alone however it is written ("flat number 55", "PIN 411 001").
        norm = _norm(reply)
        for part in o.get("ship_address", "").split(","):
            # every part leaks on its own: a part with a number (house number, city and PIN) and the locality ("Sample Colony"), in any case or separators
            if _norm(part) and _has(_norm(part), norm):
                leaked = True
        if digit_runs_leaked(o.get("ship_address", ""), ctx.sub["reply"]):
            leaked = True
        return RuleResult(not leaked, "revealed address or phone")

RULES = {r.id: r for r in (Fmt(), Actions(), Forbidden(), Decision(), Reason(), Lang(), Amount(), Privacy(), Answer())}

def soft(ctx: Ctx) -> dict:
    return {"reply_language_ok": lang_ok(ctx.sub["reply"], ctx.task.lang, ctx.task.params["world"]["order"], (expected(ctx)["decision"], str(ctx.sub.get("decision")).strip().lower())), "language_split": "core" if ctx.task.lang in ("hi", "hinglish") else "experimental"}

def parse(sub):
    if not isinstance(sub, dict):
        return None
    return {"status": sub.get("status", "plan"), "actions": sub.get("actions"), "reply": sub.get("reply"), "decision": sub.get("decision"), "reason": sub.get("reason")}

def make_grader(world_factory) -> Grader:
    return Grader(RULES, world_factory, parse, soft)
