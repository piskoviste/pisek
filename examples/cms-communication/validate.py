#!/usr/bin/env python3
import sys

test = int(sys.argv[1])
MAX_VAL = 10**9
MAX_N = [10**6, 10, 1000, 10**6][test]

n, x = map(int, input().split(" "))  # We use explicitly split(" ") to be more strict
elements = list(map(int, input().split(" ")))

assert 1 <= n <= MAX_N, f"{n=} limits"
assert 1 <= x <= MAX_VAL, f"{x=} limits"

for e in elements:
    assert 1 <= e <= MAX_VAL, f"{e=} limits"
assert sorted(elements) == elements, "Not increasing"

try:
    input()
except EOFError:
    exit(42)  # The input is valid

assert False, "The input doesn't end when it should"
