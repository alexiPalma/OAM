"""Disabled compatibility bootstrap.

fix.py is the only runtime entrypoint. Legacy automatic imports and global
monkey patches are intentionally disabled so they cannot overwrite callbacks
or battle logic at interpreter startup.
"""
