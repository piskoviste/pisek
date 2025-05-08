#!/usr/bin/env python3
import os
import sys
import subprocess

inp = sys.stdin.read()
program_dir = os.path.dirname(sys.argv[0])
subprocess.run(os.path.join(program_dir, "solve"), input=inp.encode())
