from colorama import Cursor
from readchar import readkey, key
from typing import Sequence, TypeVar

from pisek.utils.text import stop
from pisek.utils.colors import ColorSettings

T = TypeVar("T")


def input_string(message: str) -> str:
    return input(message)


def input_choice(message: str, choices: Sequence[tuple[T, str]]) -> T:
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

        try:
            k = readkey()
        except KeyboardInterrupt:
            stop()
        if k in (key.SPACE, key.ENTER):
            return choices[selected][0]
        elif k in "123456789":
            selected = min(int(k) - 1, len(choices) - 1)
        elif k == key.DOWN:
            selected = (selected + 1) % len(choices)
        elif k == key.UP:
            selected = (selected - 1) % len(choices)

        print(Cursor.UP() * len(choices), end="")
