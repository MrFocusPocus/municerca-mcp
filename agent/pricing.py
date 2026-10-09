"""USD prices per million tokens, used to estimate the cost of each conversation.

Estimates use list prices for uncached input, so they are an upper bound. A model that is
not in the table needs MUNICERCA_PRICE_IN and MUNICERCA_PRICE_OUT in the environment;
without them the cost is reported as unknown instead of guessed.
"""

from __future__ import annotations

import os

# (input, output) USD per 1M tokens.
# DeepSeek: peak, cache miss prices from api-docs.deepseek.com/quick_start/pricing, read 2026-10-09.
PRICES: dict[str, tuple[float, float]] = {
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
}


def price_for(model: str) -> tuple[float, float] | None:
    price_in = os.environ.get("MUNICERCA_PRICE_IN")
    price_out = os.environ.get("MUNICERCA_PRICE_OUT")
    if price_in and price_out:
        return float(price_in), float(price_out)
    return PRICES.get(model)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = price_for(model)
    if price is None:
        return None
    return round((input_tokens * price[0] + output_tokens * price[1]) / 1_000_000, 6)
