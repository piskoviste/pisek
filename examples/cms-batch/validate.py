#!/usr/bin/env python3
import sys

test = int(sys.argv[1])
n, k = map(int, input().split(" "))  # We use explicitly split(" ") to be more strict

assert 1 <= n <= 10**5, f"{n=} limits"
assert 1 <= k <= 10**9, f"{k=} limits"

if test == 1:
    assert n == k, "N and K should be equal"
elif test == 2:
    assert k <= 10**5, f"{k=} is too big"

try:
    input()
except EOFError:
    exit(42)  # The input is valid

assert False, "The input doesn't end when it should"
