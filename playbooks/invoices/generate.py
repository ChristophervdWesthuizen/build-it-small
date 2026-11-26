"""Make the test set for Playbook 1: 200 invented supplier invoices with answer keys.

Everything here is fictional: companies, banks, VAT numbers, accounts. No real data.
Run:  python generate.py          (writes data/*.json and cases/*.html + cases/*.truth.json)
Then: node render.mjs             (HTML to PDF and PNG)
Then: python degrade.py           (PNG to 'scans' and 'phone photos')
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DATA, CASES = HERE / "data", HERE / "cases"
VAT_RATE = 0.15  # South African standard VAT rate; check it is still current before publishing
SEED = 20261126
N_CASES = 200
BUYER = {"name": "Mzansi Manufacturing (Pty) Ltd", "address": "14 Foundry Road, Germiston, 1401"}

BANKS = ["Protea Bank", "Highveld Mutual Bank", "Cape Commerce Bank", "Ubuntu Savings Bank"]
SUPPLIER_NAMES = [
    ("Karoo Quill Office Supply (Pty) Ltd", "office"), ("Highveld Sparkle Cleaning CC", "cleaning"),
    ("Bluegum and Pepper Catering (Pty) Ltd", "catering"), ("Two Rivers Byte Solutions", "it"),
    ("Fynbos Ink Print and Signage", "print"), ("Mopane Line Logistics (Pty) Ltd", "logistics"),
    ("Sandstone Watch Security Services", "security"), ("Waterberg Volt Electrical CC", "electrical"),
    ("Protea Paperworks Stationers", "office"), ("Klipspringer Express Couriers", "logistics"),
    ("Baobab Fresh Hygiene Supplies", "cleaning"), ("Umhlanga Keystone Facilities (Pty) Ltd", "facilities"),
    ("Drakensberg Oak Furniture Co", "furniture"), ("Kalahari Axle Fleet Services", "fleet"),
    ("Marula Stack Software (Pty) Ltd", "it"), ("Agulhas Pipe Plumbing CC", "facilities"),
    ("Springbok Crate Packaging", "packaging"), ("Lowveld Shield Pest Control", "cleaning"),
    ("Cederberg Compass Consulting", "consulting"), ("Zebra Stripe Signs and Banners", "print"),
]
UNKNOWN_NAMES = [("Gemsbok Bolt Hardware (Pty) Ltd", "electrical"), ("Tugela Thread Uniforms", "office"),
                 ("Magaliesberg Mist Water Co", "catering"), ("Sabie Spark Generators", "electrical"),
                 ("Hex River Haulage", "logistics"), ("Nama Bloom Florists", "facilities")]
ITEMS = {
    "office": [("A4 copy paper, box of 5 reams", 389.00), ("Toner cartridge, black", 1249.00), ("Ballpoint pens, box of 50", 145.50), ("Lever arch files", 38.90), ("Desk organiser", 219.00)],
    "cleaning": [("Monthly office cleaning", 8450.00), ("Window cleaning, external", 2300.00), ("Hand soap refill 5L", 189.00), ("Sanitary bin service", 95.00), ("Deep clean, kitchen", 1750.00)],
    "catering": [("Staff lunch platter (20 pax)", 2850.00), ("Coffee and tea service", 640.00), ("Boardroom breakfast", 1320.00), ("Bottled water, case of 24", 132.00)],
    "it": [("Laptop support, monthly", 4200.00), ("Microsoft 365 licence", 285.00), ("Network switch, 24 port", 3899.00), ("Callout fee", 650.00), ("Backup service, monthly", 1100.00)],
    "print": [("Business cards, 500", 420.00), ("Pull up banner", 1150.00), ("A1 poster print", 260.00), ("Vehicle decal", 2480.00)],
    "logistics": [("Same day delivery, Gauteng", 380.00), ("Overnight courier, national", 245.00), ("Pallet transport, per pallet", 1650.00), ("Fuel surcharge", 120.00)],
    "security": [("Guarding, monthly", 18500.00), ("Armed response, monthly", 1450.00), ("CCTV maintenance", 2200.00)],
    "electrical": [("LED panel light", 465.00), ("Electrician, per hour", 590.00), ("Distribution board inspection", 1850.00), ("Cable, 100m roll", 1290.00)],
    "facilities": [("Aircon service", 1380.00), ("Plumber, per hour", 560.00), ("Geyser replacement 150L", 7900.00), ("Garden maintenance, monthly", 3200.00)],
    "furniture": [("Office chair, ergonomic", 3450.00), ("Desk, 1600mm", 4100.00), ("Filing cabinet, 4 drawer", 2650.00)],
    "fleet": [("Vehicle service, minor", 2950.00), ("Tyre, 195/65 R15", 1240.00), ("Wheel alignment", 450.00)],
    "packaging": [("Carton, double wall", 18.40), ("Stretch wrap roll", 145.00), ("Pallet, wooden", 165.00), ("Packing tape, 48mm", 24.50)],
    "consulting": [("Consulting, per hour", 1450.00), ("Workshop facilitation, day", 12500.00), ("Report preparation", 6800.00)],
}

# How many cases of each kind of trouble. The rest are clean. A case can carry more than one.
MESS = {"missing_vat_number": 10, "credit_note": 8, "duplicate": 8, "bank_changed": 8,
        "price_above_po": 10, "unknown_supplier": 6, "math_error": 6, "no_po": 10}
FORMATS = ["pdf"] * 140 + ["scan"] * 40 + ["photo"] * 20


def vat_number(r):
    return "4" + "".join(str(r.randint(0, 9)) for _ in range(9))


def account(r):
    return "".join(str(r.randint(0, 9)) for _ in range(r.choice([9, 10, 11])))


def make_supplier(r, name, cat, i):
    bank = r.choice(BANKS)
    return {"id": f"S{i:03d}", "name": name, "category": cat, "vat_number": vat_number(r),
            "address": f"{r.randint(1, 220)} {r.choice(['Main', 'Church', 'Station', 'Industria', 'Voortrekker', 'Market'])} Street, {r.choice(['Pretoria', 'Johannesburg', 'Durban', 'Cape Town', 'Gqeberha', 'Polokwane', 'Bloemfontein'])}",
            "bank": {"bank_name": bank, "account_number": account(r), "branch_code": str(r.randint(100000, 999999))}}


def money(x):
    return round(x + 1e-9, 2)


def main():
    r = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    CASES.mkdir(exist_ok=True)
    suppliers = [make_supplier(r, n, c, i + 1) for i, (n, c) in enumerate(SUPPLIER_NAMES)]
    unknown = [make_supplier(r, n, c, 900 + i) for i, (n, c) in enumerate(UNKNOWN_NAMES)]

    # Invoices already paid last month: the history a duplicate is checked against.
    history = []
    for k in range(30):
        s = r.choice(suppliers)
        history.append({"supplier_id": s["id"], "invoice_number": f"{r.choice(['INV', 'IN', 'TI', ''])}{r.randint(1000, 99999)}",
                        "total": money(r.uniform(300, 40000))})

    # Assign trouble to cases: each messy case carries exactly one kind, so each result means one thing.
    idx = list(range(N_CASES))
    r.shuffle(idx)
    tags = {i: set() for i in range(N_CASES)}
    pos = 0
    for kind, n in MESS.items():
        for _ in range(n):
            tags[idx[pos % N_CASES]].add(kind)
            pos += 1
    formats = FORMATS[:]
    r.shuffle(formats)

    pos_list, cases = [], []
    start = date(2026, 10, 1)
    for i in range(N_CASES):
        t = tags[i]
        dup = None
        if "unknown_supplier" in t:
            s = unknown[len([c for c in cases if "unknown_supplier" in c["tags"]]) % len(unknown)]
        elif "duplicate" in t:  # same supplier and number as an invoice already paid
            dup = r.choice(history)
            s = next(x for x in suppliers if x["id"] == dup["supplier_id"])
        else:
            s = r.choice(suppliers)
        cat_items = ITEMS[s["category"]]
        n_lines = r.randint(1, min(5, len(cat_items)))
        chosen = r.sample(cat_items, n_lines)
        lines = []
        po_lines = []
        for desc, price in chosen:
            if "per hour" in desc:
                qty = r.randint(1, 12)
            elif "monthly" in desc or price >= 1000 or any(w in desc.lower() for w in ("service", "inspection", "fee", "workshop", "report", "deep clean", "replacement", "alignment")):
                qty = r.choice([1, 1, 1, 2, 3])
            else:
                qty = r.choice([1, 2, 3, 4, 5, 6, 10, 12, 20, 24, 50])
            po_lines.append({"description": desc, "qty": qty, "unit_price": price})
            lines.append({"description": desc, "qty": qty, "unit_price": price})
        if "price_above_po" in t:
            j = r.randrange(len(lines))
            lines[j]["unit_price"] = money(lines[j]["unit_price"] * r.uniform(1.06, 1.2))
        for ln in lines:
            ln["line_total"] = money(ln["qty"] * ln["unit_price"])
        subtotal = money(sum(ln["line_total"] for ln in lines))
        vat = money(subtotal * VAT_RATE)
        total = money(subtotal + vat)
        if "math_error" in t:  # the supplier's own arithmetic is wrong on the page
            total = money(total + r.choice([-100, -10, 10, 50, 100]))
        po_number = None
        if "no_po" not in t and "unknown_supplier" not in t:
            po_number = f"PO-2026-{1000 + i:04d}"
            pos_list.append({"po_number": po_number, "supplier_id": s["id"], "lines": po_lines})
        inv_date = start + timedelta(days=r.randint(0, 50))
        if dup:
            inv_no = dup["invoice_number"]
        else:
            inv_no = f"{r.choice(['INV', 'IN', 'TI', 'INV-', ''])}{r.randint(1000, 99999)}"
        bank = dict(s["bank"])
        if "bank_changed" in t:
            bank = {"bank_name": r.choice([b for b in BANKS if b != bank["bank_name"]]), "account_number": account(r),
                    "branch_code": str(r.randint(100000, 999999))}
        doc_type = "credit_note" if "credit_note" in t else "invoice"
        printed = {
            "doc_type": doc_type, "supplier_name": s["name"],
            "supplier_vat_number": None if "missing_vat_number" in t else s["vat_number"],
            "invoice_number": inv_no, "invoice_date": inv_date.isoformat(),
            "po_number": po_number, "lines": lines, "subtotal": subtotal, "vat_amount": vat, "total": total,
            "bank_name": bank["bank_name"], "bank_account_number": bank["account_number"], "branch_code": bank["branch_code"],
        }
        # What the workflow should do with it.
        expected = set()
        if "unknown_supplier" in t:
            expected.add("unknown_supplier")
        if "duplicate" in t:
            expected.add("duplicate")
        if "bank_changed" in t and "unknown_supplier" not in t:
            expected.add("bank_details_changed")
        if "price_above_po" in t and po_number:
            expected.add("price_above_po")
        if "math_error" in t:
            expected.add("arithmetic_error")
        if "no_po" in t or "unknown_supplier" in t:
            expected.add("no_purchase_order")
        if doc_type == "credit_note":
            expected.add("credit_note")
        if "missing_vat_number" in t:  # a tax invoice without it can't support a VAT input claim
            expected.add("missing_vat_number")
        cases.append({"id": f"inv{i + 1:03d}", "format": formats[i], "template": r.randint(1, 6),
                      "numfmt": r.choice(["space_dot", "comma_dot", "space_comma"]),
                      "datefmt": r.choice(["iso", "dmy_slash", "long", "short"]),
                      "tags": sorted(t), "printed": printed, "expected_exceptions": sorted(expected),
                      "expected_route": "person" if expected else "auto"})

    (DATA / "suppliers.json").write_text(json.dumps(suppliers, indent=1))
    (DATA / "purchase_orders.json").write_text(json.dumps(pos_list, indent=1))
    (DATA / "paid_history.json").write_text(json.dumps(history, indent=1))
    from templates import render_html
    for c in cases:
        (CASES / f"{c['id']}.html").write_text(render_html(c, BUYER))
        (CASES / f"{c['id']}.truth.json").write_text(json.dumps(c, indent=1))
    n_auto = sum(c["expected_route"] == "auto" for c in cases)
    print(f"{len(cases)} cases: {n_auto} clean (auto), {len(cases) - n_auto} need a person. Formats:",
          {f: formats.count(f) for f in set(formats)})


if __name__ == "__main__":
    main()
