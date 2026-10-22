"""Generated websites for testing agents in 'unknown territory'.

8 archetypes (dev: flights, weather, library, shop | held-out: jobs, restaurants, stocks, wiki). Every site gets a random *skin*
(label vocabulary, label placement, result layout, link style, value formats). The held-out ("test") skins use vocabulary and
layouts that dev skins never use. Noise levels are cumulative:
  L0 clean | L1 cookie banner + delayed promo popup + decoy search/newsletter forms + sponsored links
  L2 + flaky 503s, random delays, shuffled rows, sponsored rows | L3 + JS-rendered results, pagination (3 rows/page)
Gold answers come straight from the generated data, never from any agent."""
from __future__ import annotations

import html
import json
import zlib
import random
import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote, urlparse

CITIES = ["Paris", "Berlin", "Tokyo", "Madrid", "Lisbon", "Oslo", "Cairo", "Lima", "Seoul", "Dublin", "Vienna", "Prague", "Rome", "Athens", "Nairobi", "Mumbai"]
AIRLINES = ["Delta", "Lufthansa", "Emirates", "Air France", "KLM", "Qantas", "Iberia", "Finnair", "Turkish", "Ryanair", "JetBlue", "ANA"]
FIRST = ["Alice", "Bruno", "Carla", "Daniel", "Elena", "Farid", "Grace", "Hugo", "Isla", "Jonas", "Kira", "Leo", "Maya", "Noah", "Olga", "Pavel"]
LAST = ["Adams", "Brandt", "Costa", "Dubois", "Eriksen", "Farouk", "Gomez", "Holm", "Ivanov", "Jensen", "Kaur", "Lopez", "Meyer", "Novak", "Ortiz", "Park"]
ADJ = ["Silent", "Golden", "Hidden", "Broken", "Distant", "Crimson", "Ancient", "Fragile", "Wandering", "Electric", "Hollow", "Northern"]
NOUN = ["Harbor", "Garden", "Orchard", "Compass", "Archive", "Lantern", "River", "Signal", "Meadow", "Fortress", "Atlas", "Voyage"]
CATS = ["Laptops", "Cameras", "Headphones", "Monitors", "Keyboards", "Tablets"]
BRANDS = ["Aria", "Nova", "Helix", "Orbit", "Vertex", "Pulse", "Zenith", "Quark"]
JOBS = ["Data Engineer", "Backend Developer", "Product Designer", "Site Reliability Engineer", "QA Analyst", "ML Engineer", "DevOps Engineer", "Security Analyst"]
COMPANIES = ["Globex", "Initech", "Umbrella", "Hooli", "Soylent", "Wonka", "Stark Labs", "Acme Corp", "Cyberdyne", "Tyrell"]
CUISINES = ["Italian", "Thai", "Mexican", "Indian", "Japanese", "French", "Greek", "Korean"]
RESTO_A = ["Casa", "Golden", "Little", "Blue", "Royal", "Old", "Happy", "Spice"]
RESTO_B = ["Luna", "Wok", "Bistro", "Garden", "Table", "Kitchen", "House", "Corner"]
COUNTRIES = ["Peru", "Norway", "Kenya", "Vietnam", "Chile", "Portugal", "Egypt", "Canada", "Iceland", "Nepal", "Morocco", "Ghana"]
CAPITALS = ["Lima", "Oslo", "Nairobi", "Hanoi", "Santiago", "Lisbon", "Cairo", "Ottawa", "Reykjavik", "Kathmandu", "Rabat", "Accra"]
CURRENCIES = ["Sol", "Krone", "Shilling", "Dong", "Peso", "Euro", "Pound", "Dollar", "Krona", "Rupee", "Dirham", "Cedi"]
BRAND_SITE = ["Skyline", "Orbit", "Meridian", "Beacon", "Atlas", "Harbor", "Summit", "Pioneer", "Lumen", "Nimbus"]

# vocabulary: 6 synonyms per concept. dev skins use [0:3], held-out test skins use [3:6]
V = {
    "origin": ["From", "Origin", "Departing from", "Leaving", "Starting city", "Depart city"],
    "destination": ["To", "Destination", "Arriving at", "Going to", "End city", "Arrive city"],
    "date": ["Date", "Departure date", "When", "Travel date", "Day", "Flight day"],
    "city": ["City", "Location", "Town", "Place", "Where", "Area"],
    "title_q": ["Title", "Book title", "Search books", "Find a book", "Name of work", "Book"],
    "term": ["Search", "Search term", "Topic", "Look up", "Article", "Query"],
    "ticker": ["Ticker", "Symbol", "Stock symbol", "Quote", "Code", "Security"],
    "keyword": ["Keywords", "Job title", "Role", "Position", "What", "Search jobs"],
    "cuisine": ["Cuisine", "Food type", "Kind of food", "Style", "Craving", "Type"],
    "airline": ["Airline", "Carrier", "Operator", "Flight by", "Company", "Line"],
    "depart": ["Departs", "Departure", "Leaves", "Time", "Takeoff", "STD"],
    "price": ["Price", "Fare", "Cost", "Amount", "Rate", "Total"],
    "temperature": ["Temperature", "Temp", "Now", "Reading", "Degrees", "Air"],
    "humidity": ["Humidity", "Relative humidity", "Moisture", "Dampness", "RH", "Mugginess"],
    "wind": ["Wind", "Wind speed", "Breeze", "Gusts", "Air speed", "Windiness"],
    "conditions": ["Conditions", "Sky", "Outlook", "Weather", "Skies", "State"],
    "title": ["Title", "Book", "Name", "Work", "Item", "Entry"],
    "author": ["Author", "Writer", "By", "Creator", "Penned by", "Written by"],
    "year": ["Year", "Published", "Date", "Released", "Pub. year", "Edition year"],
    "shelf": ["Shelf", "Location", "Call number", "Where", "Stack", "Aisle"],
    "status": ["Status", "Availability", "Available?", "State", "Loan status", "Copy status"],
    "isbn": ["ISBN", "Identifier", "Code", "Catalog no", "Book id", "Barcode"],
    "product": ["Product", "Name", "Item", "Model", "Article", "Listing"],
    "stock": ["In stock", "Stock", "Units", "Inventory", "On hand", "Quantity"],
    "sku": ["SKU", "Code", "Part no", "Item no", "Ref", "Barcode"],
    "company": ["Company", "Employer", "Organisation", "Firm", "Hiring", "Org"],
    "salary": ["Salary", "Pay", "Compensation", "Wage", "Package", "Earnings"],
    "jobtitle": ["Title", "Position", "Role", "Job", "Opening", "Vacancy"],
    "rating": ["Rating", "Score", "Stars", "Reviews", "Grade", "Rank"],
    "phone": ["Phone", "Telephone", "Call", "Contact number", "Tel", "Reservations"],
    "restoname": ["Name", "Restaurant", "Place", "Venue", "Eatery", "Spot"],
    "change": ["Change", "% Change", "Move", "Delta", "Daily move", "Variation"],
    "volume": ["Volume", "Shares traded", "Turnover", "Vol.", "Traded", "Liquidity"],
    "capital": ["Capital", "Capital city", "Seat of government", "Main city", "Administrative centre", "Metropolis"],
    "population": ["Population", "Inhabitants", "People", "Residents", "Headcount", "Demographic"],
    "currency": ["Currency", "Money", "Legal tender", "Tender", "Coinage", "Unit"],
    # "twin" columns: same value shape as a wanted column, different meaning
    "tax": ["Taxes", "Fees", "Surcharge", "Levy", "Duty", "Charges"],
    "bonus": ["Bonus", "Extra pay", "Signing bonus", "Perks", "Stipend", "Incentive"],
    "high": ["Day high", "High", "Peak", "Session high", "Top", "Ceiling"],
    "feels": ["Feels like", "Apparent", "Real feel", "Perceived", "Wind chill", "Heat index"],
    "largest": ["Largest city", "Biggest city", "Major city", "Top city", "Chief port", "Commercial hub"],
}

# shape of each gold key (used by the judge; agents never see this)
SHAPE = {"airline": "text", "depart": "time", "price": "money", "temperature": "temp", "humidity": "percent", "wind": "text", "conditions": "text",
         "title": "text", "author": "text", "year": "int", "shelf": "code", "status": "text", "isbn": "code", "product": "text", "stock": "int", "sku": "code",
         "company": "text", "salary": "money", "jobtitle": "text", "rating": "rating", "phone": "phone", "restoname": "text", "change": "percent",
         "volume": "int", "capital": "text", "population": "int", "currency": "text",
         "tax": "money", "bonus": "money", "high": "money", "feels": "temp", "largest": "text"}

FMT = {"money": ["${v}", "{v} USD", "USD {v}.00", "€{v}"], "time": ["{hh:02d}:{mm:02d}", "{h12}:{mm:02d} {ap}"], "percent": ["{v}%", "{v} %"],
       "temp": ["{v}°C", "{v} °C", "{v}°"], "int": ["{v}", "{v:,}"], "rating": ["{v}", "{v}/5", "★ {v}"], "phone": ["+1-555-{v}", "555-{v}"]}


def fmt(shape: str, raw, idx: int) -> str:
    if shape in FMT:
        f = FMT[shape][idx % len(FMT[shape])]
        if shape == "time":
            hh, mm = raw
            return f.format(hh=hh, mm=mm, h12=(hh % 12) or 12, ap="AM" if hh < 12 else "PM")
        return f.format(v=raw)
    return str(raw)


def numc(x) -> str:
    f = float(x)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def canon_raw(shape: str, raw) -> str:
    if shape == "time":
        return str(raw[0] * 60 + raw[1])
    if shape in ("money", "percent", "temp", "int", "rating"):
        return numc(raw)
    if shape == "phone":
        return re.sub(r"\D", "", str(raw))[-4:]
    return str(raw).strip().lower()


def canon_disp(shape: str, text: str) -> str:
    t = str(text)
    if shape == "time":
        m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", t, re.I)
        if not m:
            return ""
        hh, mm = int(m.group(1)), int(m.group(2))
        if m.group(3):
            hh = hh % 12 + (12 if m.group(3).upper() == "PM" else 0)
        return str(hh * 60 + mm)
    if shape in ("money", "percent", "temp", "int", "rating"):
        m = re.search(r"-?\d[\d,]*\.?\d*", t)
        return numc(m.group(0).replace(",", "")) if m else ""
    if shape == "phone":
        return re.sub(r"\D", "", t)[-4:]
    return t.strip().lower()


@dataclass
class Skin:
    split: str                       # dev | test
    vidx: list                       # per-concept synonym index
    label_style: str                 # for | wrap | span | placeholder | aria
    name_style: str                  # meaningful | opaque
    layout: str                      # table | cards | list | dl
    link_style: str                  # text | icon
    formats: dict
    date_widget: str                 # date | text
    submit: str
    order_swap: bool


def make_skin(rng: random.Random, split: str) -> Skin:
    lo = 0 if split == "dev" else 3
    return Skin(split, [lo + rng.randrange(3) for _ in range(8)] and {}, "for", "meaningful", "table", "text", {}, "date", "Search", False)


@dataclass
class Task:
    tid: str
    site_id: str
    arch: str
    split: str
    goal: list            # [canonical goal, synonym goal]
    have: dict
    want: list            # [canonical want names, synonym want names]
    want_keys: list       # gold keys aligned with want
    gold: list            # list of {key: canon value}
    start: str
    meta: dict = field(default_factory=dict)


class Site:
    def __init__(self, site_id: str, arch: str, split: str, seed: int, n_tasks: int = 3):
        self.id, self.arch, self.split = site_id, arch, split
        self.host = f"{site_id}.test"
        r = random.Random(f"site-{seed}-{site_id}")
        self.rng = r
        lo = 0 if split == "dev" else 3
        self.vidx: dict[str, int] = {}
        for k in V:
            self.vidx[k] = lo + r.randrange(3)
        self.brand = r.choice(BRAND_SITE) + " " + r.choice(["Hub", "Net", "Place", "Zone", "Point"])
        self.label_style = r.choice(["for", "wrap", "span"] if split == "dev" else ["placeholder", "aria", "span", "wrap"])
        self.name_style = r.choice(["meaningful", "opaque"])
        self.layout = r.choice(["table", "cards", "list"] if split == "dev" else ["dl", "cards", "list"])
        self.link_style = "text" if split == "dev" else r.choice(["icon", "text"])
        self.fmt_idx = {s: r.randrange(4) for s in FMT}
        self.date_widget = "date" if split == "dev" else r.choice(["text", "date"])
        self.submit = r.choice(["Search", "Go", "Find", "Show results"]) if split == "dev" else r.choice(["Let's go", "Submit", "Look up", "→"])
        self.swap = r.random() < 0.15           # swap the two city selects on flights
        self.twin = r.random() < 0.6                 # a second column with the same value shape as a wanted one
        self.twin_first = r.random() < 0.5
        self.next_label = r.choice(["Next", "Next ›", "More results"]) if split == "dev" else r.choice(["›", "Older", "Load more"])
        self.build(r)
        self.tasks = self.make_tasks(r, n_tasks)

    # ------------------------------------------------------------------ data
    def lab(self, key: str) -> str:
        return V[key][self.vidx[key]]

    def build(self, r: random.Random):
        a = self.arch
        if a == "flights":
            self.cities = r.sample(CITIES, 8)
            self.al = r.sample(AIRLINES, 6)
            self.flights = []
            combos = set()
            while len(combos) < 5:
                o, d = r.sample(self.cities, 2)
                combos.add((o, d, f"2026-11-{r.randint(1, 20):02d}"))
            for (o, d, dt) in sorted(combos):
                for _ in range(r.randint(4, 6)):
                    self.flights.append({"origin": o, "destination": d, "date": dt, "airline": r.choice(self.al), "depart": (r.randint(5, 22), r.choice([0, 15, 30, 45])),
                                         "price": r.randint(90, 980)})
        elif a == "weather":
            self.cities = r.sample(CITIES, 8)
            self.rows = {c: {"city": c, "temperature": r.randint(-5, 38), "humidity": r.randint(20, 95), "wind": f"{r.randint(3, 40)} km/h",
                             "conditions": r.choice(["Sunny", "Cloudy", "Rain", "Windy", "Fog", "Clear"])} for c in self.cities}
        elif a == "library":
            self.books = []
            used = set()
            while len(self.books) < 12:
                t = f"The {r.choice(ADJ)} {r.choice(NOUN)}"
                if t in used:
                    continue
                used.add(t)
                self.books.append({"id": f"b{len(self.books)}", "title": t, "author": f"{r.choice(FIRST)} {r.choice(LAST)}", "year": r.randint(1950, 2024),
                                   "isbn": f"978{r.randint(10**6, 10**7 - 1)}", "shelf": f"{r.choice('ABCDEF')}-{r.randint(1, 40)}", "status": r.choice(["Available", "Checked out", "On hold"])})
                if r.random() < 0.5:
                    self.books.append({"id": f"b{len(self.books)}", "title": t + " II", "author": f"{r.choice(FIRST)} {r.choice(LAST)}", "year": r.randint(1950, 2024),
                                       "isbn": f"978{r.randint(10**6, 10**7 - 1)}", "shelf": f"{r.choice('ABCDEF')}-{r.randint(1, 40)}", "status": r.choice(["Available", "Checked out"])})
        elif a == "shop":
            self.cats = r.sample(CATS, 4)
            self.products = []
            for c in self.cats:
                for _ in range(5):
                    self.products.append({"id": f"p{len(self.products)}", "category": c, "product": f"{r.choice(BRANDS)} {r.choice('XZRQ')}{r.randint(100, 900)}",
                                          "price": r.randint(40, 1900), "stock": r.randint(0, 120), "sku": f"{r.choice('KLMN')}{r.randint(1000, 9999)}"})
        elif a == "jobs":
            self.cities = r.sample(CITIES, 6)
            self.jobs = []
            for _ in range(24):
                self.jobs.append({"id": f"j{len(self.jobs)}", "keyword": r.choice(JOBS), "location": r.choice(self.cities), "company": r.choice(COMPANIES), "salary": r.randint(40, 190) * 1000})
        elif a == "restaurants":
            self.cities = r.sample(CITIES, 5)
            self.cuis = r.sample(CUISINES, 5)
            self.restos = []
            used = set()
            for _ in range(30):
                n = f"{r.choice(RESTO_A)} {r.choice(RESTO_B)}"
                if n in used:
                    continue
                used.add(n)
                self.restos.append({"id": f"r{len(self.restos)}", "restoname": n, "cuisine": r.choice(self.cuis), "city": r.choice(self.cities), "rating": round(r.uniform(3.0, 5.0), 1),
                                    "phone": f"{r.randint(1000, 9999)}"})
        elif a == "stocks":
            self.quotes = {}
            while len(self.quotes) < 8:
                t = "".join(r.choice("ABCDEFGHKLMNPRSTVWXZ") for _ in range(4))
                self.quotes[t] = {"ticker": t, "price": r.randint(8, 900), "change": r.randint(-9, 9), "volume": r.randint(10**4, 9 * 10**6)}
        elif a == "wiki":
            idx = r.sample(range(len(COUNTRIES)), 8)
            self.arts = [{"id": f"a{i}", "term": COUNTRIES[i], "capital": CAPITALS[i], "population": r.randint(1, 140) * 10**6 // 3, "currency": CURRENCIES[i]} for i in idx]

    # ------------------------------------------------------------------ tasks
    def make_tasks(self, r: random.Random, n: int) -> list[Task]:
        a = self.arch
        out = []
        S = lambda k, raw: canon_raw(SHAPE[k], raw)
        if a == "flights":
            combos = sorted({(f["origin"], f["destination"], f["date"]) for f in self.flights})
            for i, (o, d, dt) in enumerate(r.sample(combos, n)):
                rows = [f for f in self.flights if (f["origin"], f["destination"], f["date"]) == (o, d, dt)]
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split,
                                [f"Find the airline and price of flights from {o} to {d} on {dt}", f"What are the carrier and fare for trips from {o} to {d} on {dt}?"],
                                {"origin": o, "destination": d, "date": dt}, [["airline", "price"], ["carrier", "fare"]], ["airline", "price"],
                                [{"airline": S("airline", x["airline"]), "price": S("price", x["price"])} for x in rows], "/"))
        elif a == "weather":
            for i, c in enumerate(r.sample(self.cities, n)):
                x = self.rows[c]
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"What is the temperature and humidity in {c}?", f"How many degrees and what humidity is it in {c} right now?"],
                                {"city": c}, [["temperature", "humidity"], ["degrees", "humidity"]], ["temperature", "humidity"],
                                [{"temperature": S("temperature", x["temperature"]), "humidity": S("humidity", x["humidity"])}], "/"))
        elif a == "library":
            for i, b in enumerate(r.sample(self.books, n)):
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"Where is the book '{b['title']}' shelved and what is its status?", f"Which shelf location and availability does '{b['title']}' have?"],
                                {"title": b["title"]}, [["shelf", "status"], ["location", "availability"]], ["shelf", "status"],
                                [{"shelf": S("shelf", b["shelf"]), "status": S("status", b["status"])}], "/"))
        elif a == "shop":
            for i, p in enumerate(r.sample(self.products, n)):
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"What is the price and stock of the {p['product']} in {p['category']}?", f"How much does the {p['product']} ({p['category']}) cost and how many units are in stock?"],
                                {"category": p["category"], "product": p["product"]}, [["price", "stock"], ["cost", "units in stock"]], ["price", "stock"],
                                [{"price": S("price", p["price"]), "stock": S("stock", p["stock"])}], "/"))
        elif a == "jobs":
            combos = sorted({(j["keyword"], j["location"]) for j in self.jobs})
            for i, (k, l) in enumerate(r.sample(combos, n)):
                rows = [j for j in self.jobs if (j["keyword"], j["location"]) == (k, l)]
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"Find the company and salary of {k} jobs in {l}", f"Which employer and pay for {k} openings in {l}?"],
                                {"keyword": k, "location": l}, [["company", "salary"], ["employer", "pay"]], ["company", "salary"],
                                [{"company": S("company", j["company"]), "salary": S("salary", j["salary"])} for j in rows], "/"))
        elif a == "restaurants":
            combos = sorted({(x["cuisine"], x["city"]) for x in self.restos})
            for i, (cu, ci) in enumerate(r.sample(combos, n)):
                rows = [x for x in self.restos if (x["cuisine"], x["city"]) == (cu, ci)]
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"List the name and phone of {cu} restaurants in {ci}", f"Which restaurant and telephone for {cu} food in {ci}?"],
                                {"cuisine": cu, "city": ci}, [["name", "phone"], ["restaurant", "telephone"]], ["restoname", "phone"],
                                [{"restoname": S("restoname", x["restoname"]), "phone": S("phone", x["phone"])} for x in rows], "/"))
        elif a == "stocks":
            for i, t in enumerate(r.sample(sorted(self.quotes), n)):
                q = self.quotes[t]
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"What is the price and change of {t}?", f"Give the last price and percent change for {t}"],
                                {"ticker": t}, [["price", "change"], ["last price", "percent change"]], ["price", "change"],
                                [{"price": S("price", q["price"]), "change": S("change", q["change"])}], "/"))
        elif a == "wiki":
            for i, x in enumerate(r.sample(self.arts, n)):
                out.append(Task(f"{self.id}.{i}", self.id, a, self.split, [f"What are the capital and population of {x['term']}?", f"Name the capital city and inhabitants of {x['term']}"],
                                {"term": x["term"]}, [["capital", "population"], ["capital city", "inhabitants"]], ["capital", "population"],
                                [{"capital": S("capital", x["capital"]), "population": S("population", x["population"])}], "/"))
        for t in out:
            t.meta = {"layout": self.layout, "label_style": self.label_style, "link_style": self.link_style, "name_style": self.name_style, "date_widget": self.date_widget}
        return out

    # ------------------------------------------------------------------ html
    def form_fields(self) -> list[tuple]:
        """(key, concept, widget, options|None) for the main search form"""
        a = self.arch
        if a == "flights":
            f = [("origin", "origin", "select", self.cities), ("destination", "destination", "select", self.cities), ("date", "date", self.date_widget, None)]
            if self.swap:
                f[0], f[1] = f[1], f[0]
                f[0] = ("destination", "destination", "select", self.cities)
                f[1] = ("origin", "origin", "select", self.cities)
            return f
        if a == "weather":
            return [("city", "city", "text", None)]
        if a == "library":
            return [("title", "title_q", "text", None)]
        if a == "jobs":
            return [("keyword", "keyword", "text", None), ("location", "city", "select", self.cities)]
        if a == "restaurants":
            return [("cuisine", "cuisine", "select", self.cuis), ("city", "city", "select", self.cities)]
        if a == "stocks":
            return [("ticker", "ticker", "text", None)]
        if a == "wiki":
            return [("term", "term", "text", None)]
        return []

    def fname(self, key: str, i: int) -> str:
        return key if self.name_style == "meaningful" else f"{'qfxz'[i % 4]}{i + 1}"

    def render_form(self, action: str, fields: list, heading: str, submit: str, form_id: str = "main") -> str:
        parts = [f'<form action="{action}" method="get" id="{form_id}"><h2>{html.escape(heading)}</h2>']
        for i, (key, concept, widget, opts) in enumerate(fields):
            label = self.lab(concept)
            nm = self.fname(key, i)
            ident = f"{form_id}_{nm}"
            ph = ""
            if widget == "select":
                first = f'<option value="">Select {html.escape(label.lower())}</option>' if self.label_style == "placeholder" else '<option value=""></option>'
                inp = f'<select id="{ident}" name="{nm}"' + (f' aria-label="{html.escape(label)}"' if self.label_style == "aria" else "") + ">" + first + "".join(f'<option value="{html.escape(o)}">{html.escape(o)}</option>' for o in opts) + "</select>"
            elif widget == "date":
                inp = f'<input type="date" id="{ident}" name="{nm}"' + (f' aria-label="{html.escape(label)}"' if self.label_style == "aria" else "") + ">"
            else:
                ph_text = "YYYY-MM-DD" if key == "date" else label
                extra = f' placeholder="{html.escape(ph_text)}"' if (self.label_style == "placeholder" or key == "date") else ""
                extra += f' aria-label="{html.escape(label)}"' if self.label_style == "aria" else ""
                inp = f'<input type="text" id="{ident}" name="{nm}"{extra}>'
            if self.label_style == "for":
                parts.append(f'<div class="row"><label for="{ident}">{html.escape(label)}</label>{inp}</div>')
            elif self.label_style == "wrap":
                parts.append(f'<div class="row"><label>{html.escape(label)} {inp}</label></div>')
            elif self.label_style == "span":
                parts.append(f'<div class="row"><span class="lbl">{html.escape(label)}</span>{inp}</div>')
            else:
                parts.append(f'<div class="row">{inp}</div>')
        parts.append(f'<button type="submit">{html.escape(submit)}</button></form>')
        return "".join(parts)

    def render_records(self, recs: list[dict], fields: list[tuple], link_fn=None, ad_idx=None) -> str:
        """fields: [(key, concept)]; recs: dict key->display text; link_fn(rec)->href or None"""
        L = self.layout
        lk = lambda rec: ("" if not link_fn or not link_fn(rec) else
                          (f'<a class="more" href="{link_fn(rec)}" title="Open record" aria-label="Open record">→</a>' if self.link_style == "icon"
                           else f'<a class="more" href="{link_fn(rec)}">{["View", "Details", "More info"][hash(rec.get("_k", "")) % 3]}</a>'))
        ad = lambda rec: '<span class="badge ad">Sponsored</span>' if rec.get("_ad") else ""
        out = []
        if L == "table":
            out.append("<table><thead><tr>" + "".join(f"<th>{html.escape(self.lab(c))}</th>" for _, c in fields) + ("<th></th>" if link_fn else "") + "</tr></thead><tbody>")
            for rec in recs:
                out.append(f'<tr class="{"ad" if rec.get("_ad") else "rec"}">' + "".join(f"<td>{html.escape(str(rec[k]))}</td>" for k, _ in fields) + (f"<td>{lk(rec)}{ad(rec)}</td>" if link_fn else f"<td>{ad(rec)}</td>" if rec.get("_ad") else "") + "</tr>")
            out.append("</tbody></table>")
        elif L == "cards":
            for rec in recs:
                out.append(f'<div class="card {"ad" if rec.get("_ad") else "rec"}">' + ad(rec) + "".join(f'<div class="kv"><span class="k">{html.escape(self.lab(c))}</span> <span class="v">{html.escape(str(rec[k]))}</span></div>' for k, c in fields) + lk(rec) + "</div>")
        elif L == "list":
            out.append("<ul>")
            for rec in recs:
                out.append(f'<li class="{"ad" if rec.get("_ad") else "rec"}">' + ad(rec) + " · ".join(f"<b>{html.escape(self.lab(c))}:</b> {html.escape(str(rec[k]))}" for k, c in fields) + " " + lk(rec) + "</li>")
            out.append("</ul>")
        else:  # dl (held-out layout)
            for rec in recs:
                out.append(f'<section class="rec {"ad" if rec.get("_ad") else ""}">' + ad(rec) + "<dl>" + "".join(f"<dt>{html.escape(self.lab(c))}</dt><dd>{html.escape(str(rec[k]))}</dd>" for k, c in fields) + "</dl>" + lk(rec) + "</section>")
        return "".join(out)

    def shell(self, body: str, level: int, rng: random.Random, nav: str = "", title: str = "") -> str:
        head_search = '<form action="/help" method="get" class="hs"><input type="text" name="q" placeholder="Search help"><button>Go</button></form>' if level >= 1 else ""
        foot = ('<form action="/subscribe" method="get" class="nl"><label>Email address <input type="email" name="email" required></label><button>Subscribe</button></form>' if level >= 1 else "")
        ads = '<div class="promo-link"><a class="ad" href="/win">Sponsored: win a free trip today!</a></div>' if level >= 1 else ""
        banner = ('<div id="cb" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.55);z-index:9998"><div style="background:#fff;margin:20vh auto;width:320px;padding:20px">'
                  '<p>We use cookies to improve your experience.</p><button id="cb-accept" onclick="localStorage.setItem(\'ok\',\'1\');document.getElementById(\'cb\').remove()">Accept all</button> '
                  '<button onclick="localStorage.setItem(\'ok\',\'1\');document.getElementById(\'cb\').remove()">Reject non-essential</button></div></div>'
                  "<script>if(localStorage.getItem('ok')){var e=document.getElementById('cb');if(e)e.remove()}</script>" if level >= 1 else "")
        delay = rng.randint(500, 900)
        promo = (f"<script>setTimeout(function(){{if(localStorage.getItem('pp')||document.getElementById('pp'))return;var d=document.createElement('div');d.id='pp';"
                 "d.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:9999';"
                 "d.innerHTML='<div style=\"background:#fff;margin:25vh auto;width:300px;padding:16px\"><p>Get 10% off your first order!</p>"
                 "<button aria-label=\"Close\" onclick=\"localStorage.setItem(\\'pp\\',\\'1\\');document.getElementById(\\'pp\\').remove()\">×</button></div>';"
                 f"document.body.appendChild(d)}},{delay})</script>" if level >= 1 else "")
        return (f"<!doctype html><html><head><meta charset=utf-8><title>{html.escape(self.brand)} {html.escape(title)}</title></head><body>"
                f'<header><div class="logo"><a href="/">{html.escape(self.brand)}</a></div><nav>{nav}</nav>{head_search}</header>{banner}'
                f"<main>{ads}{body}</main><footer>{foot}<a href='/about'>About</a> <a href='/terms'>Terms</a></footer>{promo}</body></html>")

    # ------------------------------------------------------------------ routing
    def handle(self, url: str, level: int, rng: random.Random) -> tuple[int, str]:
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = u.path or "/"
        a = self.arch
        nav = ""
        if a == "shop":
            nav = "".join(f'<a href="/category/{quote(c)}">{html.escape(c)}</a> ' for c in self.cats)
            if level >= 1:
                nav += f'<a class="ad" href="/deals">Deals on {html.escape(self.cats[0])}!</a>'
        if path == "/help":
            return 200, self.shell("<h1>Help center</h1><ul><li>How do I reset my password?</li><li>Contact support</li></ul>", level, rng, nav, "help")
        if path in ("/subscribe", "/win", "/deals", "/about", "/terms"):
            return 200, self.shell("<h1>Thanks!</h1><p>Nothing to see here.</p>", level, rng, nav)
        if path == "/":
            if a == "shop":
                body = "<h1>Shop by category</h1><p>Browse our catalogue using the menu above.</p>"
            else:
                head = {"flights": "Find flights", "weather": "Weather lookup", "library": "Library catalogue", "jobs": "Job search", "restaurants": "Find a restaurant", "stocks": "Stock quotes", "wiki": "Encyclopedia"}[a]
                body = f"<h1>{head}</h1>" + self.render_form("/search", self.form_fields(), head, self.submit)
            return 200, self.shell(body, level, rng, nav)
        # ---- category (shop)
        if path.startswith("/category/") and a == "shop":
            cat = path.split("/", 2)[2]
            from urllib.parse import unquote
            cat = unquote(cat)
            recs = [{"_k": p["id"], "product": p["product"], "price": fmt("money", p["price"], self.fmt_idx["money"]), "_href": f"/item/{p['id']}"} for p in self.products if p["category"] == cat]
            body = f"<h1>{html.escape(cat)}</h1>" + self.render_records(self.decorate(recs, level, rng, [("product", "product"), ("price", "price")]), [("product", "product"), ("price", "price")], lambda r: r.get("_href"))
            return 200, self.shell(body, level, rng, nav, cat)
        # ---- detail pages
        if path.startswith("/item/"):
            iid = path.split("/", 2)[2]
            return 200, self.shell(self.detail_body(iid), level, rng, nav, "details")
        # ---- search
        if path == "/search":
            return self.search(q, level, rng, nav)
        return 404, "<html><body><h1>Not found</h1></body></html>"

    def add_twin(self, recs, flds, target, key, shape, fn):
        """insert a same-shape decoy column next to `target` (before or after, per site)"""
        if not self.twin:
            return flds
        for r in recs:
            if not r.get("_ad"):
                r[key] = fn(zlib.crc32(f"{self.id}{r['_k']}".encode()), r)
        i = [k for k, _ in flds].index(target)
        out = list(flds)
        out.insert(i if self.twin_first else i + 1, (key, key))
        return out

    def decorate(self, recs, level, rng, fields):
        recs = list(recs)
        if level >= 2:
            rng.shuffle(recs)
            ad = {"_ad": True, "_k": "ad"}
            for k, c in fields:
                shape = SHAPE.get(c, "text")
                ad[k] = fmt(shape, (9, 0) if shape == "time" else 99, self.fmt_idx.get(shape, 0)) if shape in FMT else "Special offer"
            ad["_href"] = "/win"
            recs.insert(rng.randint(0, len(recs)), ad)
        return recs

    def paginate(self, recs, q, level, base_qs):
        page = int(q.get("page", "1") or 1)
        if level >= 3 and len(recs) > 3:
            tot = recs
            recs = recs[(page - 1) * 3: page * 3]
            nxt = f'<a class="next" href="/search?{base_qs}&page={page + 1}">{html.escape(self.next_label)}</a>' if page * 3 < len(tot) else ""
            return recs, nxt
        return recs, ""

    def search(self, q, level, rng, nav):
        a = self.arch
        fields = self.form_fields()
        key_of = {self.fname(k, i): k for i, (k, *_r) in enumerate(fields)}
        P = {key_of[n]: v for n, v in q.items() if n in key_of and v != ""}
        base_qs = "&".join(f"{n}={quote(v)}" for n, v in q.items() if n != "page")
        link_fn = None
        flds = []
        if a == "flights":
            rows = [f for f in self.flights if (f["origin"], f["destination"], f["date"]) == (P.get("origin"), P.get("destination"), P.get("date"))]
            flds = [("airline", "airline"), ("depart", "depart"), ("price", "price")]
            recs = [{"_k": str(i), "airline": f["airline"], "depart": fmt("time", f["depart"], self.fmt_idx["time"]), "price": fmt("money", f["price"], self.fmt_idx["money"]), "_p": f["price"]} for i, f in enumerate(rows)]
            flds = self.add_twin(recs, flds, "price", "tax", "money", lambda h, r: fmt("money", r["_p"] // 9 + h % 7 + 1, self.fmt_idx["money"]))
        elif a == "weather":
            c = next((x for x in self.cities if x.lower() == P.get("city", "").lower()), None)
            flds = [("temperature", "temperature"), ("humidity", "humidity"), ("wind", "wind"), ("conditions", "conditions")]
            recs = [] if c is None else [{"_k": c, "temperature": fmt("temp", self.rows[c]["temperature"], self.fmt_idx["temp"]), "humidity": fmt("percent", self.rows[c]["humidity"], self.fmt_idx["percent"]),
                                          "wind": self.rows[c]["wind"], "conditions": self.rows[c]["conditions"], "_p": self.rows[c]["temperature"]}]
            flds = self.add_twin(recs, flds, "temperature", "feels", "temp", lambda h, r: fmt("temp", r["_p"] + (h % 4 + 1) * (1 if h % 2 else -1), self.fmt_idx["temp"]))
        elif a == "library":
            rows = [b for b in self.books if P.get("title", "\0").lower() in b["title"].lower()]
            flds = [("title", "title"), ("author", "author"), ("year", "year")]
            recs = [{"_k": b["id"], "title": b["title"], "author": b["author"], "year": fmt("int", b["year"], 0), "_href": f"/item/{b['id']}"} for b in rows]
            link_fn = lambda r: r.get("_href")
        elif a == "jobs":
            rows = [j for j in self.jobs if P.get("keyword", "\0").lower() in j["keyword"].lower() and j["location"] == P.get("location")]
            flds = [("jobtitle", "jobtitle"), ("company", "company"), ("salary", "salary")]
            recs = [{"_k": j["id"], "jobtitle": j["keyword"], "company": j["company"], "salary": fmt("money", j["salary"], self.fmt_idx["money"])} for j in rows]
            flds = self.add_twin(recs, flds, "salary", "bonus", "money", lambda h, r: fmt("money", 500 + h % 9000, self.fmt_idx["money"]))
        elif a == "restaurants":
            rows = [x for x in self.restos if x["cuisine"] == P.get("cuisine") and x["city"] == P.get("city")]
            flds = [("restoname", "restoname"), ("rating", "rating"), ("phone", "phone")]
            recs = [{"_k": x["id"], "restoname": x["restoname"], "rating": fmt("rating", x["rating"], self.fmt_idx["rating"]), "phone": fmt("phone", x["phone"], self.fmt_idx["phone"])} for x in rows]
        elif a == "stocks":
            t = next((k for k in self.quotes if k.lower() == P.get("ticker", "").lower()), None)
            flds = [("price", "price"), ("change", "change"), ("volume", "volume")]
            recs = [] if t is None else [{"_k": t, "price": fmt("money", self.quotes[t]["price"], self.fmt_idx["money"]), "change": fmt("percent", self.quotes[t]["change"], self.fmt_idx["percent"]), "volume": fmt("int", self.quotes[t]["volume"], self.fmt_idx["int"]), "_p": self.quotes[t]["price"]}]
            flds = self.add_twin(recs, flds, "price", "high", "money", lambda h, r: fmt("money", r["_p"] + h % 40 + 1, self.fmt_idx["money"]))
        elif a == "wiki":
            rows = [x for x in self.arts if P.get("term", "\0").lower() in x["term"].lower()]
            flds = [("title", "title")]
            recs = [{"_k": x["id"], "title": x["term"], "_href": f"/item/{x['id']}"} for x in rows]
            link_fn = lambda r: r.get("_href")
        else:
            recs, flds = [], []
        recs = self.decorate(recs, level, random.Random(f"{self.id}|{base_qs}"), flds)      # stable across the pages of one search
        recs, nxt = self.paginate(recs, q, level, base_qs)
        inner = self.render_records(recs, flds, link_fn) if recs else "<p class='empty'>No results found.</p>"
        if level >= 3:
            res = f'<div id="results">Loading results…</div><script>setTimeout(function(){{document.getElementById("results").innerHTML={json.dumps(inner + nxt)}}},{rng.randint(150, 400)})</script>'
        else:
            res = f'<div id="results">{inner}{nxt}</div>'
        return 200, self.shell(f"<h1>Results</h1>{res}", level, rng, nav, "results")

    def detail_body(self, iid: str) -> str:
        a = self.arch
        if a == "library":
            b = next((x for x in self.books if x["id"] == iid), None)
            if b:
                flds = [("title", "title"), ("isbn", "isbn"), ("shelf", "shelf"), ("status", "status")]
                return f"<h1>{html.escape(b['title'])}</h1>" + self.render_records([dict(b, _k=b["id"])], flds)
        if a == "shop":
            p = next((x for x in self.products if x["id"] == iid), None)
            if p:
                flds = [("product", "product"), ("sku", "sku"), ("stock", "stock")]
                return f"<h1>{html.escape(p['product'])}</h1>" + self.render_records([{"_k": p["id"], "product": p["product"], "sku": p["sku"], "stock": fmt("int", p["stock"], self.fmt_idx["int"])}], flds)
        if a == "wiki":
            x = next((y for y in self.arts if y["id"] == iid), None)
            if x:
                flds = [("capital", "capital"), ("population", "population"), ("currency", "currency")]
                rec = {"_k": x["id"], "capital": x["capital"], "population": fmt("int", x["population"], self.fmt_idx["int"]), "currency": x["currency"]}
                flds = self.add_twin([rec], flds, "capital", "largest", "text", lambda h, r: CITIES[h % len(CITIES)])
                return f"<h1>{html.escape(x['term'])}</h1><p>{html.escape(x['term'])} is a country.</p>" + self.render_records([rec], flds)
        return "<h1>Not found</h1>"


class Web:
    """Routes browser requests to generated sites. Non-determinism (flaky 503s, delays, shuffles) comes from a per-run RNG."""

    def __init__(self, sites: list[Site], level: int, seed: int):
        self.sites = {s.host: s for s in sites}
        self.level = level
        self.rng = random.Random(f"web-{seed}-{level}")
        self.requests = 0
        self.errors = 0

    def route(self, route):
        req = route.request
        u = urlparse(req.url)
        if req.resource_type != "document":
            route.fulfill(status=204, body="")
            return
        site = self.sites.get(u.hostname)
        self.requests += 1
        if site is None:
            route.fulfill(status=404, content_type="text/html", body="<h1>no such site</h1>")
            return
        if self.level >= 2:
            time.sleep(self.rng.uniform(0, 0.05))
            if self.rng.random() < 0.10:
                self.errors += 1
                route.fulfill(status=503, content_type="text/html", body="<html><body><h1>503 Service Unavailable</h1><p>Please retry.</p></body></html>")
                return
        status, body = site.handle(req.url, self.level, self.rng)
        route.fulfill(status=status, content_type="text/html; charset=utf-8", body=body)


DEV_ARCH = ["flights", "weather", "library", "shop"]
TEST_ARCH = ["jobs", "restaurants", "stocks", "wiki"]


def make_world(seed: int, dev_sites: int = 3, test_sites: int = 4, tasks_per_site: int = 3) -> list[Site]:
    sites = []
    for ai, a in enumerate(DEV_ARCH):
        for i in range(dev_sites):
            sites.append(Site(f"d{ai}x{i}", a, "dev", seed, tasks_per_site))
    for ai, a in enumerate(TEST_ARCH):
        for i in range(test_sites):
            sites.append(Site(f"t{ai}x{i}", a, "test", seed, tasks_per_site))
    return sites
