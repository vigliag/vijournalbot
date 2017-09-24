## VIJOURNALBOT

This is a stupid Telegram bot for keeping a journal. It periodically reminds you to write, and asks you questions

### Environment variables

- VIJOURNALBOT_TOKEN: telegram bot token
- VIJOURNALBOT_PASSWORD: password to recognize users allowed to use the bot
- VIJOURNALBOT_SMTP_LOGIN: login to the smtp service to send weekly recaps
- VIJOURNALBOT_SMTP_PASSWORD
- VIJOURNALBOT_SMTP_SERVER
- VIJOURNALBOT_SMTP_PORT

### Commands

- `start <password>` to authorize the current chat
- `questions` to list the entered questions
- `add <question_id>` to add more questions
- `del <question_id>` to remove questions
- `stop` to stop asking questions (clears the session) and return to idle
- `ask` prompts the system to ask you questions now
- any other text will be logged
- questions are automatically asked every evening at 20:30 UTC
- an email recap is automatically sent on sundays 22:50 UTC
