# DeFi Position Monitor

Universal DeFi position monitor — multi-chain, multi-protocol, multi-wallet.

Currently supports:
- **Chain:** SUI
- **Protocol:** AlphaLend (Bluefin)
- **Price Oracle:** Pyth Network
- **Notifications:** Telegram (dual-bot), Email (SMTP)

## Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/defi-position-monitor.git
cd defi-position-monitor

# 2. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 3. Copy and fill in your secrets
cp .env.example .env
# Edit .env — add your SUI wallet address(es), Telegram bot tokens, etc.

# 4. Copy the config template (or use config.yaml directly)
cp config.yaml.example config.yaml
# Edit config.yaml — adjust wallets, thresholds, and notification settings

# 5. Run a single health check
python3 -m src check

# 6. Generate a daily report
python3 -m src report

# 7. Continuous monitoring (runs in foreground)
python3 -m src monitor          # uses interval from config.yaml
python3 -m src monitor 10       # override: check every 10 minutes
```

## Fork & Deploy with GitHub Actions

If you want automated monitoring without running a server, fork this repo and use GitHub Actions:

1. **Fork** this repository to your own GitHub account.

2. **Add secrets** in your fork: go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   | Secret | Description |
   |--------|-------------|
   | `SUI_WALLET_ADDRESS` | Your primary SUI wallet address |
   | `SUI_WALLET_ADDRESS_2` | (Optional) Second SUI wallet address |
   | `TELEGRAM_ALERT_BOT_TOKEN` | Telegram bot token for unmuted alerts |
   | `TELEGRAM_LOG_BOT_TOKEN` | Telegram bot token for silent log messages |
   | `TELEGRAM_CHAT_ID` | Telegram chat ID to receive notifications |

3. **Enable Actions** in your fork: go to the **Actions** tab and click "I understand my workflows, go ahead and enable them".

4. **Trigger a test run**: on the Actions tab, select either workflow and click **Run workflow** to verify everything works.

Two workflows are included out of the box:
- **DeFi Position Monitor** — runs `python3 -m src check` every 15 minutes
- **Daily Position Report** — runs `python3 -m src report` daily at 8 AM Sydney time

You can customise the schedule by editing the `cron` expressions in `.github/workflows/`.

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

