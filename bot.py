import os

import asyncio
import telegram


async def main():
    token = os.getenv("TG_TOKEN")

    if token is None:
        raise KeyError("No Telegram bot token in environmental variables")

    bot = telegram.Bot(token)
    async with bot:
        print(await bot.get_me())


def start_bot():
    asyncio.run(main())