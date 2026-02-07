"""Configuration loader — reads config.yaml, interpolates env vars, validates."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frozen config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdsConfig:
    ltv_warning: float = 70.0
    ltv_critical: float = 80.0


@dataclass(frozen=True)
class MonitorConfig:
    check_interval_minutes: int = 15
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)


@dataclass(frozen=True)
class WalletConfig:
    label: str = ""
    chain: str = ""
    address: str = ""
    protocols: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChainConfig:
    rpc_endpoints: tuple[str, ...] = ()
    rpc_timeout: int = 30


@dataclass(frozen=True)
class ProtocolConfig:
    chain: str = ""
    contracts: dict[str, str] = field(default_factory=dict)
    liquidation_threshold: float = 85.0
    token_decimals: dict[str, int] = field(default_factory=dict)
    token_aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PythConfig:
    hermes_url: str = "https://hermes.pyth.network/v2/updates/price/latest"
    feeds: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PriceOracleConfig:
    provider: str = "pyth"
    pyth: PythConfig = field(default_factory=PythConfig)


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool = False
    alert_bot_token: str = ""
    log_bot_token: str = ""
    chat_id: str = ""


@dataclass(frozen=True)
class EmailConfig:
    enabled: bool = False
    alert_email: str = ""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = ""
    sender_password: str = ""


@dataclass(frozen=True)
class NotificationsConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    email: EmailConfig = field(default_factory=EmailConfig)


@dataclass(frozen=True)
class AppConfig:
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    wallets: tuple[WalletConfig, ...] = ()
    chains: dict[str, ChainConfig] = field(default_factory=dict)
    protocols: dict[str, ProtocolConfig] = field(default_factory=dict)
    price_oracle: PriceOracleConfig = field(default_factory=PriceOracleConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)


# ---------------------------------------------------------------------------
# Env interpolation
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)}")


def _interpolate_env(value: Any) -> Any:
    """Recursively replace ${VAR} references with environment variable values."""
    if isinstance(value, str):
        return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# YAML → dataclass builders
# ---------------------------------------------------------------------------


def _build_thresholds(raw: dict[str, Any]) -> ThresholdsConfig:
    return ThresholdsConfig(
        ltv_warning=float(raw.get("ltv_warning", 70.0)),
        ltv_critical=float(raw.get("ltv_critical", 80.0)),
    )


def _build_monitor(raw: dict[str, Any]) -> MonitorConfig:
    return MonitorConfig(
        check_interval_minutes=int(raw.get("check_interval_minutes", 15)),
        thresholds=_build_thresholds(raw.get("thresholds", {})),
    )


def _build_wallets(raw: list[dict[str, Any]]) -> tuple[WalletConfig, ...]:
    wallets: list[WalletConfig] = []
    for w in raw:
        wallets.append(
            WalletConfig(
                label=w.get("label", ""),
                chain=w.get("chain", ""),
                address=w.get("address", ""),
                protocols=tuple(w.get("protocols", [])),
            )
        )
    return tuple(wallets)


def _build_chains(raw: dict[str, Any]) -> dict[str, ChainConfig]:
    chains: dict[str, ChainConfig] = {}
    for name, cfg in raw.items():
        chains[name] = ChainConfig(
            rpc_endpoints=tuple(cfg.get("rpc_endpoints", [])),
            rpc_timeout=int(cfg.get("rpc_timeout", 30)),
        )
    return chains


def _build_protocols(raw: dict[str, Any]) -> dict[str, ProtocolConfig]:
    protocols: dict[str, ProtocolConfig] = {}
    for name, cfg in raw.items():
        protocols[name] = ProtocolConfig(
            chain=cfg.get("chain", ""),
            contracts=dict(cfg.get("contracts", {})),
            liquidation_threshold=float(cfg.get("liquidation_threshold", 85.0)),
            token_decimals=dict(cfg.get("token_decimals", {})),
            token_aliases=dict(cfg.get("token_aliases", {})),
        )
    return protocols


def _build_price_oracle(raw: dict[str, Any]) -> PriceOracleConfig:
    pyth_raw = raw.get("pyth", {})
    return PriceOracleConfig(
        provider=raw.get("provider", "pyth"),
        pyth=PythConfig(
            hermes_url=pyth_raw.get("hermes_url", PythConfig.hermes_url),
            feeds=dict(pyth_raw.get("feeds", {})),
        ),
    )


def _build_notifications(raw: dict[str, Any]) -> NotificationsConfig:
    tg = raw.get("telegram", {})
    em = raw.get("email", {})
    return NotificationsConfig(
        telegram=TelegramConfig(
            enabled=bool(tg.get("enabled", False)),
            alert_bot_token=tg.get("alert_bot_token", ""),
            log_bot_token=tg.get("log_bot_token", ""),
            chat_id=tg.get("chat_id", ""),
        ),
        email=EmailConfig(
            enabled=bool(em.get("enabled", False)),
            alert_email=em.get("alert_email", ""),
            smtp_server=em.get("smtp_server", "smtp.gmail.com"),
            smtp_port=int(em.get("smtp_port", 587)),
            sender_email=em.get("sender_email", ""),
            sender_password=em.get("sender_password", ""),
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load and validate application configuration from YAML + .env.

    Args:
        config_path: Path to config.yaml. Defaults to ``config.yaml`` in the
            project root (two levels up from this file).
    """
    load_dotenv()

    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    raw = _interpolate_env(raw)

    cfg = AppConfig(
        monitor=_build_monitor(raw.get("monitor", {})),
        wallets=_build_wallets(raw.get("wallets", [])),
        chains=_build_chains(raw.get("chains", {})),
        protocols=_build_protocols(raw.get("protocols", {})),
        price_oracle=_build_price_oracle(raw.get("price_oracle", {})),
        notifications=_build_notifications(raw.get("notifications", {})),
    )

    _validate(cfg)
    logger.info("Configuration loaded from %s", config_path)
    return cfg


def _validate(cfg: AppConfig) -> None:
    """Raise on invalid configuration."""
    if not cfg.wallets:
        raise ValueError("At least one wallet must be configured")

    for wallet in cfg.wallets:
        if not wallet.address:
            raise ValueError(f"Wallet '{wallet.label}' has no address")
        if wallet.chain not in cfg.chains:
            raise ValueError(
                f"Wallet '{wallet.label}' references unknown chain '{wallet.chain}'"
            )
        for proto in wallet.protocols:
            if proto not in cfg.protocols:
                raise ValueError(
                    f"Wallet '{wallet.label}' references unknown protocol '{proto}'"
                )
