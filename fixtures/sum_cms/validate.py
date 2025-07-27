#!/usr/bin/env python3
# Validator based on Kasiopea's validator template from Pali Madaj.
import sys
import argparse


def main(diff):
    BOUNDS = [(-1e18, 1e18), (0, 1e9), (-1e9, 1e9), (-1e18, 1e18)]
    assert 0 <= diff < len(BOUNDS)
    read_values(2, *BOUNDS[diff])


# ----------------- Cast nize jsou pomocne funkce, snad nebude treba upravovat -----------------

line_number = 0


def read_line():
    global line_number
    line_number += 1
    return input()


def fail(message):
    global line_number
    print(message + " (on line {})".format(line_number), file=sys.stderr)
    sys.exit(1)


def read_values(count=None, minimum=None, maximum=None, value_type=int):
    try:
        line = read_line()
    except EOFError:
        fail("Unexpected end of file.")

    try:
        numbers = list(map(value_type, line.split(" ")))
    except ValueError as err:
        fail(str(err))

    if count is not None and len(numbers) != count:
        fail(
            "The number of values was {} and should have been {}.".format(
                len(numbers), count
            )
        )
    if minimum is not None and any(x < minimum for x in numbers):
        fail("A value was smaller than {}.".format(minimum))
    if maximum is not None and any(x > maximum for x in numbers):
        fail("A value was greater than {}.".format(maximum))

    return numbers


def expect_eof():
    koniec = False
    try:
        input()
    except EOFError:
        koniec = True
    if not koniec:
        fail("The file continues, but it should have ended.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loads an input from stdin and validates it."
    )
    parser.add_argument("test", type=int, help="test number (0-3)")
    args = parser.parse_args()
    main(args.test)
    expect_eof()
    exit(42)
