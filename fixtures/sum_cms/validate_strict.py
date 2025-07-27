#!/usr/bin/env python3
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Nacte ze stdin vstupy ulohy a zkontroluje jejich spravnost"
    )
    parser.add_argument("test", type=int, help="test (indexovany od 1)")
    args = parser.parse_args()

    # Here the bounds for test 3 are stricter than what the generator really creates.
    BOUNDS = [(-1e18, 1e18), (0, 1e9), (-1e9, 1e9), (-1e9, 1e9)][args.test]
    a, b = map(int, input().split(" "))
    assert BOUNDS[0] <= a <= BOUNDS[1]
    assert BOUNDS[0] <= b <= BOUNDS[1]

    end = True
    try:
        input()
    except EOFError:
        end = True
    assert end
    exit(42)
