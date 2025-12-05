import re
from colorama import Fore, Back

_ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def remove_colors(text: str) -> str:
    return _ANSI_REGEX.sub("", text)


class __ColorSettings:
    """Singleton object to store current color settings."""

    def __init__(self) -> None:
        self.colors_on = True

    def set_state(self, colors_on: bool) -> None:
        """Sets whether colors should be displayed."""
        self.colors_on = colors_on

    def _colored(self, what, msg: str, color: str) -> str:
        """Recolors all white text to given color."""
        if not self.colors_on:
            return msg

        col = getattr(what, color.upper())
        msg = msg.replace(f"{what.RESET}", f"{what.RESET}{col}")
        return f"{col}{msg}{what.RESET}"

    def colored(self, msg: str, color: str) -> str:
        return self._colored(Fore, msg, color)

    def colored_back(self, msg: str, color: str) -> str:
        return self._colored(Back, msg, color)


ColorSettings = __ColorSettings()
