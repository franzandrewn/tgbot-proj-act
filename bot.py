import os

import asyncio
import telegram
import httpx


async def main():
    tg_token = os.getenv("TG_TOKEN")
    news_token = os.getenv("NEWS_TOKEN")

    if tg_token is None:
        raise KeyError("No Telegram bot token in environmental variables")
    if news_token is None:
        raise KeyError("No news token in environmental variables")

    bot = telegram.Bot(tg_token)
    async with bot:
        print(await bot.get_me())

        async with httpx.AsyncClient() as client:
            params = {"q": "apple", "from": "2024-11-07", "to": "2024-11-07", "sortBy": "popularity"}
            headers = {"X-Api-Key": news_token}
            r = await client.get("https://newsapi.org/v2/everything", params=params, headers=headers)
            if r.status_code == 200:
                print(r.json())
            else:
                print(r.status_code, r)


def start_bot():
    asyncio.run(main())
