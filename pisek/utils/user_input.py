from colorama import Cursor
from readchar import readkey, key
from typing import Sequence, TypeVar

from pisek.utils.colors import ColorSettings

T = TypeVar("T")


def input_string(message: str) -> str:
    inp = ""
    while not inp:
        inp = input(message).strip()
    return inp


def input_choice(message: str, choices: Sequence[tuple[T, str]], no_jumps: bool) -> T:
    if no_jumps:
        return input_choice_no_jumps(message, choices)

    assert choices

    print(message)

    selected = 0
    while True:
        for i, (_, text) in enumerate(choices):
            full_text = f" {i+1}. {text}"
            if selected == i:
                selector = ColorSettings.colored(">", "cyan")
                print(ColorSettings.colored_back(selector + full_text, "lightblack_ex"))
            else:
                print(" " + full_text)

        k = readkey()
        if k in (key.SPACE, key.ENTER):
            return choices[selected][0]
        elif k in "123456789":
            selected = min(int(k) - 1, len(choices) - 1)
        elif k == key.DOWN:
            selected = (selected + 1) % len(choices)
        elif k == key.UP:
            selected = (selected - 1) % len(choices)

        print(Cursor.UP() * len(choices), end="")


def input_choice_no_jumps(message: str, choices: Sequence[tuple[T, str]]) -> T:
    assert choices

    print(message)

    for i, (_, text) in enumerate(choices):
        full_text = f" {i+1}. {text}"
        print(" " + full_text)

    while True:
        try:
            selected = int(input(f"Enter number from 1 to {len(choices)}: ")) - 1
            if 0 <= selected < len(choices):
                return choices[selected][0]
        except ValueError:
            pass
