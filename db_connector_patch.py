"""Compatibility fix for purchase code expecting config.connect()."""
from db import connect as _connect
import config

config.connect = _connect
print('[OAM] DB CONNECT COMPAT: ON')
