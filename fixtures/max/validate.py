#!/usr/bin/env python3
def read_ints(n: int):
    inp = input()
    assert inp == inp.strip()
    ints = list(map(int, inp.split(" ")))
    assert len(ints) == n
    return ints


(n,) = read_ints(1)
nums = read_ints(n)

try:
    input()
except EOFError:
    quit(42)
raise ValueError("Input continues.")
