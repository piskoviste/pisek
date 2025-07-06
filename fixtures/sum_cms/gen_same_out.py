#!/usr/bin/env python3
# Generates inputs that all have the same answer

import random
import sys
import os

test_dir = sys.argv[1]
os.makedirs(test_dir, exist_ok=True)

ANS = 12345

POSITIVE_ONLY = [True, False, False]
MAX_ABS = [int(1e9), int(1e9), int(1e18)]

random.seed(123)

for test_i, (positive_only, max_abs) in enumerate(zip(POSITIVE_ONLY, MAX_ABS)):
    for ti in range(5):

        if positive_only:
            a = random.randint(0, ANS)
        else:
            a = random.randint(
                max(-max_abs, ANS - max_abs), min(max_abs, ANS + max_abs)
            )

        test_filename = "{:0>2}_{:0>2}.in".format(test_i + 1, ti + 1)
        with open(os.path.join(test_dir, test_filename), "w") as f:
            f.write(f"{a} {ANS-a}\n")
