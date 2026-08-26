"""Disabled compatibility bootstrap.

The project now has one authoritative runtime: fix.py.
Do not monkey-patch asyncio, bot callbacks, or battle handlers at Python startup.
Those old automatic patches caused multiple callback owners to coexist.
"""
