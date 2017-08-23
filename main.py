#!/usr/bin/env python

import os
import logging
from datetime import datetime, time, timedelta
from functools import wraps
from collections import defaultdict
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from pony import orm
from database import db, Question, User, Update
from mail import send_out_weekly_recap

BOT_TOKEN = os.environ['VIJOURNALBOT_TOKEN']
PASSWORD = os.environ['VIJOURNALBOT_PASSWORD']
NOTIFIER_LAST_RUN = datetime.now()

class Session(object):
    """In memory state of a chat session"""
    def __init__(self):
        self.remaining_questions = []
        self.authorized = False
    
    def advance_question(self):
        """advances to the next question"""
        if self.remaining_questions:
            return self.remaining_questions.pop()
        else:
            return None

    def current_question(self):
        """returns the current question if any"""
        if self.remaining_questions:
            return self.remaining_questions[-1]
        else:
            return None

    def set_questions(self, questions):
        self.remaining_questions = list(reversed(questions))

# Keeps a chat_id -> sessionData mapping
SESSIONS = defaultdict(Session)

@orm.db_session
def init_session(chat_id):
    """loads session data for a given chat_id"""

    session = SESSIONS[chat_id]
    if not session.authorized:
        user = User.get(chat_id=chat_id)
        if user:
            session.authorized = True
    return session

def chat_session(handler):
    """handles authentication and provides a `session` object to handlers"""

    @wraps(handler)
    def func_wrapper(bot, update, *args, **kwargs):
        chat_id = update.message.chat_id
        session = init_session(chat_id)
        
        if not session.authorized:
            bot.send_message(chat_id=chat_id, text="Unauthenticated, run /start <password>")
            return

        handler(session, bot, update, *args, **kwargs)

    return func_wrapper

@orm.db_session
def handle_start(bot, update, **kwargs):
    """Handles start message, authenticating and creating User objects"""
    chat_id = update.message.chat_id
    args = kwargs.get('args')

    if args[0] != PASSWORD:
        bot.send_message(chat_id=chat_id, text="Not Authenticated")
        return

    session = SESSIONS[chat_id]
    session.authorized = True
    bot.send_message(chat_id=chat_id, 
                    text="Succesfully authenticated. Send messages to be logged in your journal")

    user = User.get(chat_id=chat_id)
    if not user:
        User(chat_id=chat_id, reminder_time=time(20, 30))

def ask_one(bot, chat_id):
    """Asks a single question to the user"""
    question = SESSIONS[chat_id].current_question()
    if question:
        bot.send_message(chat_id=chat_id, text=question.text)
    else:
        bot.send_message(chat_id=chat_id, text="You've answered all questions!")

@chat_session
@orm.db_session
def handle_message(session, bot, update):
    """Handles incoming messages"""
    chat_id = update.message.chat_id
    current_question = session.current_question()

    Update(text=update.message.text,
           timestamp=datetime.now(),
           answers=current_question.id if current_question else None,
           user=chat_id)

    if current_question:
        session.advance_question()
        ask_one(bot, chat_id)
    else:
        bot.send_message(chat_id=chat_id, text="Logged")

@chat_session
@orm.db_session
def handle_ask(session, bot, update):
    """Starts asking the user a series of questions"""
    chat_id = update.message.chat_id
    session.set_questions(list(orm.select(q for q in Question if q.enabled)))
    ask_one(bot, chat_id)

def question_list(chat_id):
    """Returns a list of defined questions"""
    questions = orm.select(q for q in Question if q.enabled and q.user.chat_id == chat_id)[:]
    text = "\n".join("{}: {}".format(q.id, q.text) for q in questions) or "No questions"
    return text

@chat_session
@orm.db_session
def handle_question_list(session, bot, update):
    """Replies with the list of defined questions"""
    chat_id = update.message.chat_id
    bot.send_message(chat_id=chat_id, text=question_list(chat_id))

@chat_session
@orm.db_session
def handle_add_question(session, bot, update):
    """Adds a question"""
    chat_id = update.message.chat_id
    qtext = update.message.text.replace("/add ", "")
    Question(enabled=True, text=qtext, user=update.message.chat_id)
    
    bot.send_message(chat_id=update.message.chat_id, text="Question added")
    bot.send_message(chat_id=chat_id, text=question_list(chat_id))

@chat_session
@orm.db_session
def handle_email(session, bot, update):
    """Adds a question"""
    chat_id = update.message.chat_id
    email = update.message.text.replace("/email ", "").strip()
    user = User.get(chat_id=chat_id)
    if email:
        user.email = email
        bot.send_message(chat_id=update.message.chat_id, text="Email updated")
    else:
        bot.send_message(chat_id=update.message.chat_id, text="Current mail: " + user.email)

@chat_session
@orm.db_session
def handle_del_question(session, bot, update, **kwargs):
    """Disables a question given its id"""
    chat_id = update.message.chat_id

    args = kwargs.get('args')
    qid = int(args[0])
    question = Question[qid]
    if question.answers.count() > 0:
        question.enabled = False
    else:
        question.delete()

    bot.send_message(chat_id=chat_id, text="Question deleted")
    bot.send_message(chat_id=chat_id, text=question_list(chat_id))

@chat_session
def handle_stop(session, bot, update):
    session.set_questions([])
    bot.send_message(chat_id=update.message.chat_id, text="asking stopped")

def error_callback(bot, update, error):
    logging.error(error)
    if update and update.message and update.message.chat_id:
        bot.send_message(chat_id=update.message.chat_id, text="There was an error, sorry")

@orm.db_session
def reminder_sender(bot, job):
    global NOTIFIER_LAST_RUN

    last_time = NOTIFIER_LAST_RUN.time()
    time_now = datetime.now().time()
    users_to_notify = orm.select(u for u in User if u.reminder_time > last_time and u.reminder_time < time_now )

    for user in users_to_notify:
        chat_id = user.chat_id
        session = SESSIONS[chat_id]
        session.set_questions(list(orm.select(q for q in Question if q.enabled and q.user == user)))
        ask_one(bot, chat_id)

    NOTIFIER_LAST_RUN = datetime.now()

def weekly_recap():
    if datetime.now().isoweekday == 7:
        send_out_weekly_recap()

def setup():
    """Sets up the bot"""
    
    db.bind(provider='sqlite', filename='./data/database.sqlite', create_db=True)
    db.generate_mapping(create_tables=True)
    orm.sql_debug(True)

    updater = Updater(token=BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_error_handler(error_callback)

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    dispatcher.add_handler(CommandHandler('start', handle_start, pass_args=True))
    dispatcher.add_handler(CommandHandler('questions', handle_question_list))
    dispatcher.add_handler(CommandHandler('add', handle_add_question))
    dispatcher.add_handler(CommandHandler('del', handle_del_question, pass_args=True))
    dispatcher.add_handler(CommandHandler('stop', handle_stop))
    dispatcher.add_handler(CommandHandler('ask', handle_ask))
    dispatcher.add_handler(CommandHandler('email', handle_email))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_message))

    updater.job_queue.run_repeating(weekly_recap, timedelta(days=1), first=time(23,50))
    updater.job_queue.run_repeating(reminder_sender, 60.0 * 10)

    updater.start_polling()

    logging.info("Bot started")
    updater.idle()

if __name__ == '__main__':
    setup()
