"""Pequenos helpers compartilhados apenas pela camada HTTP."""

from __future__ import annotations


_MAX_REQUEST_INTEGER = (1 << 63) - 1


def optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
        return parsed if -_MAX_REQUEST_INTEGER <= parsed <= _MAX_REQUEST_INTEGER else None
    except ValueError:
        return None


def plural(value: int, singular: str, plural_form: str) -> str:
    return singular if value == 1 else plural_form
