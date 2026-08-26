"""Direct attack command support.

Supports `/атаковать @username`, `атаковать @username`, and `/attack @username`
from both private chats and groups.
"""

from db import connect, user
import fix


async def _find_by_username(username):
    name = str(username or '').strip().lstrip('@').lower()
    if not name:
        return None
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT * FROM users WHERE lower(username)=? LIMIT 1',
            (name,),
        )
        return await cur.fetchone()
    finally:
        await db.close()


async def _create_attack(message, bot, username):
    attacker_id = int(message.from_user.id)
    target = await _find_by_username(username)
    if not target:
        return await message.answer(
            '❌ Игрок с таким юзернеймом не найден.\n'
            'Он должен хотя бы один раз открыть бота через /start.'
        )

    defender_id = int(target['user_id'])
    if defender_id == attacker_id:
        return await message.answer('❌ Нельзя атаковать самого себя.')

    attacker = await user(attacker_id)
    if not attacker:
        return await message.answer('❌ Сначала открой бота через /start.')

    # Use the same cooldown/army helpers as the existing bot runtime.
    left = int(fix.app.cd_seconds(attacker))
    if left > 0:
        return await message.answer(
            f'⏳ До следующей атаки: {left // 60:02d}:{left % 60:02d}'
        )
    if int(fix.app.cd_seconds(target)) > 0:
        return await message.answer('❌ Этот игрок сейчас недоступен для атаки.')
    if fix.app.army_size(attacker) <= 0:
        return await message.answer('❌ У тебя нет армии для атаки.')
    if fix.app.army_size(target) <= 0:
        return await message.answer('❌ У этого игрока нет армии.')

    existing = await fix.get_invite(attacker_id, defender_id)
    if existing and int(existing[7]) == 0:
        return await message.answer('⏳ У тебя уже есть ожидающий запрос на бой.')

    attacker_name = '@' + attacker['username'] if attacker['username'] else f'ID {attacker_id}'
    target_name = '@' + target['username'] if target['username'] else f'ID {defender_id}'
    invite_text = (
        '⚔️ WORLDWAR DYNASTY • НА ВАС НАПАЛИ\n\n'
        f'👤 Нападающий: {attacker_name}\n\n'
        f'{fix.app.army_text(attacker)}\n\n'
        'Примите бой или откажитесь.'
    )
    keyboard = fix.app.kb([
        [('⚔️ ПРИНЯТЬ БОЙ', f'oam_accept:{attacker_id}')],
        [('🏳️ ОТКАЗАТЬСЯ', f'oam_decline:{attacker_id}')],
    ])

    try:
        defender_message = await bot.send_message(
            defender_id, invite_text, reply_markup=keyboard
        )
    except Exception:
        return await message.answer(
            f'❌ Не удалось отправить приглашение {target_name}.\n'
            'Убедись, что пользователь уже запускал бота через /start и не заблокировал его.'
        )

    db = await connect()
    try:
        await db.execute(
            '''INSERT OR REPLACE INTO oam_battle_invites
               (attacker_id, defender_id, attacker_chat_id, attacker_message_id,
                defender_chat_id, defender_message_id, created_at, running)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0)''',
            (
                attacker_id, defender_id,
                int(message.chat.id), int(message.message_id),
                defender_id, int(defender_message.message_id),
                fix.now_iso(),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return await message.answer(
        f'⏳ Атака на {target_name} отправлена. Ожидаем принятия боя.'
    )


_original_text_handler = fix.text_handler


async def patched_text_handler(message, bot):
    text = (message.text or '').strip()
    parts = text.split()
    command = parts[0].split('@')[0].lower() if parts else ''

    if command in ('/атаковать', '/attack', 'атаковать') and len(parts) >= 2:
        return await _create_attack(message, bot, parts[1])

    return await _original_text_handler(message, bot)


fix.text_handler = patched_text_handler
print('[OAM] DIRECT ATTACK COMMAND: ON')
