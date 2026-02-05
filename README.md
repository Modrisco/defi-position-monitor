# Bluefin AlphaLend Position Monitor

Automated monitoring system for your Bluefin AlphaLend lending positions on SUI blockchain. Get real-time alerts when your LTV ratio reaches dangerous levels and receive daily position reports.

## Features

✅ **Automated LTV Monitoring** - Continuously check your loan-to-value ratio  
✅ **Multi-Channel Alerts** - Email and Telegram notifications  
✅ **Daily Reports** - Automated daily position summaries  
✅ **Customizable Thresholds** - Set your own warning and critical LTV levels  
✅ **Health Factor Tracking** - Monitor liquidation risk in real-time  

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example configuration:
```bash
cp .env.example .env
```

Edit `.env` with your details:
```bash
# Required
SUI_WALLET_ADDRESS=0xYourWalletAddressHere
ALERT_EMAIL=your-email@example.com

# For Email Alerts (using Gmail)
SENDER_EMAIL=your-gmail@gmail.com
SENDER_PASSWORD=your-app-password
```

### 3. Setup Email Alerts (Gmail)

If using Gmail for alerts:
1. Go to Google Account → Security
2. Enable 2-Step Verification
3. Create an App Password:
   - Go to Security → 2-Step Verification → App passwords
   - Select "Mail" and "Other (Custom name)"
   - Copy the 16-character password
   - Use this as `SENDER_PASSWORD` in `.env`

### 4. Setup Telegram Alerts (Optional)

1. Create a Telegram bot:
   - Message [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. Get your Chat ID:
   - Message your bot
   - Visit: `https://api.telegram.org/bot<YourBOTToken>/getUpdates`
   - Find your `chat_id` in the response

3. Add to `.env`:
```bash
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

## Usage

### One-Time Position Check

Check your positions immediately:
```bash
python bluefin_monitor.py check
```

### Generate Daily Report

Create a comprehensive position report:
```bash
python bluefin_monitor.py report
```

### Continuous Monitoring

Run continuous monitoring (checks every 15 minutes by default):
```bash
python bluefin_monitor.py monitor
```

Custom check interval (in minutes):
```bash
python bluefin_monitor.py monitor 30  # Check every 30 minutes
```

## Automated Daily Reports

### Linux/Mac (Cron)

Add to your crontab (`crontab -e`):

```bash
# Daily report at 8 AM
0 8 * * * cd /path/to/monitor && /usr/bin/python3 bluefin_monitor.py report

# Continuous monitoring (restart if stopped)
*/15 * * * * cd /path/to/monitor && pgrep -f bluefin_monitor.py || /usr/bin/python3 bluefin_monitor.py monitor &
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 8:00 AM
4. Action: Start a program
   - Program: `python.exe`
   - Arguments: `bluefin_monitor.py report`
   - Start in: Path to your monitor directory

## Running as a Service

### Using systemd (Linux)

Create `/etc/systemd/system/bluefin-monitor.service`:

```ini
[Unit]
Description=Bluefin AlphaLend Position Monitor
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/monitor
ExecStart=/usr/bin/python3 /path/to/monitor/bluefin_monitor.py monitor 15
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable bluefin-monitor
sudo systemctl start bluefin-monitor
sudo systemctl status bluefin-monitor
```

### Using Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bluefin_monitor.py .
COPY .env .

CMD ["python", "bluefin_monitor.py", "monitor", "15"]
```

Build and run:
```bash
docker build -t bluefin-monitor .
docker run -d --name bluefin-monitor --restart unless-stopped bluefin-monitor
```

## Alert Examples

### Warning Alert (LTV ≥ 70%)
```
⚠️ WARNING: Elevated LTV Ratio

Your Bluefin AlphaLend position LTV is getting high:
- Current LTV: 72.50%
- Health Factor: 1.17
- Liquidation Threshold: 85.00%

Consider adding collateral or reducing your borrowed amount.
```

### Critical Alert (LTV ≥ 80%)
```
🚨 CRITICAL ALERT: High LTV Ratio!

Your Bluefin AlphaLend position has reached a critical LTV level:
- Current LTV: 82.00%
- Health Factor: 1.04
- Liquidation Threshold: 85.00%

⚠️ ACTION REQUIRED: Add more collateral or repay debt immediately!
```

## Customization

### Adjust Alert Thresholds

Edit `.env`:
```bash
LTV_WARNING_THRESHOLD=65   # Warning at 65%
LTV_CRITICAL_THRESHOLD=75  # Critical at 75%
```

### Monitor Multiple Wallets

Create multiple configuration files and run separate instances:
```bash
# Wallet 1
SUI_WALLET_ADDRESS=0xWallet1... python bluefin_monitor.py monitor &

# Wallet 2  
SUI_WALLET_ADDRESS=0xWallet2... python bluefin_monitor.py monitor &
```

## Understanding the Metrics

### LTV (Loan-to-Value) Ratio
```
LTV = (Borrowed Value / Collateral Value) × 100
```
- **Safe**: < 50%
- **Moderate**: 50-70%
- **Warning**: 70-80%
- **Critical**: > 80%

### Health Factor
```
Health Factor = (Collateral Value × Liquidation Threshold) / Borrowed Value
```
- **Safe**: > 1.5
- **Moderate**: 1.2 - 1.5
- **Warning**: 1.05 - 1.2
- **Critical**: < 1.05
- **Liquidation**: < 1.0

## Troubleshooting

### "No positions found"
- Verify your wallet address is correct
- Ensure you have active AlphaLend positions
- Check that you're connected to mainnet

### "Email not sending"
- Verify SMTP credentials in `.env`
- For Gmail, ensure you're using an App Password (not your regular password)
- Check that "Less secure app access" is NOT enabled (use App Passwords instead)

### "RPC connection failed"
- The script will automatically rotate between RPC endpoints
- You can add your own RPC provider to the `SUI_RPC_ENDPOINTS` list

## Sample Output

```
Checking positions for wallet: 0xYOUR_WALLET_ADDRESS
Found 1 position capabilities

--- Fetched prices from Pyth Network ---
  BTC: $69,926.6998
  SUI: $1.0004
  USDC: $0.9998

============================================================
POSITION SUMMARY
============================================================
  Position ID: 0x0ad0d437bc758c0facb76e9587e8315e9bd8ed6977f3b3609bcec2498a067871
  Collateral Assets: USDC (market 6), XBTC (market 16)
  Borrowed Assets: SUI

  Total Collateral:     $5,222.70
  Safe Collateral:      $4,374.93
  Liquidation Value:    $4,636.07
  Total Borrowed:       $2,907.21

  LTV:                  55.66%
  Health Factor:        1.5947
  Liquidation Threshold: 88.77%

  Position Healthy:     Yes
  Liquidatable:         No
============================================================
```

---

## Technical Details: How This Script Works

### Contract Discovery Process

Finding the correct contract addresses and data structures required several steps of blockchain exploration:

#### 1. Finding the PositionCap Object

The script first queries all objects owned by the wallet using `suix_getOwnedObjects`. It looks for objects with type containing `PositionCap`:

```
0xd631cd66138909636fc3f73ed75820d0c5b76332d1644608ed1c85ea2b8219b4::position::PositionCap
```

The PositionCap contains a `position_id` field that references the actual position data stored in the protocol.

#### 2. Finding the Protocol State Object

The `LENDING_PROTOCOL_ID` was discovered by examining AlphaLend documentation and the [DefiLlama adapter](https://github.com/DefiLlama/DefiLlama-Adapters/blob/main/projects/bluefin-alphalend/index.js):

```
0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93
```

Querying this object with `sui_getObject` reveals the protocol structure:

```bash
curl -X POST https://fullnode.mainnet.sui.io:443 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"sui_getObject","params":["0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93",{"showContent":true}]}'
```

This returns:
- `markets` table: `0x2326d387ba8bb7d24aa4cfa31f9a1e58bf9234b097574afb06c5dfb267df4c2e`
- `positions` table: `0x9923cec7b613e58cc3feec1e8651096ad7970c0b4ef28b805c7d97fe58ff91ba`

#### 3. Fetching Position Data

Positions are stored as dynamic fields in the positions table, keyed by the position ID (from PositionCap). The query uses `suix_getDynamicFieldObject`:

```python
await self._rpc_call(
    "suix_getDynamicFieldObject",
    [POSITIONS_TABLE_ID, {"type": "0x2::object::ID", "value": position_id}]
)
```

#### 4. Position Data Structure

The Position object contains pre-calculated USD values with 18 decimal precision:

| Field | Description |
|-------|-------------|
| `total_collateral_usd` | Total collateral value in USD (18 decimals) |
| `total_loan_usd` | Total borrowed value in USD (18 decimals) |
| `liquidation_value` | Value at which liquidation occurs |
| `safe_collateral_usd` | Safe collateral threshold |
| `is_position_healthy` | Boolean health status |
| `is_position_liquidatable` | Boolean liquidation status |
| `collaterals` | VecMap of market_id -> amount |
| `loans` | Vector of Borrow objects with coin_type, amount |

### Price Feed Integration (Pyth Network)

Prices are fetched from Pyth Network's Hermes API:

```
https://hermes.pyth.network/v2/updates/price/latest?ids[]=<feed_id>
```

#### Discovering Price Feed IDs

Feed IDs were discovered by querying the Pyth API:

```bash
# Search for SUI price feed
curl "https://hermes.pyth.network/v2/price_feeds?query=SUI&asset_type=crypto"

# Search for BTC price feed
curl "https://hermes.pyth.network/v2/price_feeds?query=BTC&asset_type=crypto"
```

#### Price Feed IDs Used

| Asset | Pyth Feed ID |
|-------|--------------|
| SUI | `23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744` |
| BTC/XBTC | `e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43` |
| USDC | `eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a` |
| ETH | `ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace` |
| USDT | `2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b` |

### LTV and Health Factor Calculation

```python
# LTV = (borrowed / collateral) * 100
ltv = (total_loan_usd / total_collateral_usd) * 100

# Health Factor = liquidation_value / total_loan_usd
# Values > 1 are healthy, < 1 means liquidatable
health_factor = liquidation_value / total_loan_usd
```

---

## Key Contract Addresses (SUI Mainnet)

| Contract | Address |
|----------|---------|
| AlphaLend Package | `0xd631cd66138909636fc3f73ed75820d0c5b76332d1644608ed1c85ea2b8219b4` |
| Lending Protocol | `0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93` |
| Positions Table | `0x9923cec7b613e58cc3feec1e8651096ad7970c0b4ef28b805c7d97fe58ff91ba` |
| Markets Table | `0x2326d387ba8bb7d24aa4cfa31f9a1e58bf9234b097574afb06c5dfb267df4c2e` |

---

## Resources & References

### Official Documentation
- [Pyth Network Docs](https://docs.pyth.network/price-feeds/use-real-time-data/sui)
- [AlphaLend Introduction](https://docs.alphafi.xyz/alphalend/introduction/what-is-alphalend)
- [Bluefin Lending Features](https://learn.bluefin.io/bluefin/lending-on-bluefin/protocol-features)

### Contract & API References
- [AlphaLend Contracts GitHub](https://github.com/AlphaFiTech/alphalend-contracts-interfaces)
- [DefiLlama AlphaLend Adapter](https://github.com/DefiLlama/DefiLlama-Adapters/blob/main/projects/bluefin-alphalend/index.js)
- [AlphaLend SDK (npm)](https://www.npmjs.com/package/@alphafi/alphalend-sdk)

### API Endpoints
- Pyth Hermes API: `https://hermes.pyth.network/v2/updates/price/latest`
- SUI RPC: `https://fullnode.mainnet.sui.io:443`

## Security Notes

⚠️ **Important Security Practices:**
- Never commit your `.env` file to git
- Use environment variables for production
- Restrict file permissions: `chmod 600 .env`
- Use read-only wallet monitoring (no private keys needed)
- Regularly update dependencies

## Support & Resources

- **Bluefin Docs**: https://learn.bluefin.io
- **SUI Docs**: https://docs.sui.io
- **AlphaLend Docs**: https://docs.alphafi.xyz/alphalend
- **AlphaLend GitHub**: https://github.com/AlphaFiTech/alphalend-contracts-interfaces
- **Pyth Network**: https://www.pyth.network

## License

MIT License - Feel free to modify and use for your own monitoring needs.

## Disclaimer

This tool is provided as-is for monitoring purposes. Always verify positions through the official Bluefin interface. The authors are not responsible for any losses incurred from using this tool.
