#!/usr/bin/env python3
import sys
from typing import NoReturn


def award(points: float, msg: str) -> NoReturn:
    print(points)
    print(msg, file=sys.stderr)
    exit(0)


def reject() -> NoReturn:
    award(0, "translate:wrong")


input_, correct_output, contestant_output = sys.argv[1:]

with open(input_) as f:
    n, k = map(int, f.readline().split())

with open(contestant_output) as f:
    try:
        numbers = list(map(int, f.readline().split()))
    except ValueError:
        reject()  # The contestant did not print integers
    except EOFError:
        reject()  # The contestant output ends

    if f.read().strip():
        reject()  # Contestant output doesn't end when it should


# Be careful to check **ALL** constraints
if any(map(lambda x: x <= 0, numbers)):
    reject()

if sum(numbers) == k:
    award(1.0, "translate:success")
elif sum(numbers) >= k / 2:
    award(0.5, "translate:partial")
else:
    reject()  # Not enough sand used
