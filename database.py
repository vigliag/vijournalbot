from pony import orm
from datetime import datetime, time
db = orm.Database()

class Question(db.Entity):
    """Represents a question the user wants to be asked daily"""
    enabled = orm.Required(bool)
    options = orm.Optional(str)
    text = orm.Required(str)
    answers = orm.Set('Update')
    user = orm.Required('User')

class Update(db.Entity):
    """Represents a single update in the database"""
    timestamp = orm.Required(datetime)
    text = orm.Required(str)
    user = orm.Required('User')
    answers = orm.Optional(Question)
    message_id = orm.Optional(int)

class User(db.Entity):
    """Represents a single user, to notify periodically"""
    chat_id = orm.PrimaryKey(int)
    email = orm.Optional(str)
    reminder_time = orm.Optional(time)
    #last_reminded = orm.Optional(datetime)
    #last_mail_summary = orm.Optional(datetime)
    questions = orm.Set(Question)
    updates = orm.Set(Update)