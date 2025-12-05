#!/usr/bin/env python3
import os

assert os.environ["TASK"] == "max"
assert os.environ["DBG"] == "false_false"

input()
print(max(map(int, input().split())))
