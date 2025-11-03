import logging
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.request import HTTPXRequest
import os
import asyncio
import requests


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# Функция для получения списка песен, упорядоченного по ID
def get_song_all():
    conn = sqlite3.connect('ado.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, Namejp, Namerom FROM ado ORDER BY id")
    songs = cursor.fetchall()
    conn.close()
    return songs


async def download_google_video(url: str, dest_folder: str = "media") -> str:
    """Скачивает видео из публичной ссылки Google Drive."""
    if not url or "drive.google.com" not in url:
        return None

    try:
        file_id = url.split("/d/")[1].split("/")[0]
    except IndexError:
        return None

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(dest_folder, f"{file_id}.mp4")

    if os.path.exists(dest_path):
        return dest_path  # уже скачано

    def _download():
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

    await asyncio.to_thread(_download)
    return dest_path


async def download_google_audio(url: str, dest_folder: str = "media") -> str:
    """Скачивает видео из публичной ссылки Google Drive."""
    if not url or "drive.google.com" not in url:
        return None

    try:
        file_id = url.split("/d/")[1].split("/")[0]
    except IndexError:
        return None

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(dest_folder, f"{file_id}.mp3")

    if os.path.exists(dest_path):
        return dest_path  # уже скачано

    def _download():
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

    await asyncio.to_thread(_download)
    return dest_path


# Функция для получения информации о песне (по названию или ID)
def get_song_info(song_title_or_id):
    conn = sqlite3.connect('ado.db')
    cursor = conn.cursor()

    # Проверка, является ли запрос числом (ID)
    if song_title_or_id.isdigit() and song_title_or_id != "0":
        query = "SELECT id, Namejp, Namerom, Data, TranslationName, Other, LinkA, Album, LinkB, GoogleVideoLink, GoogleAudioLink FROM ado WHERE id = ?"
        cursor.execute(query, (song_title_or_id,))
    else:
        query = """SELECT id, Namejp, Namerom, Data, TranslationName, Other, LinkA, Album, LinkB, GoogleVideoLink, GoogleAudioLink 
                   FROM ado 
                   WHERE Namerom LIKE ? OR Namejp LIKE ?"""
        cursor.execute(query, ('%' + song_title_or_id + '%', '%' + song_title_or_id + '%'))

    result = cursor.fetchone()
    conn.close()
    return result


# Асинхронный обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    logger.info('Received /start command')
    songs = get_song_all()
    # Формируем текст приветствия и список песен
    message = "Здравствуйте! Напишите номер или название песни Ado, и я предоставлю вам информацию о ней.\nСписок песен:\n"
    # Цикл для добавления песен в сообщение
    for song_id, namejp, namerom in songs:
        # Проверка на "-"
        if namerom == "-":
            message += f"{song_id}. {namejp}\n"
        else:
            message += f"{song_id}. {namejp} ({namerom})\n"
    await update.message.reply_text(message)


# Асинхронный обработчик текстовых сообщений
async def song_info(update: Update, context: CallbackContext) -> None:
    song_title_or_id = update.message.text.strip()
    logger.info(f'Received song request: {song_title_or_id}')
    song = get_song_info(song_title_or_id)
    if song:
        # Формируем основную информацию о песне
        response = f"Название: {song[1]}"
        if song[2] != "-":
            response += f" ({song[2]})"
        response += f"\nДата выхода: {song[3]}\nПеревод названия: {song[4]}"

        if song[7] != "-":
            response += f"\nАльбом: {song[7]}"

        if song[5] != "-":
            response += f"\n\n{song[5]}"

        response += f"\n\nСсылки (YouTube)"
        if song[6] != "-":
            response += f"\nMV: {song[6]}"
        if song[8] != "-":
            response += f"\nАудио: {song[8]}"

        await update.message.reply_text(response)

        # Отправка аудио с Google Drive
        try:
            google_audio_index = 10
            google_audio = song[google_audio_index] if len(song) > google_audio_index else None

            if google_audio and google_audio != "-":
                google_audio_path = await download_google_audio(google_audio)
                if google_audio_path:
                    with open(google_audio_path, "rb") as f:
                        await context.bot.send_audio(
                            chat_id=update.effective_chat.id,
                            audio=f
                        )
                    os.remove(google_audio_path)  # безопасное удаление после отправки
                else:
                    await update.message.reply_text("Не удалось скачать аудио")
        except Exception as e:
            logger.error(f"Ошибка при скачивании аудио с Google Drive: {e}")
            await update.message.reply_text("Ошибка при скачивании аудио")

        # Отправка видео с Google Drive
        try:
            google_video_index = 9
            google_video = song[google_video_index] if len(song) > google_video_index else None

            if google_video and google_video != "-":
                google_video_path = await download_google_video(google_video)
                if google_video_path:
                    with open(google_video_path, "rb") as f:
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=f
                        )
                    os.remove(google_video_path)  # безопасное удаление после отправки
                else:
                    await update.message.reply_text("Не удалось скачать видео")
        except Exception as e:
            logger.error(f"Ошибка при скачивании видео с Google Drive: {e}")

    else:
        response = "Информация о песне не найдена."
        logger.info(f'Response: {response}')
        await update.message.reply_text(response)


def main() -> None:
    token = os.environ['BOT_TOKEN']
    # Увеличиваем таймауты
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0
    )

    application = Application.builder().token(token).request(request).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, song_info))

    port = int(os.environ.get("PORT", 8080))  # ← Render задаёт порт через переменную
    webhook_url = os.environ['WEBHOOK_URL']

    application.run_webhook(  # ← вместо run_polling()
        listen="0.0.0.0",  # слушаем на всех интерфейсах
        port=port,  # порт задаёт Render
        url_path=token,  # путь совпадает с токеном
        webhook_url=f"{webhook_url}/{token}"  # полный адрес вебхука
    )


if __name__ == "__main__":
    main()

    

