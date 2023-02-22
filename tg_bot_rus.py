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

OPENAI_TOKEN = os.getenv('OPENAI_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_ADMIN_CHAT_ID = os.getenv('TELEGRAM_ADMIN_CHAT_ID')

model = 'text-davinci-003'
stop_symbols = '###'

translator = Translator()

users = {}


def check_tokens():
    """Проверка пред заполненных переменных окружения."""
    return all((OPENAI_TOKEN, TELEGRAM_TOKEN, TELEGRAM_ADMIN_CHAT_ID))


if not check_tokens():
    logger.critical('Отсутствует хотя бы одна переменная окружения')
    raise ValueError('Отсутствует хотя бы одна переменная окружения!')
logger.debug('Переменные прошли проверку')
bot = telebot.TeleBot(TELEGRAM_TOKEN)
openai.api_key = OPENAI_TOKEN


def db_table_val(user_id: int, user_name: str, user_first_name: str,
                 user_last_name: str, user_rq: str, user_rq_trans: str,
                 openai_ans: str, openai_ans_trans: str):
    try:
        sqlite_connection = sqlite3.connect('Telegram_GPT_rq',
                                            check_same_thread=False)
        cursor_db = sqlite_connection.cursor()
        logger.debug('Соединение с SQLite для бд "db/db_tele_GPT" открыто')

        cursor_db.execute(
            'INSERT INTO UsersRq (user_id, user_name, user_first_name, '
            'user_last_name, user_rq, user_rq_trans, '
            'openai_ans, openai_ans_trans) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (user_id, user_name, user_first_name, user_last_name, user_rq,
             user_rq_trans, openai_ans, openai_ans_trans)
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
            logger.debug(f'Соединение с SQLite закрыто')


def _get_user(id):
    user = users.get(id, {'id': id, 'last_text': '', 'last_prompt_time': 0})
    users[id] = user
    return user


def _process_rq(user, rq):
    insert_db = {'rq': rq, 'eng_rq': '', 'ans': '', 'rus_ans': ''}
    try:
        user_context = _get_user(user.id)
        last_text = user_context['last_text']
        # По прошествию 10 мин контекст общения очищается
        if time.time() - user_context['last_prompt_time'] > 600:
            last_text = ''
            user_context['last_prompt_time'] = 0
            user_context['last_text'] = ''
            logger.debug(
                f'По прошествию 10 мин контекст общения для {user.id} очищен')

        if rq and 0 < len(rq) < 1000:
            inc_detect = translator.detect(rq)
            if inc_detect.lang == 'ru':
                logger.debug('Перевод запроса с русского языка')
                eng_rq = translator.translate(rq, dest='en', src='ru').text
                rq = eng_rq
                insert_db['eng_rq'] = eng_rq
            # Обрезка до 1000 символов
            prompt = f'{last_text}Q: {rq} ->'[-1000:]
            logger.debug('Отправлен запрос в OpenAI.')
            completion = openai.Completion.create(
                engine=model,
                prompt=prompt,
                max_tokens=256,
                stop=[stop_symbols],
                temperature=0.7,
            )
            eng_ans = completion['choices'][0]['text'].strip()
            if '->' in eng_ans:
                eng_ans = eng_ans.split('->')[0].strip()
            ans = eng_ans
            if inc_detect.lang == 'ru':
                logger.debug('Перевод ответа с английского языка')
                rus_ans = translator.translate(eng_ans, dest='ru',
                                               src='en').text
                insert_db['rus_ans'] = rus_ans
                ans = rus_ans
            user_context['last_text'] = prompt + ' ' + eng_ans + stop_symbols
            user_context['last_prompt_time'] = time.time()
            insert_db['ans'] = ans
            db_table_val(user_id=user.id, user_name=user.username,
                         user_first_name=user.first_name,
                         user_last_name=user.last_name,
                         user_rq=insert_db['rq'],
                         user_rq_trans=insert_db['eng_rq'],
                         openai_ans=insert_db['ans'],
                         openai_ans_trans=insert_db['rus_ans'])

            return ans
        else:
            user_context['last_prompt_time'] = 0
            user_context['last_text'] = ''
            message_error = 'Ошибка! Слишком длинный вопрос'
            logger.error(message_error)
            return message_error
    except Exception as error:
        logger.error(error)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        f'СкайНет просыпается! ✌\n\n-Используется модель: {model}'
        '\n-Чтобы очистить контекст общения напишите /clear',
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
    user['last_prompt_time'] = 0
    user['last_text'] = ''
    bot.reply_to(message, 'История общения очищена!')
    logger.debug(f'Контекст общения для пользователя "{user["id"]}" очищен')


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    user = message.chat
    rq = message.text
    user_full_name = (
        f'Пользователь: {user.id}-{user.username}'
        f'-{user.first_name}-{user.last_name}; '
    )
    logger.debug('<<< '+user_full_name + ' Послал запрос')
    ans = _process_rq(user, rq)
    logger.debug('>>> '+user_full_name + ' Дан ответ.')
    bot.send_message(user.id, ans)


if __name__ == '__main__':

    while True:
        try:
            logger.info('Бот приступает к работе')
            bot.polling()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            bot.send_message(TELEGRAM_ADMIN_CHAT_ID, message)
        finally:
            logger.debug('Ожидаем 3 сек и включаемся')
            time.sleep(3)
