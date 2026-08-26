"""Keyword navigation patch.

Handles menu/navigation words directly, without the old text-keyword cooldown.
Unknown text is passed to the original handler so existing stateful flows
(promo codes, buying quantities, admin input, etc.) keep working.
"""
import re

import bot as app
import run


class _CallbackFromMessage:
    """Small adapter so existing callback screens can be reused for text."""
    def __init__(self, message):
        self.message = message
        self.from_user = message.from_user
        self.data = ''

    async def answer(self, *args, **kwargs):
        return None


_KEYWORDS = {
    'меню': 'home',
    'домой': 'home',
    'главное меню': 'home',
    'назад': 'home',
    'выйти': 'home',
    'выход': 'home',
    'топ': 'top',
    'топ вояк': 'top',
    'профиль': 'profile',
    'армия': 'army',
    'ферма': 'farm',
    'арсенал': 'shop',
    'магазин': 'shop',
    'атака': 'attack',
    'бонус': 'bonus',
    'промокод': 'promo',
    'кейсы': 'cases',
    'кейс': 'cases',
    'донат': 'donate',
    'правила': 'rules',
    'помощь': 'help',
}


def _key(text):
    text = str(text or '').strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text


async def _dispatch_keyword(message, target):
    # Leaving any previous text-input state is intentional when the user asks
    # for navigation. This makes "меню" a reliable escape hatch.
    if target == 'home':
        app.STATE.pop(message.from_user.id, None)
        return await run.home_callback(_CallbackFromMessage(message))

    app.STATE.pop(message.from_user.id, None)
    c = _CallbackFromMessage(message)
    handler = getattr(app, target, None)
    if handler is None:
        return False
    return await handler(c)


_original_text_handler = run.text_handler


async def keyword_text_handler(message, bot, *args, **kwargs):
    text = _key(getattr(message, 'text', ''))
    target = _KEYWORDS.get(text)
    if target is not None:
        # No 5-second keyword cooldown here. Every recognized navigation word
        # is handled immediately.
        return await _dispatch_keyword(message, target)
    return await _original_text_handler(message, bot, *args, **kwargs)


run.text_handler = keyword_text_handler
