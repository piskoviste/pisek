#!/usr/bin/env python3
import itertools
import random
import sys

FEATURES = ["few", "small", "equal", "max"]


def gen(input_name: str) -> None:
    max_n = 10 if "few" in input_name else 10**5
    max_k = 10**5 if "small" in input_name else 10**9

    if "max" in input_name:
        n = max_n
        k = max_k
    else:
        n = random.randint(1, max_n)
        k = random.randint(n, max_k)

    if "equal" in input_name:
        k = n

    print(n, k)


# No arguments - List all inputs we can generate
if len(sys.argv) == 1:
    for variant in itertools.product([True, False], repeat=4):
        features = [f for i, f in enumerate(FEATURES) if variant[i]]
        if "equal" in features and "small" not in features:
            continue  # Any equal input is small

        if features:
            print("_".join(features), end=" ")
            if "max" in features:
                # max is deterministic - no need for seed
                print("seeded=false")
            else:
                # Otherwise generate this input three times
                print("repeat=3")
        else:
            print("big repeat=5")

# Generate an input
else:
    # Input is seeded
    if len(sys.argv) == 3:
        random.seed(sys.argv[2])

    gen(sys.argv[1])
