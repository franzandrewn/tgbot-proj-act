import logging
import os
from datetime import date, datetime, timedelta

import httpx
from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

CHOOSING, TOP_HEADLINES, SEARCH, IN_SETTINGS, TYPING_REPLY = range(5)

main_keyboard = [
    ["Поиск новостей"],
    ["Параметры запроса"]
]
main_markup = ReplyKeyboardMarkup(main_keyboard, one_time_keyboard=True)

search_keyboard = [
    ["Получить новости"],
    ["Параметры запроса", "Назад"]
]
search_markup = ReplyKeyboardMarkup(search_keyboard, one_time_keyboard=True)

settings_keyboard = [
    ["Ключевые слова", "Сортировка"],
    ["Начало поиска", "Конец поиска"],
    ["Язык", "Страна"],
    ["Сохранить"]
]
settings_flat = [x.lower() for xs in settings_keyboard for x in xs]
settings_markup = ReplyKeyboardMarkup(settings_keyboard, one_time_keyboard=True)

translate_keys = {"q": "Ключевые слова", "sortBy": "Сортировка", "from": "Начало поиска", "to": "Конец поиска",
                  "language": "Язык", "country": "Страна"}
back_translate_keys = {"ключевые слова": "q", "сортировка": "sortBy", "начало поиска": "from", "конец поиска": "to",
                       "язык": "language", "страна": "country"}

sort_values = {"популярность": "popularity", "релевантность": "relevancy", "дата": "publishedAt"}
tg_token = os.getenv("TG_TOKEN")
news_token = os.getenv("NEWS_TOKEN")

if tg_token is None:
    raise KeyError("No Telegram bot token in environmental variables")
if news_token is None:
    raise KeyError("No news token in environmental variables")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Доступные команды:\n"
                                        "<b>\\start</b> - начало работы с ботом\n"
                                        "<b>\\help</b> - доступ к сообщению с помощью\n"
                                        "<b>\\contact</b> - контакты разработчика\n"
                                        "Для работы с основным функционалам бота используйте предоставляемую клавиатуру с коммандами",
                                   parse_mode=ParseMode.HTML)


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Контакт разработчика: @franzandrn")


async def everything_request(token, q=None, from_par="1970-01-01", to_par=date.today().isoformat(),
                             lang_par="ru", sort_par="popularity"):
    q_par = "VR+OR+AR"
    if q is not None:
        q_par = "(" + q + ")+AND+(" + q_par + ")"
    async with httpx.AsyncClient() as client:
        params = {"q": q_par, "from": from_par, "to": to_par, "language": lang_par, "sortBy": sort_par, "pageSize": 100}
        headers = {"X-Api-Key": token}
        r = await client.get("https://newsapi.org/v2/everything", params=params, headers=headers)
        if r.status_code == 200:
            return r.json()
        else:
            raise Exception("bad status code(((")


async def top_headlines_request(token, country_par=None):
    q_par = "VR+OR+AR"
    async with httpx.AsyncClient() as client:
        if country_par is not None:
            params = {"q": q_par, "country": country_par, "pageSize": 100}
        else:
            params = {"q": q_par, "pageSize": 100}
        headers = {"X-Api-Key": token}
        r = await client.get("https://newsapi.org/v2/top-headlines", params=params, headers=headers)
        if r.status_code == 200:
            return r.json()
        else:
            raise Exception("bad status code(((")


def facts_to_str(user_data: dict[str, str]) -> str:
    """Helper function for formatting the gathered user info."""

    facts = [f"{translate_keys[key]} - {value}" for key, value in user_data.items() if key in translate_keys]
    return "\n".join(facts).join(["\n", "\n"])


def construct_article_msg(article, ar_num, ar_len):
    published_iso = datetime.fromisoformat(article["publishedAt"][:10])
    published_iso = published_iso.date().isoformat()
    return f"""Новость {ar_num} из {ar_len}:
                    Опубликовано в {article["source"]["name"]} от {published_iso}
                    автор - {article["author"]}
                    {article["title"]}
                    <a href='{article["url"]}'>Ссылка</a>
                """


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation, display any stored data and ask user for input."""
    reply_text = "Привет. Я бот, помогающий следить за новостями в сфере VR/AR!\n"
    if context.user_data:
        reply_text += (
            f" У меня уже сохранены твои настройки запроса\n {facts_to_str(context.user_data)}"
        )
    else:
        context.user_data.update({"q": "VR AR", "sortBy": "популярность", "from": "1970-01-01", "to": "сегодня",
                                  "language": "ru", "country": "RU"})
        reply_text += (
            f" Мы встречаемся в первый раз, вот базовые настройки запроса {facts_to_str(context.user_data)}"
        )
    await update.message.reply_text(reply_text, reply_markup=main_markup)

    return CHOOSING


async def main_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for info about the selected predefined choice."""
    text = update.message.text.lower()

    next_state = CHOOSING
    reply_markup = main_markup
    if text == "Топ новостей".lower():
        next_state = TOP_HEADLINES
        reply_text = f"Давай найдем последние горячие новости."
        reply_markup = search_markup
    elif text == "Поиск новостей".lower():
        next_state = SEARCH
        reply_text = f"Необходимо найти новости по определенным параметрам? Без проблем."
        reply_markup = search_markup
    elif text == "Параметры запроса".lower():
        next_state = IN_SETTINGS
        reply_text = f"Текущие настройки поиска:\n{facts_to_str(context.user_data)}"
        reply_markup = settings_markup
    else:
        reply_text = f"Неверная команда"
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return next_state


async def top_headlines_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower()

    next_state = TOP_HEADLINES
    reply_markup = search_markup

    if text == "Получить новости".lower():
        next_state = CHOOSING
        reply_text = f"Возврат к основному меню"
        reply_markup = main_markup
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Последние горячие новости")

        params = context.user_data
        results = await top_headlines_request(news_token, country_par=params["country"])
        if results["status"] == "ok":
            logger.info(f"got ok results: {results}")
            articles = results["articles"]
            articles = [x for x in articles if "removed" not in x["url"]][:10]
            ar_len = len(articles)
            ar_num = 1
            for article in articles:
                article_msg = construct_article_msg(article, ar_num, ar_len)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=article_msg,
                                               parse_mode=ParseMode.HTML)
                ar_num += 1
        else:
            logger.info(f"no results: {results}")
    elif text == "Параметры запроса".lower():
        next_state = IN_SETTINGS
        reply_text = f"Текущие параметры запросов: \n{facts_to_str(context.user_data)}"
        reply_markup = settings_markup
    elif text == "Назад".lower():
        next_state = CHOOSING
        reply_text = f"Возврат к основному меню"
        reply_markup = main_markup
    else:
        reply_text = f"Неверная команда"
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return next_state


async def search_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower()

    next_state = TOP_HEADLINES
    reply_markup = search_markup

    if text == "Получить новости".lower():
        next_state = CHOOSING
        reply_text = f"Возврат к основному меню"
        reply_markup = main_markup
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Вот найденные новости")

        params = context.user_data
        sortBy = sort_values[params["sortBy"]]
        to = params["to"]
        if to == "сегодня":
            to = date.today().isoformat()
        fr = params["from"]
        if date.fromisoformat(fr) < date.today() - timedelta(days=28):
            fr = date.today() - timedelta(days=28)
            fr = fr.isoformat()
        results = await everything_request(news_token, q=params["q"], sort_par=sortBy, from_par=fr,
                                           to_par=to, lang_par=params["language"])
        if results["status"] == "ok":
            logger.info(f"got ok results: {results}")
            articles = results["articles"]
            articles = [x for x in articles if "removed" not in x["url"]][:10]
            ar_len = len(articles)
            ar_num = 1
            for article in articles:
                article_msg = construct_article_msg(article, ar_num, ar_len)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=article_msg,
                                               parse_mode=ParseMode.HTML)
                ar_num += 1
        else:
            logger.info(f"no results: {results}")

    elif text == "Параметры запроса".lower():
        next_state = IN_SETTINGS
        reply_text = f"Текущие параметры запросов: \n{facts_to_str(context.user_data)}"
        reply_markup = settings_markup
    elif text == "Назад".lower():
        next_state = CHOOSING
        reply_text = f"Возврат к основному меню"
        reply_markup = main_markup
    else:
        reply_text = f"Неверная команда"
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return next_state


async def settings_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data["choice"] = text.lower()

    next_state = IN_SETTINGS
    reply_markup = settings_markup

    logger.info(f"{text.lower()} in {str(settings_flat)}")
    if text.lower() in settings_flat and text.lower() != "Сохранить".lower():
        next_state = TYPING_REPLY
        reply_text = f"Введите значение для параметра"
        reply_markup = None
    elif text.lower() == "Сохранить".lower():
        next_state = CHOOSING
        reply_text = f"Возврат к основному меню"
        reply_markup = main_markup
    else:
        reply_text = f"Неверная команда"
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return next_state


async def received_information(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for the next category."""
    text = update.message.text
    category = context.user_data["choice"]
    translated_category = back_translate_keys[category]

    if translated_category == "country":
        text = text.upper()
    elif translated_category == "q":
        text = "+".join([x for x in text.split(" ")])
    elif translated_category == "to" and text.lower() == "сегодня":
        text = date.today().isoformat()
    elif translated_category == "from" and date.fromisoformat(text) < date.today() - timedelta(days=28):
        text = date.today() - timedelta(days=28)
        text = text.isoformat()
    else:
        text = text.lower()

    context.user_data[translated_category] = text
    del context.user_data["choice"]

    await update.message.reply_text(f"Параметр сохранён.", reply_markup=settings_markup)

    return IN_SETTINGS


async def show_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the gathered info."""
    await update.message.reply_text(
        f"This is what you already told me: {facts_to_str(context.user_data)}"
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    if "choice" in context.user_data:
        del context.user_data["choice"]

    await update.message.reply_text(
        f"Итоговые значения параметров: {facts_to_str(context.user_data)}До следующего раза",
        reply_markup=main_markup,
    )
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""

    # Create the Application and pass it your bot's token.
    persistence = PicklePersistence(filepath="conversationbot")
    application = Application.builder().token(tg_token).persistence(persistence).build()

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$")), main_choice
                ),
            ],
            TOP_HEADLINES: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Завершить$")), top_headlines_choice
                )
            ],
            SEARCH: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Завершить$")),
                    search_choice,
                )
            ],
            IN_SETTINGS: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Завершить$")),
                    settings_choice,
                )
            ],
            TYPING_REPLY: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Завершить$")),
                    received_information,
                )
            ],
        },
        name="my_conversation",
        persistent=True,
        fallbacks=[MessageHandler(filters.Regex("^Завершить$"), done)],
    )

    application.add_handler(conv_handler)

    show_data_handler = CommandHandler("show_settings", show_data)
    application.add_handler(show_data_handler)
    help_handler = CommandHandler("help", help_command)
    application.add_handler(help_handler)
    contact_handler = CommandHandler("contact", contact)
    application.add_handler(contact_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def start_bot():
    main()
