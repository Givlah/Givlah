"""Single source of the current time.

Services and selectors call ``now()`` instead of ``timezone.now()`` so tests can
inject a fixed server time with ``frozen_time``.
"""

from contextlib import contextmanager

from django.utils import timezone

_override = None


def now():
    return _override if _override is not None else timezone.now()


@contextmanager
def frozen_time(moment):
    global _override
    previous, _override = _override, moment
    try:
        yield
    finally:
        _override = previous
