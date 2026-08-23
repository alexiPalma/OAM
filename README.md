# WorldWarDynasty

Telegram game bot based on the transferred Voennabot project.

## Run

1. Install Python 3.11+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`.
4. Set `BOT_TOKEN` and `OWNER_ID`.
5. Run `python bot.py`.

The owner is the value of `OWNER_ID` (currently configured by the project owner as `1456274593`).

The admin panel is opened from `/start` and contains the economy, bonuses, cases, earning tasks, donations, admins, giving units/cash, broadcasts, statistics and editing sections.

## Earning tasks

The admin earning menu has exactly three types:

- 🚀 Channel boost
- 📢 Channel subscription
- 👥 Group subscription

Commands:

`/addboost https://t.me/... 150000`

`/addchannel https://t.me/... 150000`

`/addgroup https://t.me/... 150000`
