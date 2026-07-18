#!/usr/bin/env python3
from random import seed, randrange
from library import load, peek, answer

seed(0xDEADBEEF42)

n, x = load()
for _ in range(100):
    pos = randrange(0, n)
    if peek(pos) == x:
        answer(pos)
answer(-1)
