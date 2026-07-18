from typing import NoReturn


def peek(pos: int) -> int:
    print(f"? {pos}", flush=True)
    x = int(input())
    if x == -1:
        exit(0)
    return x


def load() -> tuple[int, int]:
    return tuple(map(int, input().split()))


def answer(pos: int) -> NoReturn:
    print(f"! {pos}", flush=True)
    exit(0)
