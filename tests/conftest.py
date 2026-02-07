"""Shared test fixtures and sample data."""
from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from src.config import (
    AppConfig,
    ChainConfig,
    EmailConfig,
    MonitorConfig,
    NotificationsConfig,
    PriceOracleConfig,
    ProtocolConfig,
    PythConfig,
    TelegramConfig,
    ThresholdsConfig,
    WalletConfig,
)
from src.models import AssetDetail, PositionData


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_thresholds() -> ThresholdsConfig:
    return ThresholdsConfig(ltv_warning=70.0, ltv_critical=80.0)


@pytest.fixture()
def sample_chain_config() -> ChainConfig:
    return ChainConfig(
        rpc_endpoints=("https://rpc1.example.com", "https://rpc2.example.com"),
        rpc_timeout=10,
    )


@pytest.fixture()
def sample_protocol_config() -> ProtocolConfig:
    return ProtocolConfig(
        chain="sui",
        contracts={
            "lending_protocol_id": "0xabc",
            "package_id": "0xdef",
            "positions_table_id": "0x111",
            "markets_table_id": "0x222",
        },
        liquidation_threshold=85.0,
        token_decimals={"SUI": 9, "USDC": 6, "BTC": 8, "XBTC": 8},
        token_aliases={"XBTC": "BTC"},
    )


@pytest.fixture()
def sample_pyth_config() -> PythConfig:
    return PythConfig(
        hermes_url="https://hermes.pyth.network/v2/updates/price/latest",
        feeds={"SUI": "abc123", "BTC": "def456", "USDC": "ghi789"},
    )


@pytest.fixture()
def sample_app_config(
    sample_thresholds: ThresholdsConfig,
    sample_chain_config: ChainConfig,
    sample_protocol_config: ProtocolConfig,
    sample_pyth_config: PythConfig,
) -> AppConfig:
    return AppConfig(
        monitor=MonitorConfig(check_interval_minutes=5, thresholds=sample_thresholds),
        wallets=(
            WalletConfig(
                label="test-wallet",
                chain="sui",
                address="0xWALLET123",
                protocols=("alphalend",),
            ),
        ),
        chains={"sui": sample_chain_config},
        protocols={"alphalend": sample_protocol_config},
        price_oracle=PriceOracleConfig(provider="pyth", pyth=sample_pyth_config),
        notifications=NotificationsConfig(
            telegram=TelegramConfig(
                enabled=True,
                alert_bot_token="fake-alert-token",
                log_bot_token="fake-log-token",
                chat_id="12345",
            ),
            email=EmailConfig(enabled=False),
        ),
    )


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_position() -> PositionData:
    return PositionData(
        collateral_value=10000.0,
        borrowed_value=5000.0,
        ltv=50.0,
        health_factor=1.7,
        liquidation_threshold=85.0,
        asset="SUI (100.0000 @ $100.00)",
        borrowed_asset="USDC (5000.0000 @ $1.00)",
        protocol_name="alphalend",
        wallet_label="test-wallet",
        collateral_assets=(
            AssetDetail(symbol="SUI", amount=100.0, price=100.0, usd_value=10000.0),
        ),
        borrowed_assets=(
            AssetDetail(symbol="USDC", amount=5000.0, price=1.0, usd_value=5000.0),
        ),
    )


# ---------------------------------------------------------------------------
# Config YAML fixture
# ---------------------------------------------------------------------------

SAMPLE_YAML = textwrap.dedent("""\
    monitor:
      check_interval_minutes: 5
      thresholds:
        ltv_warning: 70.0
        ltv_critical: 80.0
    wallets:
      - label: test-wallet
        chain: sui
        address: "0xTEST"
        protocols: [alphalend]
    chains:
      sui:
        rpc_endpoints: ["https://rpc.example.com"]
        rpc_timeout: 10
    protocols:
      alphalend:
        chain: sui
        contracts:
          lending_protocol_id: "0xabc"
          package_id: "0xdef"
          positions_table_id: "0x111"
          markets_table_id: "0x222"
        liquidation_threshold: 85.0
        token_decimals: {SUI: 9, USDC: 6}
        token_aliases: {XBTC: BTC}
    price_oracle:
      provider: pyth
      pyth:
        hermes_url: "https://hermes.example.com"
        feeds: {SUI: "aaa", BTC: "bbb"}
    notifications:
      telegram:
        enabled: true
        alert_bot_token: "tok1"
        log_bot_token: "tok2"
        chat_id: "999"
      email:
        enabled: false
""")


@pytest.fixture()
def sample_yaml_path(tmp_path: Path) -> Path:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(SAMPLE_YAML)
    return cfg_file


# ---------------------------------------------------------------------------
# Sample on-chain data
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_collateral_entry() -> dict:
    return {
        "fields": {
            "key": "1",
            "value": "500000000000",  # 500 SUI in raw shares
        }
    }


@pytest.fixture()
def sample_market_info() -> dict:
    return {
        "coin_type": {"fields": {"name": "0x2::sui::SUI"}},
        "xtoken_ratio": {"fields": {"value": str(10**18)}},
    }


@pytest.fixture()
def sample_loan_entry() -> dict:
    return {
        "fields": {
            "amount": "5000000000",  # 5000 USDC (6 decimals)
            "coin_type": {"fields": {"name": "0xabc::coin::USDC"}},
        }
    }


@pytest.fixture()
def sample_prices() -> dict[str, float]:
    return {"SUI": 3.50, "BTC": 100000.0, "USDC": 1.0, "USDT": 1.0, "ETH": 3500.0}
