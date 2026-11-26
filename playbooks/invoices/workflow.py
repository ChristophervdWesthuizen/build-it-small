"""Playbook 1: supplier invoices. The workflow, one rung at a time.

  1. Get the text out of the PDF for free (pdftotext). Scans and photos have none.
  2. Read the invoice: rules first, then a small model, then a bigger one only if the checks fail.
  3. Check it with code: required fields, VAT number format, the arithmetic.
  4. Match it with code: supplier list, purchase order, paid history, bank details on file.
  5. Route it: a clean invoice becomes a draft bill; anything else goes to a person, with the reason.
"""
import difflib
import json
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
VAT_RATE = 0.15
BANKS = ["Protea Bank", "Highveld Mutual Bank", "Cape Commerce Bank", "Ubuntu Savings Bank"]

# ---------------------------------------------------------------- the output format (step 2)
NULLABLE_STR = {"type": ["string", "null"]}
NULLABLE_NUM = {"type": ["number", "null"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": ["invoice", "credit_note"]},
        "supplier_name": NULLABLE_STR,
        "supplier_vat_number": NULLABLE_STR,
        "invoice_number": NULLABLE_STR,
        "invoice_date": NULLABLE_STR,
        "po_number": NULLABLE_STR,
        "lines": {"type": "array", "items": {
            "type": "object",
            "properties": {"description": {"type": "string"}, "qty": {"type": "number"},
                           "unit_price": {"type": "number"}, "line_total": {"type": "number"}},
            "required": ["description", "qty", "unit_price", "line_total"], "additionalProperties": False}},
        "subtotal": NULLABLE_NUM,
        "vat_amount": NULLABLE_NUM,
        "total": NULLABLE_NUM,
        "bank_name": NULLABLE_STR,
        "bank_account_number": NULLABLE_STR,
        "branch_code": NULLABLE_STR,
    },
    "required": ["doc_type", "supplier_name", "supplier_vat_number", "invoice_number", "invoice_date", "po_number",
                 "lines", "subtotal", "vat_amount", "total", "bank_name", "bank_account_number", "branch_code"],
    "additionalProperties": False,
}

PROMPT = (HERE / "prompt.md").read_text()


# ---------------------------------------------------------------- step 1: free text
def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- step 2a: rules only
MONEY = r"(-?R?\s?\d{1,3}(?:[ ,]\d{3})*(?:[.,]\d{2}))"
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_money(s):
    if s is None:
        return None
    s = s.replace("R", "").replace("ZAR", "").strip()
    neg = s.startswith("-")
    s = s.lstrip("-").strip()
    if re.search(r",\d{2}$", s):  # decimal comma
        s = s.replace(" ", "").replace(",", ".")
    else:
        s = s.replace(" ", "").replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def parse_date(s):
    s = s.strip()
    for f in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2)[:3].lower() in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1))).isoformat()
    return None


def first(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def rules_read(text):
    """Generic label rules, written once for invoices in general, not tuned to these six layouts."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = re.compile(r"(tax invoice|invoice|credit note|faktuur|kredietnota)", re.I)
    name = next((l for l in lines if re.search(r"\b(pty|ltd|cc|co|services|solutions|supplies|stationers|couriers|packaging|consulting|signs|catering|plumbing|logistics)\b", l, re.I) and not title.fullmatch(l)), None)
    if name:
        name = re.split(r"\s{2,}", name)[0]
    date_raw = first(r"(?:date|datum|issued)[^\n\d]{0,25}(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", text)
    if not date_raw:
        date_raw = first(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|[A-Z][a-z]{2})\s+\d{4})", text, 0)
    return {
        "doc_type": "credit_note" if re.search(r"credit note|kredietnota", text, re.I) else "invoice",
        "supplier_name": name,
        "supplier_vat_number": first(r"(?:VAT|BTW)[^\n0-9]{0,40}(4\d{9})", text),
        "invoice_number": first(r"(?:invoice no|inv no|inv#|document no|invoice number|credit note number|#)\s*:?\s*([A-Z]{0,3}-?\d{3,6})\b", text),
        "invoice_date": parse_date(date_raw) if date_raw else None,
        "po_number": first(r"(PO-\d{4}-\d{4})", text),
        "lines": [],  # line items are too varied for generic rules
        "subtotal": parse_money(first(r"(?:subtotal excl|subtotal|subtotaal|amount excl\.? vat|total excl\.? vat|amount before vat is)\s*:?\s*" + MONEY, text)),
        "vat_amount": parse_money(first(r"(?:vat\s*@?\s*15%|btw / vat 15%|vat at 15% comes to|^\s*vat:?)\s*:?\s*" + MONEY, text, re.I | re.M)),
        "total": parse_money(first(r"(?:total incl\.? vat|total zar|totaal / total|amount due|amount credited|total payable is|total credited to your account is|\btotal)\s*:?\s*" + MONEY, text)),
        "bank_name": next((b for b in BANKS if b.lower() in text.lower()), None),
        "bank_account_number": first(r"(?:acc(?:ount)?(?:\s*no)?|rek/acc|account,? number)\D{0,12}(\d{9,11})", text),
        "branch_code": first(r"(?:branch(?: code)?|br|tak/branch)\D{0,8}(\d{6})\b", text),
    }


# ---------------------------------------------------------------- step 3: checks in code
REQUIRED = ["supplier_name", "invoice_number", "invoice_date", "subtotal", "vat_amount", "total", "bank_account_number"]


def close(a, b, tol=0.02):
    return a is not None and b is not None and abs(a - b) <= tol


def checks(f):
    """Returns a list of problems. Empty means the reading holds together."""
    if f is None:
        return ["unread"]
    problems = [f"missing {k}" for k in REQUIRED if f.get(k) in (None, "")]
    v = f.get("supplier_vat_number")
    if v and not re.fullmatch(r"4\d{9}", re.sub(r"\s", "", v)):
        problems.append("VAT number format")
    if f.get("invoice_date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f["invoice_date"]):
        problems.append("date format")
    if f.get("lines"):
        for ln in f["lines"]:
            if not close(ln["qty"] * ln["unit_price"], ln["line_total"], 0.05):
                problems.append("arithmetic: line")
                break
        if not close(sum(l["line_total"] for l in f["lines"]), f.get("subtotal"), 0.05):
            problems.append("arithmetic: lines to subtotal")
    if f.get("subtotal") is not None and not close(f["subtotal"] * VAT_RATE, f.get("vat_amount"), 0.05):
        problems.append("arithmetic: VAT")
    if f.get("subtotal") is not None and f.get("vat_amount") is not None and not close(f["subtotal"] + f["vat_amount"], f.get("total"), 0.02):
        problems.append("arithmetic: total")
    return problems


def only_arithmetic(problems):
    return bool(problems) and all(p.startswith("arithmetic") for p in problems)


# ---------------------------------------------------------------- step 4: match in code
def load_master():
    d = HERE / "data"
    return {k: json.loads((d / f"{k}.json").read_text()) for k in ("suppliers", "purchase_orders", "paid_history")}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_supplier(f, master):
    v = re.sub(r"\s", "", f.get("supplier_vat_number") or "")
    for s in master["suppliers"]:
        if v and s["vat_number"] == v:
            return s
    names = {norm(s["name"]): s for s in master["suppliers"]}
    best = difflib.get_close_matches(norm(f.get("supplier_name")), list(names), n=1, cutoff=0.9)
    return names[best[0]] if best else None


def exceptions(f, master):
    """What a person must look at. Empty means the invoice can become a draft bill."""
    out = []
    s = find_supplier(f, master)
    if f.get("doc_type") == "credit_note":
        out.append("credit_note")
    if not f.get("supplier_vat_number"):
        out.append("missing_vat_number")
    if s is None:
        out.append("unknown_supplier")
    else:
        if norm(f.get("bank_account_number")) != s["bank"]["account_number"]:
            out.append("bank_details_changed")
        if any(h["supplier_id"] == s["id"] and norm(h["invoice_number"]) == norm(f.get("invoice_number")) for h in master["paid_history"]):
            out.append("duplicate")
    po = next((p for p in master["purchase_orders"] if p["po_number"] == (f.get("po_number") or "").strip()), None)
    if po is None:
        out.append("no_purchase_order")
    elif f.get("lines"):
        agreed = {norm(l["description"]): l["unit_price"] for l in po["lines"]}
        for ln in f["lines"]:
            key = difflib.get_close_matches(norm(ln["description"]), list(agreed), n=1, cutoff=0.8)
            if key and ln["unit_price"] > agreed[key[0]] * 1.01:
                out.append("price_above_po")
                break
    else:
        out.append("lines_not_read")  # can't compare prices without the lines
    return sorted(set(out))
