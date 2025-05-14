from telethon import events
from hikka import loader, utils
import requests
import matplotlib.pyplot as plt
import io
import datetime

class CryptoChartMod(loader.Module):
    """Плагин для отображения графика криптовалюты и статистики с Binance"""
    strings = {"name": "CryptoChart"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_symbol",
                "BTCUSDT",
                lambda: "Криптовалюта по умолчанию",
                validator=loader.validators.String()
            )
        )

    @loader.command()
    async def crypto(self, message):
        """Использование: .crypto <символ>"""
        args = utils.get_args_raw(message)
        symbol = args.upper() if args else self.config["default_symbol"]
        interval = "1d"  # Период по умолчанию

        await message.edit(f"Получение данных для {symbol}...")

        # Получение данных о цене
        price_data = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}").json()
        if "code" in price_data:
            await message.edit(f"Ошибка: {price_data['msg']}")
            return

        price = float(price_data["lastPrice"])
        change = float(price_data["priceChangePercent"])
        high = float(price_data["highPrice"])
        low = float(price_data["lowPrice"])
        volume = float(price_data["volume"])

        # Получение данных для графика
        klines = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=30").json()
        dates = [datetime.datetime.fromtimestamp(k[0]/1000) for k in klines]
        closes = [float(k[4]) for k in klines]

        # Построение графика
        plt.figure(figsize=(10, 5))
        plt.plot(dates, closes, label=symbol)
        plt.title(f"{symbol} - График цен")
        plt.xlabel("Дата")
        plt.ylabel("Цена")
        plt.legend()
        plt.grid(True)

        # Сохранение графика в буфер
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Отправка графика и статистики
        caption = (
            f"**{symbol}**\n"
            f"Цена: `{price}` USD\n"
            f"Изменение за 24ч: `{change}%`\n"
            f"Макс: `{high}` USD\n"
            f"Мин: `{low}` USD\n"
            f"Объем: `{volume}`"
        )

        await message.client.send_file(message.chat_id, buf, caption=caption, reply_to=message.id)
        await message.delete()
