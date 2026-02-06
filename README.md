# Bluefin AlphaLend Position Monitor

Automated monitoring system for your Bluefin AlphaLend lending positions on SUI blockchain. Get real-time alerts when your LTV ratio reaches dangerous levels.

## Features

- **Real-time Price Calculation** - Uses Pyth Network oracle for accurate USD values
- **Dual Telegram Bots** - Separate bots for critical alerts (unmuted) and logs (can mute)
- **RPC Fallback** - Automatic failover between 3 RPC endpoints
- **GitHub Actions** - Scheduled monitoring every 15 minutes (free)
- **Modular Architecture** - Clean, testable code structure

## Project Structure

```
src/
├── config.py              # Configuration & constants
├── main.py                # Entry point
├── models.py              # Data classes
├── rpc/
│   └── sui_client.py      # SUI RPC with fallback
├── services/
│   ├── monitor.py         # Main orchestration
│   ├── position_service.py # Position fetching
│   └── price_service.py   # Pyth prices
└── notifications/
    ├── telegram.py        # Alert & log bots
    └── email.py           # Email notifications
```

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Required
SUI_WALLET_ADDRESS=0xYourWalletAddress

# Telegram (Recommended)
TELEGRAM_ALERT_BOT_TOKEN=your-alert-bot-token   # Keep unmuted!
TELEGRAM_LOG_BOT_TOKEN=your-log-bot-token       # Can mute
TELEGRAM_CHAT_ID=your-chat-id

# Optional - Alert thresholds
LTV_WARNING_THRESHOLD=70    # Warning at 70%
LTV_CRITICAL_THRESHOLD=80   # Critical at 80%
```

### 3. Run

```bash
# One-time check (sends log + alerts if needed)
python3 -m src.main check

# Generate daily report
python3 -m src.main report

# Continuous monitoring
python3 -m src.main monitor [minutes]
```

## Telegram Setup (Dual Bot System)

We use **two separate bots** for better notification management:

| Bot | Purpose | Keep Unmuted? |
|-----|---------|---------------|
| **Alert Bot** | Critical alerts (LTV ≥ 70%) | ✅ Yes - never miss these |
| **Log Bot** | Regular status updates | Optional - can mute |

### Create Both Bots

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` twice to create:
   - `YourName_Alert_Bot` (for critical alerts)
   - `YourName_Log_Bot` (for regular logs)
3. Copy both tokens to `.env`

### Get Your Chat ID

1. Message either bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789}` - this is your `TELEGRAM_CHAT_ID`

## GitHub Actions Deployment (Recommended)

Free scheduled monitoring using GitHub Actions.

### 1. Add Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value |
|--------|-------|
| `SUI_WALLET_ADDRESS` | Your wallet address |
| `TELEGRAM_ALERT_BOT_TOKEN` | Alert bot token |
| `TELEGRAM_LOG_BOT_TOKEN` | Log bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID |

### 2. Workflow

The workflow runs every 15 minutes (`.github/workflows/monitor.yml`):

```yaml
name: Bluefin Position Monitor

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - name: Run position monitor
        env:
          SUI_WALLET_ADDRESS: ${{ secrets.SUI_WALLET_ADDRESS }}
          TELEGRAM_ALERT_BOT_TOKEN: ${{ secrets.TELEGRAM_ALERT_BOT_TOKEN }}
          TELEGRAM_LOG_BOT_TOKEN: ${{ secrets.TELEGRAM_LOG_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 -m src.main check
```

### 3. Manual Test

Go to **Actions** → **Bluefin Position Monitor** → **Run workflow**

## How It Works

### Real-time Price Calculation

Values are calculated using current Pyth Network prices:

```
Collateral USD = Σ (token_shares × xtoken_ratio × price)
Borrowed USD   = Σ (borrowed_amount × price)
LTV            = Borrowed USD / Collateral USD × 100
```

**Key insight**: Collaterals are stored as **shares (xtokens)**, not actual tokens. The `xtoken_ratio` converts shares to actual tokens (including accrued interest).

### Sample Output

```
============================================================
POSITION SUMMARY (Real-time prices)
============================================================
  Position ID: 0x0ad0d437...

  Collateral Assets:
    - USDC: 3937.74 × $1.00 = $3,937.12
    - XBTC: 0.0170 × $65,209.32 = $1,108.71
  Total Collateral:     $5,045.83

  Borrowed Assets:
    - SUI: 2601.00 × $0.92 = $2,402.24
  Total Borrowed:       $2,402.24

  LTV:                  47.61%
  Health Factor:        1.79
  Liquidation Threshold: 85.00%

  Position Healthy:     Yes
  Liquidatable:         No
============================================================
```

### Alert Thresholds

| LTV Level | Status | Action |
|-----------|--------|--------|
| < 50% | ✅ Safe | Log only |
| 50-70% | ✅ Moderate | Log only |
| 70-80% | ⚠️ Warning | Alert + Log |
| > 80% | 🚨 Critical | Alert + Log |

## RPC Endpoints

The client automatically fails over between endpoints:

1. `https://fullnode.mainnet.sui.io:443` (default)
2. `https://sui-mainnet.nodeinfra.com` (fallback)
3. `https://sui-mainnet-endpoint.blockvision.org` (fallback)

## Technical Details

### Contract Addresses (SUI Mainnet)

| Contract | Address |
|----------|---------|
| AlphaLend Package | `0xd631cd66138909636fc3f73ed75820d0c5b76332d1644608ed1c85ea2b8219b4` |
| Lending Protocol | `0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93` |
| Positions Table | `0x9923cec7b613e58cc3feec1e8651096ad7970c0b4ef28b805c7d97fe58ff91ba` |
| Markets Table | `0x2326d387ba8bb7d24aa4cfa31f9a1e58bf9234b097574afb06c5dfb267df4c2e` |

### Pyth Price Feed IDs

| Asset | Feed ID |
|-------|---------|
| SUI | `23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744` |
| BTC/XBTC | `e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43` |
| USDC | `eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a` |
| USDT | `2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b` |
| ETH | `ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace` |

### Token Decimals

| Token | Decimals |
|-------|----------|
| SUI | 9 |
| USDC | 6 |
| USDT | 6 |
| BTC/XBTC | 8 |
| ETH | 8 |

## Alternative Deployment Options

### Local Cron (Linux/Mac)

```bash
# Every 15 minutes
*/15 * * * * cd /path/to/project && ./venv/bin/python3 -m src.main check
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY .env .
CMD ["python3", "-m", "src.main", "monitor", "15"]
```

```bash
docker build -t bluefin-monitor .
docker run -d --restart unless-stopped bluefin-monitor
```

### systemd (Linux)

```ini
[Unit]
Description=Bluefin AlphaLend Position Monitor
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python3 -m src.main monitor 15
Restart=always

[Install]
WantedBy=multi-user.target
```

## Resources

- [Bluefin Docs](https://learn.bluefin.io)
- [AlphaLend Docs](https://docs.alphafi.xyz/alphalend)
- [Pyth Network](https://www.pyth.network)
- [SUI Docs](https://docs.sui.io)

## Security Notes

- Never commit `.env` to git
- Use GitHub Secrets for CI/CD
- No private keys needed (read-only monitoring)
- Restrict file permissions: `chmod 600 .env`

## License

MIT License
