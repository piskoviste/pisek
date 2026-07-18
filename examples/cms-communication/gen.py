#!/usr/bin/env python3
import random
import sys

SIZES = {"small": 10, "medium": 1000, "big": int(1e6)}
MIN_VAL = 1
MAX_VAL = int(1e9)


def gen(n: int, contained: bool) -> None:
    values = range(MIN_VAL, MAX_VAL + 1)
    elements = sorted(random.sample(values, n))
    result = None
    while result is None or (not contained and result in elements):
        result = random.choice(elements if contained else values)
    print(n, result)
    print(*elements)


# No arguments - List all inputs we can generate
if len(sys.argv) == 1:
    for size in SIZES:
        for contained in ("with", "without"):
            print(f"{size}_{contained} repeat=3")

# Generate an input
else:
    random.seed(sys.argv[2])
    size_name, contained = sys.argv[1].split("_")
    gen(SIZES[size_name], contained == "with")
