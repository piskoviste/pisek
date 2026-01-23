# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2026        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from argparse import ArgumentTypeError
from decimal import Decimal, InvalidOperation


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


def argparse_nonnegative_Decimal(
    value: str, type_str: str = "non-negative decimal"
) -> Decimal:
    dvalue = argparse_Decimal(value, type_str)
    if dvalue < 0:
        raise ArgumentTypeError(f"invalid {type_str} value: '{value}'")
    return dvalue
