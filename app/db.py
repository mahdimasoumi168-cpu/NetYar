"""Compatibility shim for the unified NetYar database.

The production application uses ``core.db`` as the single SQLite database.
This module is kept only for older imports so legacy code does not create a
second ``netyar.sqlite3`` database.
"""

from core import db


def connect():
    return db.conn


def init_db():
    """Database initialization is handled by ``core.Database``."""
    return db


def create_payment(*args, **kwargs):
    raise RuntimeError("Online gateway payments are disabled; use the current manual/partner payment flow.")


def get_payment(*args, **kwargs):
    raise RuntimeError("Online gateway payments are disabled; use the current manual/partner payment flow.")


def set_token(*args, **kwargs):
    raise RuntimeError("Online gateway payments are disabled; use the current manual/partner payment flow.")


def set_result(*args, **kwargs):
    raise RuntimeError("Online gateway payments are disabled; use the current manual/partner payment flow.")
