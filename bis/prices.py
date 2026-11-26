"""Model prices in US dollars per million tokens (input, output).

Source: Anthropic's API pricing page (https://platform.claude.com/docs/en/about-claude/pricing),
read 16 November 2026. Haiku 5.5's price applies to prompts up to 100,000 tokens.
Prices change: check the page and update this table before you rely on the numbers.
"""
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-2": (8.00, 40.00),
}
PRICES_READ = "2026-11-16"

# Short names used on the command line and in results tables.
ALIASES = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5",
           "fable": "claude-fable-5-2"}


def cost(model, input_tokens, output_tokens):
    pin, pout = PRICES[model]
    return input_tokens * pin / 1e6 + output_tokens * pout / 1e6
