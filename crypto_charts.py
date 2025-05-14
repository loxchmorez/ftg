# crypto bot
import asyncio
import io
import os
import time
import hashlib
import requests
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from telethon.tl.types import Message
from .. import loader, utils

CACHE_DIR = "/tmp/hikka_crypto_cache"
CACHE_TIMEOUT = 300  # 5 минут
os.makedirs(CACHE_DIR, exist_ok=True)

class CryptoChartMod(loader.Module):
    strings = {"name": "CryptoChart"}

    async def client_ready(self, client, db):
        self.client = client

    def get_cache_filename(self, symbol, interval, quote):
        key = f"{symbol}_{interval}_{quote}"
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{hash_key}.png")

    def is_cached(self, symbol, interval, quote):
        path = self.get_cache_filename(symbol, interval, quote)
        return os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TIMEOUT

    def get_cached(self, symbol, interval, quote):
        with open(self.get_cache_filename(symbol, interval, quote), "rb") as f:
            return f.read()

    def cache_plot(self, symbol, interval, quote, buf):
        with open(self.get_cache_filename(symbol, interval, quote), "wb") as f:
            f.write(buf.getvalue())

    def parse_symbol(self, text):
        # "btc", "btc/usdt", "₿" => BTCUSDT
        aliases = {"₿": "BTC", "$": "USD"}
        for k, v in aliases.items():
            text = text.replace(k, v)
        text = text.upper().replace("/", "")
        if not any(text.endswith(suffix) for suffix in ("USDT", "USD", "BTC", "ETH", "EUR", "RUB")):
            text += "USDT"
        return text

    def get_binance_klines(self, symbol, interval="1d", limit=50):
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r = requests.get(url)
        if r.status_code != 200:
            raise Exception(f"Binance error: {r.text}")
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)
        df = df.astype(float)
        return df[["open", "high", "low", "close", "volume"]]

    def get_fiat_rate(self, base, quote):
        url = f"https://api.exchangerate.host/convert?from={base}&to={quote}"
        r = requests.get(url)
        data = r.json()
        if not data.get("success", False):
            raise Exception("Fiat conversion error")
        return data["result"]

    def generate_candle_plot(self, df, title="Chart"):
        buf = io.BytesIO()
        mpf.plot(df, type="candle", style="charles", title=title, ylabel="Price", volume=True, savefig=buf)
        buf.seek(0)
        return buf

    @loader.command()
    async def crypto(self, message: Message):
        """[coin] [to] — Показать график и цену"""
        args = utils.get_args_raw(message).split()
        if not args:
            await message.edit("Введите монету. Пример: `.crypto btc rub`")
            return

        coin = args[0]
        to_currency = args[1] if len(args) > 1 else "USD"
        interval = "1d"

        symbol = self.parse_symbol(coin + to_currency)
        base = coin.upper()
        quote = to_currency.upper()

        try:
            if self.is_cached(symbol, interval, quote):
                chart = self.get_cached(symbol, interval, quote)
            else:
                df = self.get_binance_klines(symbol, interval)
                chart_buf = self.generate_candle_plot(df, f"{symbol} — {interval}")
                self.cache_plot(symbol, interval, quote, chart_buf)
                chart = chart_buf.getvalue()

            price = float(df["close"].iloc[-1])
            if quote not in symbol:
                rate = self.get_fiat_rate("USD", quote)
                price *= rate

            text = f"**{base}/{quote}**
Цена: `{price:.2f} {quote}`"

            await self.client.send_file(message.chat_id, chart, caption=text, reply_to=message.id)
            await message.delete()
        except Exception as e:
            await message.edit(f"Ошибка: {e}")
