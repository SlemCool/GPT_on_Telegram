import logging
import os
import sqlite3
import sys
import time

import openai
import telebot
from dotenv import load_dotenv
from googletrans import Translator

load_dotenv()

# Включаем логирование
logging.basicConfig(
    handlers=[logging.FileHandler(filename='main.log', encoding='utf-8')],
    format='%(asctime)s  %(name)s, %(levelname)s, %(message)s',
    datefmt='%F %A %T',
    level=logging.DEBUG,
)
logger = logging.getLogger('ChatGPT_main')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(handler)

# Подтягиваем токены
OPENAI_TOKEN = os.getenv('OPENAI_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_ADMIN_CHAT_ID = os.getenv('TELEGRAM_ADMIN_CHAT_ID')

BASE_MASSAGE = {"role": "system", "content": "You`re a kind helpful assistant"}
MODEL = 'gpt-3.5-turbo'

translator = Translator()

users = {}
insert_db = {'rq': 'empty', 'eng_rq': '', 'ans': 'empty', 'rus_ans': ''}


def check_tokens():
    """Проверка пред заполненных переменных окружения."""
    return all((OPENAI_TOKEN, TELEGRAM_TOKEN, TELEGRAM_ADMIN_CHAT_ID))


if not check_tokens():
    logger.critical('Отсутствует хотя бы одна переменная окружения')
    raise ValueError('Отсутствует хотя бы одна переменная окружения!')
logger.debug('Переменные прошли проверку')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
openai.api_key = OPENAI_TOKEN


def _db_table_val(
    user_id: int,
    user_name: str,
    user_first_name: str,
    user_last_name: str,
    user_rq: str,
    user_rq_trans: str,
    openai_ans: str,
    openai_ans_trans: str,
):
    try:
        sqlite_connection = sqlite3.connect(
            'telegram_GPT_rq.sqlite', check_same_thread=False
        )
        cursor_db = sqlite_connection.cursor()
        logger.debug('Соединение с SQLite для бд "telegram_GPT_rq" открыто')

        cursor_db.execute(
            'INSERT INTO UsersRq (user_id, user_name, user_first_name, '
            'user_last_name, user_rq, user_rq_trans, '
            'openai_ans, openai_ans_trans) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                user_id,
                user_name,
                user_first_name,
                user_last_name,
                user_rq,
                user_rq_trans,
                openai_ans,
                openai_ans_trans,
            ),
        )
        sqlite_connection.commit()
        logger.debug('Запись успешно вставлена в таблицу "UsersRq"')
        cursor_db.close()
    except sqlite3.Error as error:
        if 'no such table' in str(error):
            logger.error(
                'Необходимо создать таблицу "UsersRq". '
                'ЗАПУСТИТЕ СКРИПТ ИЗ КОРНЕВОЙ ДИРЕКТОРИИ "db_create.py"!!'
            )
        logger.error(f'Не удалось вставить данные в таблицу sqlite {error}')
    finally:
        if sqlite_connection:
            sqlite_connection.close()
            logger.debug('Соединение с SQLite закрыто')


def _get_user(id):
    user = users.get(
        id,
        {
            'id': id,
            'last_text': [BASE_MASSAGE],
            'last_prompt_time': time.time(),
        },
    )
    users[id] = user
    return user


def _process_rq(user, rq):
    try:
        user_context = _get_user(user.id)
        message_history = user_context['last_text']
        last_message_time = user_context['last_prompt_time']
        # По прошествию 10 мин контекст общения очищается
        if time.time() - last_message_time > 600:
            message_history.clear()
            message_history.append(BASE_MASSAGE)
            last_message_time = time.time()
            logger.debug(
                f'По прошествию 10 мин контекст общения для {user.id} очищен'
            )

        if rq and 0 < len(rq) < 1000:
            insert_db['rq'] = rq
            inc_detect = translator.detect(rq)
            if inc_detect.lang == 'ru':
                logger.debug('Перевод запроса с русского языка')
                eng_rq = translator.translate(rq, dest='en', src='ru').text
                rq = eng_rq
                insert_db['eng_rq'] = eng_rq
            message_history.append({"role": "user", "content": rq})
            logger.debug('Отправлен запрос в OpenAI.')
            completion = openai.ChatCompletion.create(
                model=MODEL,
                messages=message_history,
                max_tokens=1000,
                temperature=0.7,
            )
            ans = completion.choices[0].message.content
            message_history.append({"role": "assistant", "content": ans})
            insert_db['ans'] = ans
            last_message_time = time.time()
            if inc_detect.lang == 'ru':
                logger.debug('Перевод ответа с английского языка')
                rus_ans = translator.translate(ans, dest='ru', src='en').text
                insert_db['rus_ans'] = rus_ans
                ans = rus_ans
            _db_table_val(
                user_id=user.id,
                user_name=user.username,
                user_first_name=user.first_name,
                user_last_name=user.last_name,
                user_rq=insert_db['rq'],
                user_rq_trans=insert_db['eng_rq'],
                openai_ans=insert_db['ans'],
                openai_ans_trans=insert_db['rus_ans'],
            )
            return ans
        else:
            message_error = 'Ошибка! Слишком длинный вопрос'
            logger.error(message_error)
            return message_error
    except Exception as error:
        logger.error(error)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        f'СкайНет просыпается! ✌\n\n-Используется модель: {MODEL}'
        '\n-Чтобы очистить контекст общения напишите /clear'
        '\n-Чтобы увидеть последний ответ бота на английском /eng',
    )
    info_message = (
        f'Кто-то нажал /start:\n\n'
        f'ID: {message.chat.id}\n'
        f'Пользователь: {message.chat.username}\n'
        f'Имя: {message.chat.first_name}\n'
        f'Фамилия: {message.chat.last_name}',
    )
    bot.send_message(TELEGRAM_ADMIN_CHAT_ID, info_message)
    logger_message = ''.join(info_message)
    logger.debug(logger_message.replace('\n', ' '))


@bot.message_handler(commands=['clear'])
def clear_history(message):
    user = _get_user(message.from_user.id)
    user['last_text'].clear()
    user['last_text'].append(BASE_MASSAGE)
    user['last_prompt_time'] = time.time()
    bot.reply_to(message, 'История общения очищена!')
    logger.debug(f'Контекст общения для пользователя "{user["id"]}" очищен')


@bot.message_handler(commands=['eng'])
def eng_answer(message):
    bot.reply_to(message, insert_db['ans'])
    logger.debug(f'Юзер "{message.chat.id}" запросил ответ на "Eng" языке')


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    user = message.chat
    rq = message.text
    user_full_name = (
        f'Пользователь: {user.id}-{user.username}'
        f'-{user.first_name}-{user.last_name}; '
    )
    logger.debug('<<< ' + user_full_name + ' Послал запрос')
    ans = _process_rq(user, rq)
    logger.debug('>>> ' + user_full_name + ' Дан ответ.')
    bot.send_message(user.id, ans)


if __name__ == '__main__':
    while True:
        try:
            logger.info('Бот приступает к работе')
            bot.polling(non_stop=True)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            bot.send_message(TELEGRAM_ADMIN_CHAT_ID, message)
        finally:
            logger.debug('Ожидаем 3 сек и включаемся')
            time.sleep(3)
