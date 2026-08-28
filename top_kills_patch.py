"""Make Top Warriors rank by accumulated kills, preserving existing UI."""
import bot as _app
from db import connect

KILL_WEIGHTS = {
    'soldier': 1, 'interceptor': 1, 'drone': 3, 'bmp': 7,
    'artillery': 8, 'tank': 10, 'helicopter': 15,
    'plane': 25, 'missile': 50,
}

async def top_users_by_kills(limit=50):
    db = await connect()
    try:
        expr = ' + '.join(
            f'COALESCE(kill_{unit},0)*{weight}'
            for unit, weight in KILL_WEIGHTS.items()
        ) or '0'
        cur = await db.execute(
            f'''SELECT user_id, username, balance, farm_level,
                       {expr} AS army_total
                FROM users
                ORDER BY army_total DESC, attacks_won DESC, user_id ASC
                LIMIT ?''',
            (max(1, min(50, int(limit))),),
        )
        return await cur.fetchall()
    finally:
        await db.close()

_app.top_users = top_users_by_kills
print('[OAM] TOP WARRIORS: KILLS')
