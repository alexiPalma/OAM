"""Startup sanity checks for the authoritative combat engine."""
from config import UNITS
from combat import resolve


def check_combat_engine():
    attacker = {k: 0 for k in UNITS}
    defender = {k: 0 for k in UNITS}
    attacker['missile'] = 100
    attacker['interceptor'] = 100
    defender['soldier'] = 5

    _a, _d, winner, _events, kills_a, kills_d = resolve(
        attacker, defender, with_kills=True
    )

    if winner != 'attacker':
        raise RuntimeError(
            'COMBAT ENGINE CHECK FAILED: 100 missiles + 100 interceptors '
            'must defeat 5 soldiers'
        )
    if int(kills_a.get('soldier', 0)) != 5:
        raise RuntimeError(
            'COMBAT ENGINE CHECK FAILED: expected all 5 soldiers to be destroyed'
        )

    return True
