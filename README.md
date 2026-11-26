# Build It Small

Practical AI processes for everyday business jobs, built on the cheapest tool that does each step properly. This is the free kit that goes with the **Build It Small** articles on LinkedIn.

## The idea, in one picture

Every task starts on the bottom step and only moves up if it has to:

1. **Simple rules:** free. Adding up, VAT, lookups.
2. **Cheap AI:** cents. Reading the paperwork.
3. **Expensive AI:** only when the cheap one's answer fails a check.
4. **A person:** the decisions. Approving, signing, paying.

A check is ordinary software asking whether an answer holds together: is everything there, do the sums add up, is this a supplier we know? If the cheap AI's answer passes, it's used. If not, it goes up a step.

## Playbook 1: supplier invoices

Folder: `playbooks/invoices/`

**What's in it:**

- **200 practice invoices** (`cases/`) in six layouts: 140 emailed PDFs, 40 scans and 20 phone photos, in English and Afrikaans, with amounts written in the ways South African suppliers write them.
- **The right answers** for each one (`cases/*.truth.json`): what's printed on it, and what a good process should do with it.
- **66 of them have one problem each**, the kind a person must catch:
  - a changed bank account
  - a duplicate
  - a credit note
  - a price above the purchase order
  - an unknown supplier
  - a missing VAT number
  - wrong sums on the invoice itself
  - no purchase order
- **The instructions for the AI** (`prompt.md`).
- **The process** (`workflow.py`): the form the AI fills in, the checks, the matching against suppliers, purchase orders and payment history, and the list of reasons an invoice goes to a person.
- **A practice bench** (`bench.py`). It runs the invoices through your chosen steps, compares every answer with the right one, counts how many problem invoices slipped through, and adds up what each call costs.

Every company, bank, VAT number and account number in it is invented. There is no real data in this kit.

**The one rule that never goes to AI:** if the bank details on an invoice don't match the ones on file, a person phones the supplier on a number you already have.

## Using it

You don't need to run any code to use the practice invoices. Open `playbooks/invoices/cases/`, pick an invoice, and compare it with its `.truth.json` file.

To run the bench you need Python 3.10 or later and `pdftotext` (part of Poppler: `brew install poppler` on a Mac, `apt install poppler-utils` on Linux).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd playbooks/invoices
../../.venv/bin/python bench.py --ladder rules                      # simple rules only, free
../../.venv/bin/python bench.py --ladder haiku,opus --estimate      # rough cost before you spend anything
../../.venv/bin/python bench.py --ladder rules,haiku,opus           # the full ladder, needs your own API key
```

The AI steps call Anthropic's API and cost money. Make an API key just for this, with a monthly spend limit, then run `.venv/bin/python -m bis.setup` from the top folder. It asks for the key without showing it and stores it in `~/.config/build-it-small/anthropic.env`, readable only by you.

Results go to `playbooks/invoices/results/`. The number that matters most is **dangerous misses**: invoices with a problem that went straight through without a person seeing them. It must be zero before anything handles real invoices.

To make a fresh set of practice invoices (optional; needs Node.js):

```bash
npm install && npx playwright install chromium     # from the top folder
cd playbooks/invoices
../../.venv/bin/python generate.py
node render.mjs
../../.venv/bin/python degrade.py
```

## Honest notes

- **No results are claimed here.** The articles give rough cost estimates from Anthropic's published prices (November 2026). They are not measured results. Run the bench on your own key to get your own numbers.
- **Prices change.** Check `bis/prices.py` against Anthropic's pricing page before relying on any cost figure.
- **The checks are a starting point, not tax or legal advice.** South African VAT is 15% and SARS says "Without a proper tax invoice a business cannot deduct input tax". Your own accountant has the final word.

## Want it built for you?

If you'd rather have this built and connected to your own accounting system, message Christopher van der Westhuizen on LinkedIn.

## Licence

MIT. See `LICENSE`.
