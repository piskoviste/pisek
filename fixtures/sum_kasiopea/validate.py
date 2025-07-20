#!/usr/bin/env python3
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loads an input from stdin and validates it."
    )
    parser.add_argument("test", type=int, help="test number (0-2)")
    args = parser.parse_args()

    # Here the bounds for test 3 are stricter than what the generator really creates.
    BOUNDS = [(-1e18, 1e18), (-1e9, 1e9), (-1e18, 1e18)]
    assert 0 <= args.test < len(BOUNDS)
    bounds = BOUNDS[args.test]

    t = int(input())
    for _ in range(t):
        a, b = map(int, input().split(" "))
        assert bounds[0] <= a <= bounds[1]
        assert bounds[0] <= b <= bounds[1]

    end = True
    try:
        input()
    except EOFError:
        end = True
    assert end
    exit(42)
