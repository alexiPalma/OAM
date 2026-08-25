"""Small correctness pass over the final runtime patch."""
import config
import db
import bot as app

RATING = {
    'soldier': 1, 'interceptor': 1, 'drone': 3, 'bmp': 7,
    'artillery': 8, 'tank': 10, 'helicopter': 15, 'plane': 25,
    'missile': 50,
}

async def top_users(limit=50):
    conn = await db.connect()
    try:
        expr = ' + '.join(f'COALESCE({k},0)*{w}' for k,w in RATING.items())
        cols = ','.join(RATING.keys())
        cur = await conn.execute(
            f'SELECT user_id,username,balance,farm_level,{cols},{expr} AS army_total '
            'FROM users ORDER BY army_total DESC, attacks_won DESC, user_id ASC LIMIT ?',
            (max(1, min(50, int(limit))),),
        )
        return await cur.fetchall()
    finally:
        await conn.close()

db.RATING_WEIGHTS = dict(RATING)
db.top_users = top_users

async def top(c):
    rows = await top_users(50)
    lines=[]
    for i,row in enumerate(rows,1):
        medal=('🥇','🥈','🥉')[i-1] if i<=3 else '🎖️'
        name='@'+row['username'] if row['username'] else f"ID {row['user_id']}"
        equipment=', '.join(f'{config.UNITS[k]["title"]} × {int(row[k])}' for k in RATING if int(row[k])) or 'нет техники'
        lines.append(f'{medal} {i}. {app.esc(name)} — 🏆 {int(row["army_total"])} рейтинга\n   {equipment}')
    return await app.safe(c, '🏆 '+app.BRAND+' • ТОП ВОЯК\n\n'+('\n'.join(lines) or 'Пока игроков нет.'), app.back())

app.top = top
