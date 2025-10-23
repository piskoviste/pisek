#!/usr/bin/env python3
import itertools
import random
import sys


def gen(test: int) -> None:
    max_n = 10**5
    max_k = 10**5 if test == 2 else 10**9

    # Dividing max_n by four actually makes stronger tests
    # as sandcastles of size 1 doesn't use half of the sand
    n = random.randint(1, max_n // 4)
    k = random.randint(n, max_k)

    if test == 1:
        k = n

    print(n, k)


random.seed(sys.argv[2])
gen(int(sys.argv[1]))
