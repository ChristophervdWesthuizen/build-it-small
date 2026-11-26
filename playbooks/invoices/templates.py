"""Six invoice layouts, as different from each other as real suppliers' invoices are."""
from datetime import date
from html import escape as e

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def fmt_money(x, style, prefix=True):
    neg = x < 0
    x = abs(x)
    whole, cents = f"{x:.2f}".split(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    if style == "space_dot":
        s = " ".join(groups) + "." + cents
        s = ("R " + s) if prefix else s
    elif style == "comma_dot":
        s = ",".join(groups) + "." + cents
        s = ("R" + s) if prefix else s
    else:  # space_comma, common on South African statements
        s = " ".join(groups) + "," + cents
        s = ("R " + s) if prefix else s
    return ("-" if neg else "") + s


def fmt_date(iso, style):
    d = date.fromisoformat(iso)
    if style == "iso":
        return d.isoformat()
    if style == "dmy_slash":
        return d.strftime("%d/%m/%Y")
    if style == "long":
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return f"{d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}"


BASE_CSS = """
body{margin:0;background:#fff;color:#1d1d1d}
.page{width:794px;min-height:1000px;padding:48px 56px;box-sizing:border-box}
table{border-collapse:collapse;width:100%} td,th{padding:6px 8px;font-size:13px}
.r{text-align:right} .small{font-size:11px;color:#666} .foot{margin-top:40px;font-size:10px;color:#999}
"""

FOOT = '<div class="foot">Fictional company. Test document for the Build It Small invoice playbook.</div>'


def render_html(c, buyer):
    p, nf, df = c["printed"], c["numfmt"], c["datefmt"]
    m = lambda x: fmt_money(x, nf)
    d = fmt_date(p["invoice_date"], df)
    credit = p["doc_type"] == "credit_note"
    vat_no = p["supplier_vat_number"]
    t = c["template"]
    lines = p["lines"]

    if t == 1:  # classic: label column, ruled table
        title = "CREDIT NOTE" if credit else "TAX INVOICE"
        rows = "".join(f"<tr><td>{e(l['description'])}</td><td class=r>{l['qty']}</td><td class=r>{m(l['unit_price'])}</td><td class=r>{m(l['line_total'])}</td></tr>" for l in lines)
        body = f"""
<div style="font-family:Arial,Helvetica,sans-serif">
<h1 style="font-size:26px;margin:0 0 4px">{title}</h1>
<div style="font-size:15px;font-weight:bold">{e(p['supplier_name'])}</div>
<div class=small>{'VAT Reg No: ' + vat_no if vat_no else ''}</div>
<table style="margin:24px 0;width:60%"><tr><td>Invoice No:</td><td>{e(p['invoice_number'])}</td></tr>
<tr><td>Date:</td><td>{d}</td></tr>{f"<tr><td>Order No:</td><td>{p['po_number']}</td></tr>" if p['po_number'] else ''}</table>
<div style="margin-bottom:16px"><b>Bill to:</b> {e(buyer['name'])}, {e(buyer['address'])}</div>
<table border=1 style="border-color:#bbb"><tr style="background:#eee"><th>Description</th><th>Qty</th><th>Unit Price</th><th>Amount</th></tr>{rows}</table>
<table style="width:45%;margin-left:55%;margin-top:12px"><tr><td>Subtotal</td><td class=r>{m(p['subtotal'])}</td></tr>
<tr><td>VAT 15%</td><td class=r>{m(p['vat_amount'])}</td></tr><tr><td><b>Total</b></td><td class=r><b>{m(p['total'])}</b></td></tr></table>
<div style="margin-top:30px" class=small>Banking details: {e(p['bank_name'])}, Acc {p['bank_account_number']}, Branch {p['branch_code']}</div>
</div>"""
    elif t == 2:  # modern: supplier right, meta grid, amount due box
        title = "Credit note" if credit else "Tax invoice"
        rows = "".join(f"<tr style='border-bottom:1px solid #eee'><td>{e(l['description'])}<div class=small>{l['qty']} × {m(l['unit_price'])}</div></td><td class=r>{m(l['line_total'])}</td></tr>" for l in lines)
        body = f"""
<div style="font-family:Georgia,serif">
<div style="text-align:right;font-size:22px">{e(p['supplier_name'])}</div>
<div style="text-align:right" class=small>{'VAT number ' + vat_no if vat_no else ''}</div>
<div style="font-size:34px;margin:40px 0 10px;color:#2b4a7a">{title} #{e(p['invoice_number'])}</div>
<table style="width:100%;margin-bottom:28px"><tr><td class=small>Issued</td><td class=small>Your ref</td><td class=small>Customer</td></tr>
<tr><td>{d}</td><td>{p['po_number'] or 'n/a'}</td><td>{e(buyer['name'])}</td></tr></table>
<table>{rows}</table>
<table style="width:50%;margin-left:50%;margin-top:18px"><tr><td>Amount excl. VAT</td><td class=r>{m(p['subtotal'])}</td></tr>
<tr><td>VAT</td><td class=r>{m(p['vat_amount'])}</td></tr></table>
<div style="background:#2b4a7a;color:#fff;padding:14px;width:45%;margin-left:52%;margin-top:10px;font-size:20px">Amount {'credited' if credit else 'due'} {m(p['total'])}</div>
<div style="margin-top:40px">Pay to {e(p['bank_name'])} · account {p['bank_account_number']} · branch code {p['branch_code']}</div>
</div>"""
    elif t == 3:  # compact, monospace, till-slip feel
        title = "CREDIT NOTE" if credit else "TAX INVOICE"
        rows = "<br>".join(f"{l['qty']} x {e(l['description'])} @ {fmt_money(l['unit_price'], nf, False)} = {fmt_money(l['line_total'], nf, False)}" for l in lines)
        body = f"""
<div style="font-family:Courier New,monospace;font-size:14px;width:460px">
<div style="text-align:center">{e(p['supplier_name'].upper())}<br>{'VAT ' + vat_no if vat_no else ''}<br>{title}</div>
<br>INV#: {e(p['invoice_number'])}<br>DATE: {d}<br>{'ORDER: ' + p['po_number'] + '<br>' if p['po_number'] else ''}ACCOUNT: {e(buyer['name'].upper())}
<br>----------------------------------------<br>{rows}<br>----------------------------------------
<br>SUBTOTAL EXCL {fmt_money(p['subtotal'], nf, False)}<br>VAT @15% {fmt_money(p['vat_amount'], nf, False)}<br>TOTAL ZAR {fmt_money(p['total'], nf, False)}
<br>----------------------------------------<br>EFT: {e(p['bank_name'].upper())} {p['bank_account_number']} BR {p['branch_code']}
</div>"""
    elif t == 4:  # two columns, bank box prominent
        title = "Credit Note" if credit else "Invoice"
        rows = "".join(f"<tr><td>{l['qty']}</td><td>{e(l['description'])}</td><td class=r>{m(l['unit_price'])}</td><td class=r>{m(l['line_total'])}</td></tr>" for l in lines)
        body = f"""
<div style="font-family:Verdana,sans-serif;font-size:13px">
<table><tr><td style="width:55%;vertical-align:top"><div style="font-size:20px;font-weight:bold">{e(p['supplier_name'])}</div>{'Tax ref (VAT): ' + vat_no if vat_no else ''}</td>
<td style="vertical-align:top;border:2px solid #333;padding:10px"><b>BANKING DETAILS</b><br>Bank: {e(p['bank_name'])}<br>Account no: {p['bank_account_number']}<br>Branch: {p['branch_code']}</td></tr></table>
<div style="font-size:24px;margin:30px 0 8px">{title}</div>
<div>Document No {e(p['invoice_number'])} &nbsp; | &nbsp; {d}{' &nbsp; | &nbsp; Customer Order ' + p['po_number'] if p['po_number'] else ''}</div>
<div style="margin:12px 0 20px">Customer: {e(buyer['name'])}</div>
<table border=1 style="border-color:#999"><tr><th>Qty</th><th>Item</th><th>Price</th><th>Total</th></tr>{rows}</table>
<div class=r style="margin-top:12px">Total excl. VAT: {m(p['subtotal'])}<br>VAT: {m(p['vat_amount'])}<br><b>Total incl. VAT: {m(p['total'])}</b></div>
</div>"""
    elif t == 5:  # bilingual Afrikaans and English labels
        title = "KREDIETNOTA / CREDIT NOTE" if credit else "BELASTINGFAKTUUR / TAX INVOICE"
        rows = "".join(f"<tr><td>{e(l['description'])}</td><td class=r>{l['qty']}</td><td class=r>{m(l['unit_price'])}</td><td class=r>{m(l['line_total'])}</td></tr>" for l in lines)
        body = f"""
<div style="font-family:Tahoma,sans-serif">
<div style="font-size:12px">{title}</div><div style="font-size:21px;margin:6px 0">{e(p['supplier_name'])}</div>
<div class=small>{'BTW nr / VAT no: ' + vat_no if vat_no else ''}</div>
<table style="margin:20px 0;width:70%"><tr><td>Faktuur nr / Inv no</td><td>{e(p['invoice_number'])}</td></tr><tr><td>Datum / Date</td><td>{d}</td></tr>
{f"<tr><td>Bestelling / PO</td><td>{p['po_number']}</td></tr>" if p['po_number'] else ''}<tr><td>Klient / Client</td><td>{e(buyer['name'])}</td></tr></table>
<table border=1 style="border-color:#ccc"><tr><th>Beskrywing / Description</th><th>Hoev / Qty</th><th>Prys / Price</th><th>Bedrag / Amount</th></tr>{rows}</table>
<table style="width:50%;margin-left:50%;margin-top:12px"><tr><td>Subtotaal</td><td class=r>{m(p['subtotal'])}</td></tr><tr><td>BTW / VAT 15%</td><td class=r>{m(p['vat_amount'])}</td></tr>
<tr><td><b>Totaal / Total</b></td><td class=r><b>{m(p['total'])}</b></td></tr></table>
<div style="margin-top:28px" class=small>Bankbesonderhede / Banking: {e(p['bank_name'])} rek/acc {p['bank_account_number']} tak/branch {p['branch_code']}</div>
</div>"""
    else:  # letter style: the numbers are inside sentences
        what = "credit note" if credit else "invoice"
        items = "".join(f"<li>{e(l['description'])}: {l['qty']} at {m(l['unit_price'])}, {m(l['line_total'])}</li>" for l in lines)
        body = f"""
<div style="font-family:'Times New Roman',serif;font-size:15px;line-height:1.5">
<div style="font-size:19px">{e(p['supplier_name'])}</div>
<div class=small>{'Registered for VAT under number ' + vat_no if vat_no else 'Registered company'}</div>
<p style="margin-top:36px">{d}</p><p>Attention: Accounts Payable, {e(buyer['name'])}</p>
<p>Please find our {what} number <b>{e(p['invoice_number'])}</b>{' against your order ' + p['po_number'] if p['po_number'] else ''} for the following:</p>
<ul>{items}</ul>
<p>The amount before VAT is {m(p['subtotal'])}, VAT at 15% comes to {m(p['vat_amount'])}, and the total {'credited to your account' if credit else 'payable'} is <b>{m(p['total'])}</b>.</p>
<p>Kindly make payment into our {e(p['bank_name'])} account, number {p['bank_account_number']}, branch code {p['branch_code']}.</p>
<p>Yours sincerely,<br>Accounts</p>
</div>"""
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body><div class=page>{body}{FOOT}</div></body></html>"
