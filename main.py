import os
import random
import requests
import telebot
import threading
import time
from config import BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN)

WORD_LENGTH = 5
INIT_GUESS_TIME = 120    # Initial time: 2 min
MIN_GUESS_TIME = 15      # Minimum per guess: 15 sec

def get_word_list():
    url = 'https://raw.githubusercontent.com/dwyl/english-words/master/words_dictionary.json'
    resp = requests.get(url)
    words_dict = resp.json()
    return [w.upper() for w in words_dict if len(w) == WORD_LENGTH and w.isalpha()]

ALL_WORDS = get_word_list()

def get_random_word():
    return random.choice(ALL_WORDS)

def color_feedback(guess, answer):
    feedback = ""
    answer_chars = list(answer)
    guess_chars = list(guess)
    for i in range(WORD_LENGTH):
        if guess_chars[i] == answer_chars[i]:
            feedback += "🟩"
            answer_chars[i] = None
        else:
            feedback += "*"
    for i in range(WORD_LENGTH):
        if feedback[i] == "🟩":
            continue
        if guess_chars[i] in answer_chars:
            idx = answer_chars.index(guess_chars[i])
            answer_chars[idx] = None
            feedback = feedback[:i] + "🟨" + feedback[i+1:]
        else:
            feedback = feedback[:i] + "🟥" + feedback[i+1:]
    return feedback

def dev_button_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("Owner", url="https://t.me/Kittu_the_meoww"),
        telebot.types.InlineKeyboardButton("Support", url="https://t.me/chuckymusic_support")
    )
    return markup

games = {}
scores = {}

WELCOME_MSG = (
    "<b>WordSeek 📖</b>\n\n"
    "• Multi-player or Solo Wordle mode!\n"
    "• Use /new for competitive group. \n"
    "• Use /solo to play alone.\n"
    "• Each round time reduces (never below 15 sec).\n"
    "• Only timeout causes OUT—not invalid word.\n"
)
HELP_MSG = (
    "• /new  : Group game \n"
    "• /solo : Solo Game \n"
    "• /join : play with your Friends \n"
    "• Each round, time reduces (never <15sec)\n"
    "• Only timeout causes OUT, wrong/short/invalid word just errors\n"
    "• Emoji/word trail + leaderboard\n"
)

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_message(
        m.chat.id, WELCOME_MSG, parse_mode="HTML", reply_markup=dev_button_markup()
    )

@bot.message_handler(commands=['help'])
def help_cmd(m):
    bot.send_message(
        m.chat.id, HELP_MSG, parse_mode="HTML", reply_markup=dev_button_markup()
    )

@bot.message_handler(commands=['leaderboard'])
def leaderboard(m):
    if not scores:
        bot.send_message(m.chat.id, "No wins yet.")
        return
    top = sorted(scores.items(), key=lambda x: -x[1])[:10]
    msg = "<b>🏆 Leaderboard (Wins):</b>\n"
    for i, (uid, score) in enumerate(top):
        try:
            user = bot.get_chat_member(m.chat.id, uid).user.first_name
        except Exception:
            user = f"User {uid}"
        msg += f"{i+1}. {user}: {score}\n"
    bot.send_message(m.chat.id, msg, parse_mode="HTML")

# ---- COMPETITIVE MODE ----
def get_time_for_round(round_num):
    # Each round time decrements by 10s, never below min
    t = INIT_GUESS_TIME - (round_num-1)*10
    return max(MIN_GUESS_TIME, t)

def start_game_after_join(cid):
    game = games[cid]
    if len(game['players']) < 2:
        bot.send_message(cid, "⏰ Time over, no one joined in time or not enough players (min 2 needed). Cancelled.")
        del games[cid]; return
    random.shuffle(game['players'])
    bot.send_message(cid,
        f"🟢 Game started ({len(game['players'])} players):\n" +
        "\n".join(f"{i+1}. <a href='tg://user?id={uid}'>{game['players_names'][uid]}</a>" for i, uid in enumerate(game['players'])),
        parse_mode="HTML"
    )
    game['playing'], game['turn_index'], game['round'] = True, 0, 1
    start_turn(cid)

def start_turn(cid):
    game = games[cid]
    # IF only one left -> winner
    if len(game['players']) == 1:
        winner_id = game['players'][0]
        winname = game['players_names'][winner_id]
        bot.send_message(cid, f"🏆 <b>{winname}</b> wins this game!", parse_mode="HTML")
        scores[winner_id] = scores.get(winner_id, 0)+1
        del games[cid]; return
    # New word/round
    word = get_random_word()
    game['word'], game['guesses_trail'] = word, []
    uid = game['players'][game['turn_index']]
    uname = game['players_names'][uid]
    time_allowed = get_time_for_round(game['round'])
    bot.send_message(cid,
        f"🎯 <a href='tg://user?id={uid}'>{uname}</a> - Your turn!\n" +
        f"Guess the {WORD_LENGTH} letter word!\nTime: {time_allowed} sec.",
        parse_mode="HTML"
    )
    timer = threading.Thread(target=turn_timer_thread, args=(cid, uid, time.time(), time_allowed))
    timer.start()
    game['turn_start'], game['timer_thread'], game['time_allowed'] = time.time(), timer, time_allowed

def turn_timer_thread(cid, uid, starttime, time_allowed):
    warned = False
    while True:
        now = time.time()
        left = time_allowed - (now-starttime)
        game = games.get(cid)
        if not game or not game['playing'] or game['players'][game['turn_index']] != uid:
            return
        if left <= 0:
            # OUT!
            out_name = game['players_names'][uid]
            bot.send_message(cid, f"⏰ <b>{out_name}</b> OUT (timeout)!", parse_mode="HTML")
            # remove
            game['players'].remove(uid)
            if game['turn_index'] >= len(game['players']): game['turn_index'] = 0
            game['round'] += 1
            start_turn(cid)
            return
        elif left <= 30 and not warned:
            bot.send_message(cid, "⚠️ 30 seconds left!")
            warned = True
        time.sleep(2)

@bot.message_handler(commands=['new'])
def new_game(m):
    cid = m.chat.id
    if cid in games:
        bot.send_message(cid, "A game is already running here!")
        return
    games[cid] = {'players':[],
                  'players_names':{},
                  'playing':False,
                  'join_start':time.time()}
    bot.send_message(cid,
        "🟢 Competition starting! Use /join to participate (2 min window, min 2).\nEach round guess time reduces.")
    threading.Thread(target=joiner_timer_thread, args=(cid, time.time())).start()

def joiner_timer_thread(cid, start_at):
    time.sleep(JOIN_TIME)
    if games.get(cid,{}).get('playing',False): return
    start_game_after_join(cid)

@bot.message_handler(commands=['join'])
def join_game(m):
    cid = m.chat.id
    uid = m.from_user.id
    if cid not in games or games[cid].get('playing',False):
        bot.send_message(cid, "No joinable game! Use /new")
        return
    game = games[cid]
    if uid in game['players']:
        bot.send_message(cid, "Already joined!")
        return
    game['players'].append(uid)
    game['players_names'][uid] = m.from_user.first_name
    bot.send_message(cid,
        f"✅ <a href='tg://user?id={uid}'>{game['players_names'][uid]}</a> joined!",
        parse_mode="HTML"
    )

# ---- SOLO MODE ----
solo_games = {}

def start_solo(cid, uid):
    solo_games[(cid,uid)] = {
        'round':1, 'active':True, 'trail':[], 'word':get_random_word(),
        'start_time':time.time(), 'time_allowed':get_time_for_round(1)
    }
    allowed = solo_games[(cid,uid)]['time_allowed']
    bot.send_message(cid, f"🟢 Solo game started!\nRound 1\nGuess the {WORD_LENGTH}-letter word.\nTime: {allowed} sec")
    threading.Thread(target=solo_timer_thread, args=(cid,uid,allowed,time.time())).start()

def solo_timer_thread(cid, uid, allowed, starttime):
    warned = False
    while True:
        now = time.time()
        left = allowed - (now-starttime)
        game = solo_games.get((cid,uid))
        if not game or not game['active']: return
        if left <= 0:
            bot.send_message(cid, f"⏰ Time up! You lost this solo game.")
            del solo_games[(cid,uid)]
            return
        elif left <= 30 and not warned:
            bot.send_message(cid, ("⚠️ 30 seconds left!"))
            warned = True
        time.sleep(2)

@bot.message_handler(commands=['solo'])
def solo_game(m):
    cid = m.chat.id; uid = m.from_user.id
    if (cid,uid) in solo_games:
        bot.send_message(cid,"Solo game already running here!")
        return
    start_solo(cid,uid)

@bot.message_handler(func=lambda m: True)
def guess_word(m):
    cid = m.chat.id; uid = m.from_user.id; txt = m.text.strip().upper()
    # Competitive
    if cid in games and games[cid].get('playing',False) and len(games[cid]['players'])>=1:
        game = games[cid]
        # Check if current turn
        if game['players'][game['turn_index']] != uid: return
        time_allowed = game['time_allowed']
        word = txt
        # Length check
        if not word.isalpha() or len(word)!=WORD_LENGTH:
            bot.send_message(cid, f"❌ Word must be exactly {WORD_LENGTH} letters",parse_mode="HTML"); return
        # Invalid word check
        if word not in ALL_WORDS:
            bot.send_message(cid, f"❌ <b>{word}</b> is not a valid word",parse_mode="HTML"); return
        # Feedback + trail
        fb = color_feedback(word,game['word'])
        game['guesses_trail'].append((word,fb))
        trail = "\n".join(f"{fb}  <b>{g}</b>" for g,fb in game['guesses_trail'])
        bot.send_message(cid, trail, parse_mode="HTML")
        if word == game['word']:
            winname = game['players_names'][uid]
            bot.send_message(cid, f"🏆 <b>{winname}</b> guessed correctly!",parse_mode="HTML")
            scores[uid] = scores.get(uid, 0)+1
            del games[cid]
        else:
            # Next turn
            game['round'] += 1
            game['turn_index'] = (game['turn_index']+1)%len(game['players'])
            start_turn(cid)
        return

    # SOLO
    if (cid,uid) in solo_games:
        game = solo_games[(cid,uid)]
        if not game['active']: return
        word = txt
        if not word.isalpha() or len(word)!=WORD_LENGTH:
            bot.send_message(cid, f"❌ Word must be exactly {WORD_LENGTH} letters",parse_mode="HTML"); return
        if word not in ALL_WORDS:
            bot.send_message(cid, f"❌ <b>{word}</b> is not a valid word",parse_mode="HTML"); return
        fb = color_feedback(word,game['word'])
        game['trail'].append((word,fb))
        trail = "\n".join(f"{fb}  <b>{g}</b>" for g,fb in game['trail'])
        bot.send_message(cid, trail, parse_mode="HTML")
        if word == game['word']:
            bot.send_message(cid, f"🏆 You WIN! Guessed correctly.",parse_mode="HTML")
            scores[uid] = scores.get(uid,0)+1
            del solo_games[(cid,uid)]
        else:
            game['round'] +=1
            next_time = get_time_for_round(game['round'])
            game['word'] = get_random_word()
            game['start_time'] = time.time()
            game['time_allowed'] = next_time
            bot.send_message(cid, f"Next round!\nGuess the word. Time: {next_time} sec")
            threading.Thread(target=solo_timer_thread, args=(cid,uid,next_time,time.time())).start()

if __name__ == '__main__':
    print("Bot running ...")
    bot.infinity_polling()
    
