"""Pure parsing functions for AlphaLend position data — no I/O."""
from __future__ import annotations

from typing import Any


def get_token_symbol(coin_type: str) -> str:
    """Extract token symbol from a SUI coin type string.

    Examples:
        "0x2::sui::SUI" → "SUI"
        "0xabc::coin::USDC" → "USDC"
    """
    if "::" in coin_type:
        return coin_type.split("::")[-1].upper()
    return coin_type.upper()


def get_decimals(token_symbol: str, token_decimals: dict[str, int]) -> int:
    """Get token decimals from config, defaulting to 9 (SUI standard)."""
    return token_decimals.get(token_symbol, 9)


def resolve_price(
    token_symbol: str,
    prices: dict[str, float],
    token_aliases: dict[str, str],
) -> float:
    """Resolve the price for a token, falling back to aliases."""
    price = prices.get(token_symbol, 0.0)
    if price == 0.0 and token_symbol in token_aliases:
        price = prices.get(token_aliases[token_symbol], 0.0)
    return price


def parse_collateral_entry(
    entry: dict[str, Any],
    market_info: dict[str, Any],
    prices: dict[str, float],
    token_decimals: dict[str, int],
    token_aliases: dict[str, str],
) -> dict[str, Any]:
    """Parse a single collateral entry into structured data.

    Collaterals are stored as xtoken *shares*. Conversion:
        actual_amount = shares * xtoken_ratio / 10^18 / 10^decimals
    """
    fields = entry.get("fields", {})
    market_id = int(fields.get("key", 0))
    shares = int(fields.get("value", 0))

    coin_type = (
        market_info.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
    )
    symbol = get_token_symbol(coin_type)
    decimals = get_decimals(symbol, token_decimals)

    xtoken_ratio_raw = market_info.get("xtoken_ratio", 10**18)
    if isinstance(xtoken_ratio_raw, dict):
        xtoken_ratio = int(
            xtoken_ratio_raw.get("fields", {}).get("value", 10**18)
        )
    else:
        xtoken_ratio = int(xtoken_ratio_raw)

    amount = (shares * xtoken_ratio) / (10**18) / (10**decimals)
    price = resolve_price(symbol, prices, token_aliases)
    usd_value = amount * price

    return {
        "symbol": symbol,
        "market_id": market_id,
        "amount": amount,
        "price": price,
        "usd_value": usd_value,
    }


def parse_loan_entry(
    entry: dict[str, Any],
    prices: dict[str, float],
    token_decimals: dict[str, int],
    token_aliases: dict[str, str],
) -> dict[str, Any]:
    """Parse a single loan entry into structured data.

    Loans store raw token amounts (not shares):
        actual_amount = raw_amount / 10^decimals
    """
    fields = entry.get("fields", {})
    raw_amount = int(fields.get("amount", 0))

    coin_type = (
        fields.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
    )
    symbol = get_token_symbol(coin_type)
    decimals = get_decimals(symbol, token_decimals)

    amount = raw_amount / (10**decimals)
    price = resolve_price(symbol, prices, token_aliases)
    usd_value = amount * price

    return {
        "symbol": symbol,
        "amount": amount,
        "price": price,
        "usd_value": usd_value,
    }


def calc_ltv(total_collateral_usd: float, total_borrowed_usd: float) -> float:
    """Calculate Loan-to-Value ratio as a percentage."""
    if total_collateral_usd <= 0:
        return 0.0
    return (total_borrowed_usd / total_collateral_usd) * 100


def calc_health_factor(
    total_collateral_usd: float,
    total_borrowed_usd: float,
    liquidation_threshold: float,
) -> float:
    """Calculate health factor.

    health_factor = (collateral * liquidation_threshold%) / borrowed
    """
    if total_borrowed_usd <= 0:
        return float("inf")
    return (total_collateral_usd * liquidation_threshold / 100) / total_borrowed_usd


def build_asset_summary(details: list[dict[str, Any]]) -> str:
    """Build a human-readable summary string for asset details."""
    parts = [
        f"{d['symbol']} ({d['amount']:.4f} @ ${d['price']:,.2f})"
        for d in details
    ]
    return ", ".join(parts) if parts else "N/A"
