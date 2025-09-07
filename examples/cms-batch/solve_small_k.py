#!/usr/bin/env python3

n, k = map(int, input().split())

sandcastles = [0] * n
for i in range(k):
    sandcastles[i % n] += 1
print(" ".join(map(str, sandcastles)))
