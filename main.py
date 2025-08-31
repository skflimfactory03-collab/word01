import random
import telebot
from telebot import types

BOT_TOKEN = '8447850903:AAFWZcZwT47xlvC8KuNDFCOmKCRj_F6F76U'  # <-- Put your bot token here
bot = telebot.TeleBot(BOT_TOKEN)

GAME_WORD_LENGTH = 5
MAX_GUESSES = 6

def load_words():
    with open('words.txt', encoding='utf-8') as f:
        return [w.strip().upper() for w in f if len(w.strip()) == GAME_WORD_LENGTH and w.strip().isalpha()]

ALL_WORDS = load_words()

def get_random_word():
    return random.choice(ALL_WORDS)

def color_feedback(guess, answer):
    feedback = ""
    answer_chars = list(answer)
    guess_chars = list(guess)
    for i in range(len(guess_chars)):
        if guess_chars[i] == answer_chars[i]:
            feedback += "🟩"
            answer_chars[i] = None
        else:
            feedback += "*"
    for i in range(len(guess_chars)):
        if feedback[i] == "🟩":
            continue
        if guess_chars[i] in answer_chars:
            idx = answer_chars.index(guess_chars[i])
            answer_chars[idx] = None
            feedback = feedback[:i] + "🟨" + feedback[i+1:]
        else:
            feedback = feedback[:i] + "🟥" + feedback[i+1:]
    return feedback

games = {}
scores = {}

WELCOME_MSG = (
    "<b>WordSeek 📖</b>\n\n"
    "A fun and competitive Wordle-style game that you can play directly on Telegram!\n\n"
    "1. Use <b>/new</b> to start a game. Add me to a group with admin permission to play with your friends.\n"
    "2. Use <b>/help</b> to get help on how to play and commands list.\n\n"
    "🛠 Developed by YOU\n"
    "Official Group: &lt;your group/link&gt;\n"
)

HELP_MSG = (
    f"How to play:\n"
    f"• Use /new to start a new Wordle game.\n"
    f"• Guess a {GAME_WORD_LENGTH}-letter word by sending it as a message.\n"
    "• After each guess, you'll see feedback:\n"
    "  🟩 - Correct letter in right spot\n"
    "  🟨 - Letter in word but wrong position\n"
    "  🟥 - Letter not in word\n"
    f"• You have {MAX_GUESSES} attempts to guess!\n"
    "/leaderboard for top players.\n"
)

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_message(
        m.chat.id, 
        WELCOME_MSG, 
        parse_mode="HTML"
    )

@bot.message_handler(commands=['help'])
def help_cmd(m):
    bot.send_message(m.chat.id, HELP_MSG)

@bot.message_handler(commands=['new'])
def new_game(m):
    cid = m.chat.id
    answer = get_random_word()
    games[cid] = {
        'answer': answer,
        'guesses': [],
        'active': True,
        'player': m.from_user.id if m.chat.type == 'private' else None
    }
    bot.send_message(
        cid, 
        f"🆕 New Wordle game started!\nGuess the {GAME_WORD_LENGTH}-letter word. Send your guesses (only English):"
    )

@bot.message_handler(commands=['myscore'])
def myscore(m):
    uid = m.from_user.id
    score = scores.get(uid, 0)
    bot.send_message(m.chat.id, f"🏆 Your score: {score}")

@bot.message_handler(commands=['leaderboard'])
def leaderboard(m):
    if not scores:
        bot.send_message(m.chat.id, "No scores yet.")
        return
    top = sorted(scores.items(), key=lambda x: -x[1])[:10]
    msg = "<b>🏆 Leaderboard:</b>\n"
    for i, (uid, score) in enumerate(top):
        try:
            user = bot.get_chat_member(m.chat.id, uid).user.first_name
        except:
            user = f"User {uid}"
        msg += f"{i+1}. {user}: {score}\n"
    bot.send_message(m.chat.id, msg, parse_mode="HTML")

@bot.message_handler(func=lambda m: True)
def guess_word(m):
    cid = m.chat.id
    txt = m.text.upper()
    if cid not in games or not games[cid]['active']:
        return
    if m.chat.type == 'private' and games[cid].get('player') != m.from_user.id:
        return
    if not txt.isalpha() or len(txt) != GAME_WORD_LENGTH or txt not in ALL_WORDS:
        return
    answer = games[cid]['answer']
    feedback = color_feedback(txt, answer)
    games[cid]['guesses'].append((txt, feedback))
    bot.send_message(cid, f"<code>{txt}</code>\n{feedback}", parse_mode="HTML")
    if txt == answer:
        bot.send_message(cid, f"🎉 Correct! The answer was: <b>{answer}</b>", parse_mode="HTML")
        uid = m.from_user.id
        scores[uid] = scores.get(uid, 0) + 1
        games[cid]['active'] = False
    elif len(games[cid]['guesses']) >= MAX_GUESSES:
        bot.send_message(cid, f"❌ Out of guesses! The word was: <b>{answer}</b>", parse_mode="HTML")
        games[cid]['active'] = False

if __name__ == '__main__':
    print("Bot running...")
    bot.infinity_polling()
