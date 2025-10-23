#!/usr/bin/env python3
import os
import sys
from typing import NoReturn

SUBTASK_POINTS = [0, 20, 30, 50]


def award(points: float | None, msg: str) -> NoReturn:
    assert "\n" not in msg
    print(msg, file=sys.stderr)
    print(f"POINTS={points}", file=sys.stderr)
    exit(42)


def reject(msg: str) -> NoReturn:
    assert "\n" not in msg
    print(msg, file=sys.stderr)
    exit(43)


def main(subtask: int, seed: str) -> NoReturn:
    # Read the test input
    with open(os.environ["TEST_INPUT"]) as f:
        n, k = map(int, f.readline().split())

    # Read the contestant output
    try:
        numbers = list(map(int, input().split()))
    except ValueError:
        reject("The output should contain integers.")
    except EOFError:
        reject("The output is empty.")

    try:
        input()
        reject("The output should contain only one line.")
    except EOFError:
        pass

    # Be careful to check **ALL** constraints
    if any(map(lambda x: x <= 0, numbers)):
        reject("The output contains negative integers.")

    if sum(numbers) == k:
        award(SUBTASK_POINTS[subtask], "All of the sand used.")
    elif sum(numbers) >= k / 2:
        award(SUBTASK_POINTS[subtask] // 2, "At least half of the sand used.")
    else:
        reject("Not enough sand used.")


if __name__ == "__main__":
    main(subtask=int(sys.argv[1]), seed=sys.argv[2])
