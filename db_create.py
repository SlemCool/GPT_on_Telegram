import sqlite3

try:
    sqlite_connection = sqlite3.connect('Telegram_GPT_rq')
    sqlite_create_table_query = '''CREATE TABLE "UsersRq"
(
    id               INTEGER not null
        primary key autoincrement,
    date_rq          DATETIME default (datetime('now', 'localtime')),
    user_id          INTEGER not null,
    user_name        TEXT(128),
    user_first_name  TEXT(128),
    user_last_name   TEXT(128),
    user_rq          TEXT(1000),
    user_rq_trans    TEXT(1000),
    openai_ans       TEXT(2000),
    openai_ans_trans TEXT(2000)
);'''

    cursor = sqlite_connection.cursor()
    print("База данных подключена к SQLite")
    cursor.execute(sqlite_create_table_query)
    sqlite_connection.commit()
    print("Таблица SQLite создана")

    cursor.close()

except sqlite3.Error as error:
    print("Ошибка при подключении к sqlite", error)
finally:
    if (sqlite_connection):
        sqlite_connection.close()
        print("Соединение с SQLite закрыто")
