# GPT Telegram Bot 🧑‍💻
This is a Telegram bot 🤖 that uses the GPT model gpt-3.5-turbo (Generative Pre-trained Transformer) model to generate text based on user input 🤯. 
The bot is built using Python and the Telegram Bot API.

Bot created for Russian community. He translate input text into google translation API and then send it to OpenAI API.

Requests from users are stored in the SQLite database.
### Requirements
🐍 Python 3.6 or higher

### Clone this repository:
```
git clone https://github.com/SlemCool/GPT_on_Telegram.git
```
```
cd GPT_on_Telegram
```

### Fill in environment variables:
Rename .env.example to .env and set up variables 📝
```
OPENAI_TOKEN = <your token from open_ai>

# Telegram bot token (can be obtained from BotFather)
TELEGRAM_TOKEN = <your token from telegram>

TELEGRAM_ADMIN_CHAT_ID = <add telegram chat_ID>
```

### Create and activate virtual environment:
```
python -m venv venv
```

```
. venv/Scripts/activate
```

### Create database:
```
python db_create.py
```

### Install the required libraries:
```
python -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```

### Run a bot 🟢:
```
python tg_bot_rus.py
```

Usage:

Start the bot by sending a message 📨 to it on Telegram.

The bot will respond with generated text based on the prompt.
