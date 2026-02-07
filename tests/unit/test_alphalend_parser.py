"""Unit tests for AlphaLend parser — pure functions, no I/O."""
from __future__ import annotations

import math

import pytest

from src.protocols.alphalend.parser import (
    build_asset_summary,
    calc_health_factor,
    calc_ltv,
    get_decimals,
    get_token_symbol,
    parse_collateral_entry,
    parse_loan_entry,
    resolve_price,
)

TOKEN_DECIMALS = {"SUI": 9, "USDC": 6, "BTC": 8, "XBTC": 8}
TOKEN_ALIASES = {"XBTC": "BTC"}
PRICES = {"SUI": 3.50, "BTC": 100000.0, "USDC": 1.0}


# ---------------------------------------------------------------------------
# get_token_symbol
# ---------------------------------------------------------------------------


class TestGetTokenSymbol:
    def test_full_coin_type(self) -> None:
        assert get_token_symbol("0x2::sui::SUI") == "SUI"

    def test_nested_module(self) -> None:
        assert get_token_symbol("0xabc::coin::USDC") == "USDC"

    def test_plain_string(self) -> None:
        assert get_token_symbol("eth") == "ETH"

    def test_empty_string(self) -> None:
        assert get_token_symbol("") == ""


# ---------------------------------------------------------------------------
# get_decimals
# ---------------------------------------------------------------------------


class TestGetDecimals:
    def test_known_token(self) -> None:
        assert get_decimals("USDC", TOKEN_DECIMALS) == 6

    def test_unknown_token_defaults_9(self) -> None:
        assert get_decimals("UNKNOWN", TOKEN_DECIMALS) == 9


# ---------------------------------------------------------------------------
# resolve_price
# ---------------------------------------------------------------------------


class TestResolvePrice:
    def test_direct_match(self) -> None:
        assert resolve_price("SUI", PRICES, TOKEN_ALIASES) == 3.50

    def test_alias_fallback(self) -> None:
        assert resolve_price("XBTC", PRICES, TOKEN_ALIASES) == 100000.0

    def test_unknown_returns_zero(self) -> None:
        assert resolve_price("DOGE", PRICES, TOKEN_ALIASES) == 0.0


# ---------------------------------------------------------------------------
# calc_ltv / calc_health_factor
# ---------------------------------------------------------------------------


class TestCalcLtv:
    def test_basic(self) -> None:
        assert calc_ltv(10000.0, 5000.0) == pytest.approx(50.0)

    def test_zero_collateral(self) -> None:
        assert calc_ltv(0.0, 5000.0) == 0.0

    def test_no_borrowed(self) -> None:
        assert calc_ltv(10000.0, 0.0) == 0.0


class TestCalcHealthFactor:
    def test_basic(self) -> None:
        hf = calc_health_factor(10000.0, 5000.0, 85.0)
        assert hf == pytest.approx(1.7)

    def test_no_borrowed_returns_inf(self) -> None:
        assert math.isinf(calc_health_factor(10000.0, 0.0, 85.0))

    def test_high_ltv(self) -> None:
        hf = calc_health_factor(10000.0, 8500.0, 85.0)
        assert hf == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# parse_collateral_entry
# ---------------------------------------------------------------------------


class TestParseCollateralEntry:
    def test_basic_parsing(
        self, sample_collateral_entry: dict, sample_market_info: dict
    ) -> None:
        result = parse_collateral_entry(
            sample_collateral_entry,
            sample_market_info,
            PRICES,
            TOKEN_DECIMALS,
            TOKEN_ALIASES,
        )
        assert result["symbol"] == "SUI"
        # 500_000_000_000 shares * (10^18 / 10^18) / 10^9 = 500.0 SUI
        assert result["amount"] == pytest.approx(500.0)
        assert result["price"] == pytest.approx(3.50)
        assert result["usd_value"] == pytest.approx(1750.0)

    def test_zero_shares(self, sample_market_info: dict) -> None:
        entry = {"fields": {"key": "1", "value": "0"}}
        result = parse_collateral_entry(
            entry, sample_market_info, PRICES, TOKEN_DECIMALS, TOKEN_ALIASES
        )
        assert result["amount"] == 0.0
        assert result["usd_value"] == 0.0


# ---------------------------------------------------------------------------
# parse_loan_entry
# ---------------------------------------------------------------------------


class TestParseLoanEntry:
    def test_basic_parsing(self, sample_loan_entry: dict) -> None:
        result = parse_loan_entry(
            sample_loan_entry, PRICES, TOKEN_DECIMALS, TOKEN_ALIASES
        )
        assert result["symbol"] == "USDC"
        # 5_000_000_000 / 10^6 = 5000.0
        assert result["amount"] == pytest.approx(5000.0)
        assert result["price"] == pytest.approx(1.0)
        assert result["usd_value"] == pytest.approx(5000.0)


# ---------------------------------------------------------------------------
# build_asset_summary
# ---------------------------------------------------------------------------


class TestBuildAssetSummary:
    def test_single_asset(self) -> None:
        details = [{"symbol": "SUI", "amount": 100.0, "price": 3.50}]
        summary = build_asset_summary(details)
        assert "SUI" in summary
        assert "100.0000" in summary

    def test_empty(self) -> None:
        assert build_asset_summary([]) == "N/A"

    def test_multiple_assets(self) -> None:
        details = [
            {"symbol": "SUI", "amount": 10.0, "price": 3.50},
            {"symbol": "USDC", "amount": 500.0, "price": 1.0},
        ]
        summary = build_asset_summary(details)
        assert "SUI" in summary
        assert "USDC" in summary
        assert ", " in summary
