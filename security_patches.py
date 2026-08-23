"""Security helpers retained from the original project.
The main bot now performs validation directly in its handlers; this module is kept
for compatibility with the transferred project structure.
"""
from asyncio import Lock

USER_LOCKS={}

def user_lock(uid):
    return USER_LOCKS.setdefault(uid,Lock())
