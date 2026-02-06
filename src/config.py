"""Configuration and constants"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Wallet configuration
WALLET_ADDRESS = os.getenv("SUI_WALLET_ADDRESS", "")

# Alert thresholds
LTV_WARNING_THRESHOLD = float(os.getenv("LTV_WARNING_THRESHOLD", "70.0"))
LTV_CRITICAL_THRESHOLD = float(os.getenv("LTV_CRITICAL_THRESHOLD", "80.0"))

# Email configuration
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

# Telegram configuration
TELEGRAM_ALERT_BOT_TOKEN = os.getenv("TELEGRAM_ALERT_BOT_TOKEN", "")
TELEGRAM_LOG_BOT_TOKEN = os.getenv("TELEGRAM_LOG_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# AlphaLend contract addresses on SUI mainnet
LENDING_PROTOCOL_ID = "0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93"
ALPHALEND_PACKAGE_ID = "0xd631cd66138909636fc3f73ed75820d0c5b76332d1644608ed1c85ea2b8219b4"
POSITIONS_TABLE_ID = "0x9923cec7b613e58cc3feec1e8651096ad7970c0b4ef28b805c7d97fe58ff91ba"
MARKETS_TABLE_ID = "0x2326d387ba8bb7d24aa4cfa31f9a1e58bf9234b097574afb06c5dfb267df4c2e"

# Precision for USD values (18 decimals)
USD_PRECISION = 10 ** 18

# SUI RPC endpoints
SUI_RPC_ENDPOINTS = [
    "https://fullnode.mainnet.sui.io:443",
    "https://sui-mainnet.nodeinfra.com",
    "https://sui-mainnet-endpoint.blockvision.org",
]

# Pyth Network configuration
PYTH_HERMES_URL = "https://hermes.pyth.network/v2/updates/price/latest"
PYTH_PRICE_FEEDS = {
    "SUI": "23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744",
    "BTC": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "XBTC": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "USDC": "eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a",
    "USDT": "2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b",
    "ETH": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
}
