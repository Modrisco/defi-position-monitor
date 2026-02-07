# DeFi Position Monitor

Universal DeFi position monitor — multi-chain, multi-protocol, multi-wallet.

Currently supports:
- **Chain:** SUI
- **Protocol:** AlphaLend (Bluefin)
- **Price Oracle:** Pyth Network
- **Notifications:** Telegram (dual-bot), Email (SMTP)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in secrets
cp .env.example .env

# 3. Review / customise config
#    (config.yaml is ready to use; secrets are interpolated from .env)
cat config.yaml

# 4. Run a single check
python3 -m src check

# 5. Generate a daily report
python3 -m src report

# 6. Continuous monitoring
python3 -m src monitor          # uses interval from config.yaml
python3 -m src monitor 10       # override: check every 10 minutes
```

## Configuration

| File | Purpose |
|------|---------|
| `config.yaml` | All non-secret configuration: chains, protocols, wallets, thresholds, oracle feeds |
| `.env` | Secrets only: wallet addresses, API tokens, passwords |
| `config.yaml.example` | Documented template (no real values) |
| `.env.example` | Documented template for secrets |

Secrets in `config.yaml` are referenced as `${ENV_VAR_NAME}` and interpolated at startup.

## Architecture

```
src/
├── cli.py                  # argparse CLI
├── config.py               # YAML loader + frozen config dataclasses
├── logging_setup.py        # Logging configuration
├── models.py               # PositionData, AssetDetail (frozen dataclasses)
├── interfaces/             # typing.Protocol definitions
│   ├── chain.py            # ChainClient
│   ├── protocol_adapter.py # ProtocolAdapter
│   ├── price_oracle.py     # PriceOracle
│   └── notifier.py         # Notifier
├── chains/sui/client.py    # SuiClient (RPC with fallback)
├── protocols/alphalend/    # AlphaLend adapter + pure parser
├── oracles/pyth.py         # Pyth Network oracle
├── notifications/          # Telegram + Email notifiers
└── services/monitor.py     # Generic orchestrator
```

### Adding a New Protocol

1. Create `src/protocols/<name>/adapter.py` implementing `ProtocolAdapter`
2. Add the protocol config section to `config.yaml`
3. Register the adapter factory in `src/services/monitor.py`

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing
```

## GitHub Actions

- **DeFi Position Monitor** — runs `python3 -m src check` every 15 minutes
- **Daily Position Report** — runs `python3 -m src report` daily at 8 AM Sydney time
