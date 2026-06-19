import asyncio
from telegram import Bot

BOT_TOKEN = "8487551708:AAE4G5ioDGRq8G6ytbL_KgkjeoQqKuEYVvo"

async def main():
    bot = Bot(BOT_TOKEN)
    # offset=-1 forces returning the last update regardless of previous fetches
    updates = await bot.get_updates(offset=-1, timeout=5)
    if updates:
        print("Chat ID:", updates[-1].message.chat.id)
    else:
        print("No messages yet. Send a message to your bot in Telegram first!")

asyncio.run(main())