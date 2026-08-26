"""Case rewards for promo codes.

Promo codes already support reward_type=case:* in the admin UI, but the old
redemption path only understood money and unit rewards. Keep the existing
redemption path untouched for those rewards and add a small persistent case
inventory for case promo rewards.
"""
import run
from db import connect

_ORIGINAL = run.use_promo_extended

CASE_NAMES = {
    'case1': '📦 Кейс 1',
    'case2': '📦 Кейс 2',
    'donate_case': '🎖 Президентский кейс',
}


async def _ensure_case_inventory(db):
    await db.execute('''CREATE TABLE IF NOT EXISTS user_cases (
        user_id INTEGER NOT NULL,
        case_id TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, case_id)
    )''')


async def use_promo_extended(message, code):
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT * FROM promos WHERE lower(code)=lower(?)',
            (code.strip(),),
        )
        promo = await cur.fetchone()
        if not promo:
            return await message.answer('❌ Промокод не найден.')
        if int(promo['uses']) >= int(promo['max_uses']):
            return await message.answer('❌ Промокод больше недоступен.')
        cur = await db.execute(
            'SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',
            (promo['code'], message.from_user.id),
        )
        if await cur.fetchone():
            return await message.answer('❌ Вы уже использовали этот промокод.')

        reward_type = str(promo['reward_type'] or 'money')
        amount = int(promo['reward_amount'] or promo['amount'] or 0)

        if reward_type.startswith('case:'):
            case_id = reward_type.split(':', 1)[1]
            if case_id not in CASE_NAMES or amount <= 0:
                return await message.answer('❌ Промокод содержит некорректный кейс.')
            await _ensure_case_inventory(db)
            await db.execute(
                '''INSERT INTO user_cases(user_id,case_id,count) VALUES(?,?,?)
                   ON CONFLICT(user_id,case_id) DO UPDATE SET count=count+excluded.count''',
                (message.from_user.id, case_id, amount),
            )
            reward_text = f'{CASE_NAMES[case_id]} × {amount}'
        elif reward_type == 'money':
            await db.execute(
                'UPDATE users SET balance=balance+? WHERE user_id=?',
                (amount, message.from_user.id),
            )
            reward_text = f'💵 +${run.app.money(amount)}'
        elif reward_type.startswith('unit:'):
            unit = reward_type.split(':', 1)[1]
            if unit not in run.UNITS or amount <= 0:
                return await message.answer('❌ Промокод содержит некорректную технику.')
            await db.execute(
                f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',
                (amount, message.from_user.id),
            )
            reward_text = f'{run.UNITS[unit]["title"]} × {amount}'
        else:
            return await message.answer('❌ Неизвестный тип награды промокода.')

        await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?', (promo['code'],))
        await db.execute(
            'INSERT INTO promo_uses(code,user_id) VALUES(?,?)',
            (promo['code'], message.from_user.id),
        )
        await db.commit()
    finally:
        await db.close()

    return await message.answer(f'🎉 Промокод активирован!\n\nНаграда: {reward_text}')


run.use_promo_extended = use_promo_extended
print('[OAM] CASE PROMO REWARDS: ON')
