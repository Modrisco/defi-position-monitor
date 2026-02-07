"""Unit tests for config loading, env interpolation, and validation."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import (
    AppConfig,
    ChainConfig,
    ThresholdsConfig,
    WalletConfig,
    _interpolate_env,
    load_config,
)


class TestInterpolateEnv:
    def test_simple_substitution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_VAR", "hello")
        assert _interpolate_env("${MY_VAR}") == "hello"

    def test_missing_var_becomes_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR_XYZ", raising=False)
        assert _interpolate_env("${NONEXISTENT_VAR_XYZ}") == ""

    def test_nested_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOK", "secret")
        result = _interpolate_env({"key": "${TOK}", "plain": "text"})
        assert result == {"key": "secret", "plain": "text"}

    def test_nested_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("A", "x")
        assert _interpolate_env(["${A}", "y"]) == ["x", "y"]

    def test_non_string_passthrough(self) -> None:
        assert _interpolate_env(42) == 42
        assert _interpolate_env(True) is True


class TestLoadConfig:
    def test_loads_valid_yaml(self, sample_yaml_path: Path) -> None:
        cfg = load_config(sample_yaml_path)
        assert isinstance(cfg, AppConfig)
        assert len(cfg.wallets) == 1
        assert cfg.wallets[0].label == "test-wallet"
        assert cfg.chains["sui"].rpc_timeout == 10
        assert cfg.protocols["alphalend"].liquidation_threshold == 85.0

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_env_interpolation_in_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_ADDR", "0xABCDEF")
        yaml_content = """\
wallets:
  - label: w1
    chain: sui
    address: "${TEST_ADDR}"
    protocols: [alphalend]
chains:
  sui:
    rpc_endpoints: ["https://rpc.test.com"]
protocols:
  alphalend:
    chain: sui
    contracts: {}
    token_decimals: {}
    token_aliases: {}
price_oracle:
  provider: pyth
  pyth:
    hermes_url: "https://hermes.test.com"
    feeds: {}
notifications:
  telegram:
    enabled: false
  email:
    enabled: false
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        cfg = load_config(cfg_file)
        assert cfg.wallets[0].address == "0xABCDEF"


class TestValidation:
    def test_no_wallets_raises(self, tmp_path: Path) -> None:
        yaml_content = """\
wallets: []
chains:
  sui:
    rpc_endpoints: ["https://rpc.test.com"]
protocols: {}
price_oracle:
  provider: pyth
  pyth: {}
notifications:
  telegram: {enabled: false}
  email: {enabled: false}
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        with pytest.raises(ValueError, match="At least one wallet"):
            load_config(cfg_file)

    def test_unknown_chain_raises(self, tmp_path: Path) -> None:
        yaml_content = """\
wallets:
  - label: w
    chain: ethereum
    address: "0x1"
    protocols: []
chains:
  sui:
    rpc_endpoints: ["https://rpc.test.com"]
protocols: {}
price_oracle:
  provider: pyth
  pyth: {}
notifications:
  telegram: {enabled: false}
  email: {enabled: false}
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        with pytest.raises(ValueError, match="unknown chain"):
            load_config(cfg_file)

    def test_unknown_protocol_raises(self, tmp_path: Path) -> None:
        yaml_content = """\
wallets:
  - label: w
    chain: sui
    address: "0x1"
    protocols: [unknown_proto]
chains:
  sui:
    rpc_endpoints: ["https://rpc.test.com"]
protocols: {}
price_oracle:
  provider: pyth
  pyth: {}
notifications:
  telegram: {enabled: false}
  email: {enabled: false}
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        with pytest.raises(ValueError, match="unknown protocol"):
            load_config(cfg_file)

    def test_empty_address_raises(self, tmp_path: Path) -> None:
        yaml_content = """\
wallets:
  - label: w
    chain: sui
    address: ""
    protocols: []
chains:
  sui:
    rpc_endpoints: ["https://rpc.test.com"]
protocols: {}
price_oracle:
  provider: pyth
  pyth: {}
notifications:
  telegram: {enabled: false}
  email: {enabled: false}
"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        with pytest.raises(ValueError, match="no address"):
            load_config(cfg_file)


class TestFrozenConfigs:
    def test_thresholds_immutable(self) -> None:
        t = ThresholdsConfig()
        with pytest.raises(AttributeError):
            t.ltv_warning = 99.0  # type: ignore[misc]

    def test_chain_config_immutable(self) -> None:
        c = ChainConfig(rpc_endpoints=("a",))
        with pytest.raises(AttributeError):
            c.rpc_timeout = 999  # type: ignore[misc]

    def test_wallet_config_immutable(self) -> None:
        w = WalletConfig(label="x", chain="sui", address="0x1")
        with pytest.raises(AttributeError):
            w.label = "y"  # type: ignore[misc]
