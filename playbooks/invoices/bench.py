"""Run the invoice test set up a ladder of readers and score the result.

  python bench.py --ladder rules                 free: generic rules only
  python bench.py --ladder rules,haiku,opus      the cost ladder (needs API credentials)
  python bench.py --ladder opus                  the big-model baseline
  python bench.py --ladder haiku,opus --estimate cost estimate only, no calls
  options: --limit N  --runs 3  --name label

A rung is tried only if the rungs below failed the checks. Rules cannot read scans or photos.
Results go to results/<name>/: cases.jsonl, summary.json and summary.md.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))
from bis.prices import ALIASES, PRICES, PRICES_READ, cost  # noqa: E402
import workflow as wf  # noqa: E402

CASES = HERE / "cases"
FIELDS = ["doc_type", "supplier_name", "supplier_vat_number", "invoice_number", "invoice_date", "po_number",
          "subtotal", "vat_amount", "total", "bank_name", "bank_account_number", "branch_code"]
NUMERIC = {"subtotal", "vat_amount", "total"}


def load_cases(limit=None):
    cs = [json.loads(p.read_text()) for p in sorted(CASES.glob("*.truth.json"))]
    return cs[:limit] if limit else cs


def doc_path(c):
    return CASES / (c["id"] + (".pdf" if c["format"] == "pdf" else ".jpg"))


def read_with(rung, c, text):
    """One rung reads one case. Returns (fields or None, info)."""
    if rung == "rules":
        if text is None:
            return None, {"model": "rules", "cost": 0.0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0,
                          "error": "no text layer (scan or photo)"}
        t0 = time.time()
        f = wf.rules_read(text)
        return f, {"model": "rules", "cost": 0.0, "input_tokens": 0, "output_tokens": 0, "seconds": time.time() - t0, "error": None}
    from bis import claude_reader
    model = ALIASES.get(rung, rung)
    if text is not None:
        return claude_reader.read(model, wf.PROMPT, wf.SCHEMA, text=text)
    return claude_reader.read(model, wf.PROMPT, wf.SCHEMA, image_path=doc_path(c))


def same_numbers(a, b):
    return a and b and all(wf.close(a.get(k), b.get(k), 0.02) for k in ("subtotal", "vat_amount", "total"))


def process(c, ladder):
    """The workflow for one invoice: climb until the checks pass, then match and route."""
    text = wf.pdf_text(doc_path(c)) if c["format"] == "pdf" else None
    calls, accepted, problems, prev = [], None, ["unread"], None
    doc_error = False
    for rung in ladder:
        f, info = read_with(rung, c, text)
        info["rung"] = rung
        problems = wf.checks(f)
        info["problems"] = problems
        calls.append(info)
        if f is not None and not problems:
            accepted = f
            break
        # Two different readers agree on the numbers and the sums still fail: the page itself is wrong.
        if f is not None and prev is not None and wf.only_arithmetic(problems) and same_numbers(f, prev):
            accepted, doc_error = f, True
            break
        if f is not None:
            prev = f
    if accepted is None and prev is not None and rung == ladder[-1] and wf.only_arithmetic(problems) and len(ladder) == 1:
        accepted = prev  # single-rung runs cannot cross-check; keep the reading, flag the sums
        doc_error = True
    if accepted is None:
        exc = ["could_not_read"]
        fields = prev or {}
    else:
        fields = accepted
        exc = wf.exceptions(fields, MASTER)
        if doc_error:
            exc = sorted(set(exc) | {"arithmetic_error"})
    return {"id": c["id"], "format": c["format"], "template": c["template"], "fields": fields, "calls": calls,
            "exceptions": exc, "route": "auto" if not exc else "person"}


def norm_val(k, v):
    if v is None:
        return None
    if k in NUMERIC:
        return round(float(v), 2)
    if k in ("supplier_vat_number", "bank_account_number", "branch_code"):
        return "".join(ch for ch in str(v) if ch.isdigit()) or None
    return wf.norm(str(v))


def score(c, r):
    p, got = c["printed"], r["fields"] or {}
    field_ok = {k: norm_val(k, got.get(k)) == norm_val(k, p.get(k)) for k in FIELDS}
    lines_ok = len(got.get("lines") or []) == len(p["lines"]) and all(
        wf.close(a["line_total"], b["line_total"]) and wf.close(a["unit_price"], b["unit_price"]) and a["qty"] == b["qty"]
        for a, b in zip(sorted(got.get("lines") or [], key=lambda x: x["line_total"]), sorted(p["lines"], key=lambda x: x["line_total"])))
    exp, gotx = set(c["expected_exceptions"]), set(r["exceptions"])
    return {"field_ok": field_ok, "lines_ok": lines_ok,
            "caught": sorted(exp & gotx), "missed": sorted(exp - gotx), "extra": sorted(gotx - exp),
            "route_ok": r["route"] == c["expected_route"],
            "dangerous": c["expected_route"] == "person" and r["route"] == "auto"}


def summarise(rows, cases, ladder, name):
    n = len(rows)
    clean = [x for x in rows if x["case"]["expected_route"] == "auto"]
    messy = [x for x in rows if x["case"]["expected_route"] == "person"]
    calls = [k for x in rows for k in x["result"]["calls"]]
    total_cost = sum(k["cost"] for k in calls)
    first_rung_ok = sum(1 for x in rows if x["result"]["calls"] and not x["result"]["calls"][0]["problems"])
    by_rung = {}
    for k in calls:
        b = by_rung.setdefault(k["rung"], {"calls": 0, "cost": 0.0, "in": 0, "out": 0, "errors": 0})
        b["calls"] += 1
        b["cost"] += k["cost"]
        b["in"] += k["input_tokens"]
        b["out"] += k["output_tokens"]
        b["errors"] += bool(k.get("error"))
    field_acc = {f: sum(x["score"]["field_ok"][f] for x in rows) / n for f in FIELDS}
    kinds = sorted({e for x in rows for e in x["case"]["expected_exceptions"]})
    per_kind = {k: {"expected": sum(k in x["case"]["expected_exceptions"] for x in rows),
                    "caught": sum(k in x["score"]["caught"] for x in rows)} for k in kinds}
    s = {
        "name": name, "ladder": ladder, "cases": n, "prices_read": PRICES_READ,
        "fields_all_right": sum(all(x["score"]["field_ok"].values()) for x in rows) / n,
        "lines_all_right": sum(x["score"]["lines_ok"] for x in rows) / n,
        "field_accuracy": field_acc,
        "passed_checks_first_rung": first_rung_ok / n,
        "escalated": sum(len(x["result"]["calls"]) > 1 for x in rows) / n,
        "could_not_read": sum("could_not_read" in x["result"]["exceptions"] for x in rows) / n,
        "clean_cases": len(clean),
        "clean_straight_through": (sum(x["result"]["route"] == "auto" for x in clean) / len(clean)) if clean else None,
        "messy_cases": len(messy),
        "messy_sent_to_person": (sum(x["result"]["route"] == "person" for x in messy) / len(messy)) if messy else None,
        "dangerous_misses": sum(x["score"]["dangerous"] for x in rows),
        "exceptions_by_kind": per_kind,
        "cost_total_usd": round(total_cost, 4),
        "cost_per_1000_usd": round(total_cost / n * 1000, 2),
        "seconds_per_invoice": round(sum(k.get("seconds", 0) for k in calls) / n, 2),
        "by_rung": by_rung,
        "by_format": {fmt: sum(all(x["score"]["field_ok"].values()) for x in rows if x["case"]["format"] == fmt) /
                      max(1, sum(x["case"]["format"] == fmt for x in rows)) for fmt in ("pdf", "scan", "photo")},
    }
    return s


def to_md(s):
    pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"
    L = [f"# Results: {s['name']}", "", f"Ladder: {' → '.join(s['ladder'])}. {s['cases']} invoices. Prices read {s['prices_read']}.", "",
         "| Measure | Result |", "|---|---|",
         f"| Every header field right | {pct(s['fields_all_right'])} |",
         f"| Every line item right | {pct(s['lines_all_right'])} |",
         f"| Passed the checks on the first rung | {pct(s['passed_checks_first_rung'])} |",
         f"| Escalated to a higher rung | {pct(s['escalated'])} |",
         f"| Could not be read at all | {pct(s['could_not_read'])} |",
         f"| Clean invoices handled with no person ({s['clean_cases']}) | {pct(s['clean_straight_through'])} |",
         f"| Problem invoices sent to a person ({s['messy_cases']}) | {pct(s['messy_sent_to_person'])} |",
         f"| **Dangerous misses** (a problem invoice that went straight through) | **{s['dangerous_misses']}** |",
         f"| Model cost per 1,000 invoices | ${s['cost_per_1000_usd']:.2f} |",
         f"| Time per invoice | {s['seconds_per_invoice']} s |", "",
         "| Field | Right |", "|---|---|"]
    L += [f"| {k} | {pct(v)} |" for k, v in s["field_accuracy"].items()]
    L += ["", "| Problem | Expected | Caught |", "|---|---|---|"]
    L += [f"| {k} | {v['expected']} | {v['caught']} |" for k, v in s["exceptions_by_kind"].items()]
    L += ["", "| Format | Every header field right |", "|---|---|"]
    L += [f"| {k} | {pct(v)} |" for k, v in s["by_format"].items()]
    L += ["", "| Rung | Calls | Tokens in | Tokens out | Cost | Errors |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {v['calls']} | {v['in']:,} | {v['out']:,} | ${v['cost']:.4f} | {v['errors']} |" for k, v in s["by_rung"].items()]
    return "\n".join(L) + "\n"


def estimate(cases, ladder, runs):
    """Rough cost before spending anything: about 4 characters per token for text,
    width × height / 750 tokens for an image, 600 tokens out, every case on every model rung
    (the worst case: nothing passes until the top)."""
    out = {}
    for rung in ladder:
        if rung == "rules":
            continue
        model = ALIASES.get(rung, rung)
        tin = 0
        for c in cases:
            if c["format"] == "pdf":
                tin += len(wf.pdf_text(doc_path(c))) / 4 + len(wf.PROMPT) / 4 + 900
            else:
                w, h = Image.open(doc_path(c)).size
                scale = min(1.0, 1568 / max(w, h))
                tin += (w * scale) * (h * scale) / 750 + len(wf.PROMPT) / 4 + 900
        tout = 600 * len(cases)
        out[model] = round(cost(model, tin, tout) * runs, 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder", default="rules")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--name")
    ap.add_argument("--estimate", action="store_true")
    a = ap.parse_args()
    ladder = [x.strip() for x in a.ladder.split(",")]
    for r in ladder:
        if r != "rules" and ALIASES.get(r, r) not in PRICES:
            sys.exit(f"unknown rung {r}")
    cases = load_cases(a.limit)
    if a.estimate:
        e = estimate(cases, ladder, a.runs)
        print(f"Worst case, every case reaching every model rung, {a.runs} run(s):")
        for m, v in e.items():
            print(f"  {m}: about ${v}")
        print(f"  total at most: about ${sum(e.values()):.2f}")
        return
    global MASTER
    MASTER = wf.load_master()
    name = a.name or a.ladder.replace(",", "-")
    for run in range(1, a.runs + 1):
        label = name if a.runs == 1 else f"{name}-run{run}"
        outdir = HERE / "results" / label
        outdir.mkdir(parents=True, exist_ok=True)
        rows = []
        with open(outdir / "cases.jsonl", "w") as fh:
            for i, c in enumerate(cases, 1):
                r = process(c, ladder)
                sc = score(c, r)
                rows.append({"case": c, "result": r, "score": sc})
                fh.write(json.dumps({"id": c["id"], "result": r, "score": sc}) + "\n")
                if i % 25 == 0:
                    print(f"  {label}: {i}/{len(cases)}", flush=True)
        s = summarise(rows, cases, ladder, label)
        (outdir / "summary.json").write_text(json.dumps(s, indent=1))
        (outdir / "summary.md").write_text(to_md(s))
        print(to_md(s))


if __name__ == "__main__":
    main()
