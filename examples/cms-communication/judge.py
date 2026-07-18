#!/usr/bin/env python3
import sys
from typing import NoReturn

MAX_QUERIES = 1000


def verdict(pts, msg=None) -> NoReturn:
    print(pts)

    if msg is None:
        if pts <= 0:
            msg = "translate:wrong"
        elif pts >= 1:
            msg = "translate:success"
        else:
            msg = "translate:partial"

    print(msg, file=sys.stderr)
    exit(0)


def reject(msg=None) -> NoReturn:
    verdict(0, msg)


def protocol_violation() -> NoReturn:
    verdict(0, "Protocol violation")


_, recv_name, send_name = sys.argv
n, x = map(int, input().split())
values = list(map(int, input().split()))
correct_answer = values.index(x) if x in values else -1

with open(send_name, "w") as send_pipe:
    with open(recv_name) as recv_pipe:

        def send(*x: int) -> None:
            try:
                print(*x, file=send_pipe)
                send_pipe.flush()
            except BrokenPipeError:
                protocol_violation()

        send(n, x)
        queries = 0
        while queries <= MAX_QUERIES:
            line = recv_pipe.readline().split()
            try:
                query_type, qv = line
                query_value = int(qv)
            except ValueError:
                protocol_violation()

            if query_type == "?":
                queries += 1
                if 0 <= query_value < n:
                    send(values[query_value])
                else:
                    send(-1)
                    protocol_violation()

            elif query_type == "!":
                if query_value == correct_answer:
                    verdict(1)
                else:
                    reject()  # Wrong answer

            else:
                protocol_violation()

        send(-1)
        reject()  # Too many queries
