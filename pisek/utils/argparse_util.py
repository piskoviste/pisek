# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2026        Daniel Skýpala <skipy@kam.mff.cuni.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from argparse import ArgumentTypeError
from decimal import Decimal, InvalidOperation

from pisek.config.config_types import Limit, PositiveLimit


def argparse_Decimal(value: str, type_str: str = "decimal") -> Decimal:
    try:
        dvalue = Decimal(value)
    except InvalidOperation:
        raise ArgumentTypeError(f"invalid {type_str} value: '{value}'")
    if not dvalue.is_finite():
        raise ArgumentTypeError(f"invalid {type_str} value: '{value}'")
    return dvalue


def argparse_positive_Decimal(
    value: str, type_str: str = "positive decimal"
) -> Decimal:
    dvalue = argparse_Decimal(value, type_str)
    if dvalue <= 0:
        raise ArgumentTypeError(f"invalid {type_str} value: '{value}'")
    return dvalue


def argparse_PositiveLimit[T: int | Decimal](
    value: str, t: type[T]
) -> PositiveLimit[T]:
    try:
        limit = Limit[T].from_str(value, t)
        assert limit > 0
        return limit
    except (ValueError, AssertionError):
        raise ArgumentTypeError(
            f"invalid limit value: '{value}'. Expected positive {t.__name__} or 'unlimited'."
        )


def argparse_PositiveDecimalLimit(value: str) -> PositiveLimit[Decimal]:
    return argparse_PositiveLimit(value, Decimal)
