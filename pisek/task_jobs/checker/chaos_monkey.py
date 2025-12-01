# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from random import Random
import string

from pisek.env.env import Env
from pisek.utils.paths import TaskPath
from pisek.task_jobs.task_job import TaskJob


def randword(length: int, rand_gen: Random):
    letters = string.ascii_lowercase
    return "".join(rand_gen.choice(letters) for _ in range(length))


class Invalidate(TaskJob):
    """Abstract Job for invalidating an output."""

    def __init__(
        self, env: Env, name: str, from_file: TaskPath, to_file: TaskPath, seed: int
    ) -> None:
        super().__init__(env, name)
        self.seed = seed
        self.from_file = from_file
        self.to_file = to_file

    def _select_line_index(self, rand_gen: Random, lines_len: int) -> int:
        assert lines_len > 0
        if lines_len <= 2 or rand_gen.randint(1, 10) == 1:
            return rand_gen.randint(0, min(1, lines_len - 1))
        else:
            return rand_gen.randint(2, lines_len - 1)


class Incomplete(Invalidate):
    """Makes an incomplete output."""

    def __init__(
        self, env: Env, from_file: TaskPath, to_file: TaskPath, seed: int
    ) -> None:
        super().__init__(
            env,
            f"Incomplete {from_file:n} -> {to_file:n} (seed {seed:x})",
            from_file,
            to_file,
            seed,
        )

    def _run(self):
        with self._open_file(self.from_file) as f:
            lines = f.readlines()

        rand_gen = Random(self.seed)
        if lines:
            lines = lines[: rand_gen.randint(0, len(lines) - 1)]

        with self._open_file(self.to_file, "w") as f:
            f.write("".join(lines))


class BlankLine(Invalidate):
    """Makes a line in the output blank."""

    def __init__(
        self, env: Env, from_file: TaskPath, to_file: TaskPath, seed: int
    ) -> None:
        super().__init__(
            env,
            f"Blank line {from_file:n} -> {to_file:n} (seed {seed:x})",
            from_file,
            to_file,
            seed,
        )

    def _run(self):
        with self._open_file(self.from_file) as f:
            lines = f.readlines()

        rand_gen = Random(self.seed)
        if lines:
            lines[self._select_line_index(rand_gen, len(lines))] = "\n"

        with self._open_file(self.to_file, "w") as f:
            f.write("".join(lines))


class ChaosMonkey(Invalidate):
    """Tries to break judge by generating nasty output."""

    def __init__(self, env, from_file: TaskPath, to_file: TaskPath, seed: int) -> None:
        super().__init__(
            env,
            f"ChaosMonkey {from_file:n} -> {to_file:n} (seed {seed:x})",
            from_file,
            to_file,
            seed,
        )

    def _run(self):
        rand_gen = Random(self.seed)

        NUMBER_MODIFIERS = [
            lambda _: 0,
            lambda x: int(x) + 1,
            lambda x: int(x) - 1,
            lambda x: -int(x),
            lambda x: int(x) + rand_gen.randint(1, 9) / 10,
        ]
        CREATE_MODIFIERS = [
            lambda _: rand_gen.randint(0, int(1e5)),
            lambda _: rand_gen.randint(-int(1e5), -1),
            lambda _: rand_gen.randint(0, int(1e18)),
            lambda _: rand_gen.randint(-int(1e18), -1),
            lambda _: randword(rand_gen.randint(1, 10), rand_gen),
        ]
        CHANGE_MODIFIERS = [
            lambda x: f"{x} {x}",
            lambda _: "",
            lambda x: randword(len(x), rand_gen),
            lambda x: randword(len(x) + 1, rand_gen),
            lambda x: randword(len(x) - 1, rand_gen),
        ]

        lines = []
        with self._open_file(self.from_file) as f:
            for line in f.readlines():
                lines.append(line.rstrip("\n").split(" "))

        if len(lines) == 0:
            lines = [[str(rand_gen.choice(CREATE_MODIFIERS)(""))]]
        else:
            line = self._select_line_index(rand_gen, len(lines))
            token = rand_gen.randint(0, len(lines[line]) - 1)

            modifiers = CREATE_MODIFIERS + CHANGE_MODIFIERS
            try:
                int(lines[line][token])
                modifiers += NUMBER_MODIFIERS
            except ValueError:
                pass
            lines[line][token] = str(rand_gen.choice(modifiers)(lines[line][token]))

        with self._open_file(self.to_file, "w") as f:
            for line in lines:
                f.write(" ".join(line) + "\n")


class TrailingString(Invalidate):
    def __init__(
        self, env: Env, from_file: TaskPath, to_file: TaskPath, seed: int
    ) -> None:
        super().__init__(
            env,
            f"Trailing string {from_file:n} -> {to_file:n} (seed {seed:x})",
            from_file,
            to_file,
            seed,
        )

    def _run(self):
        with self._open_file(self.from_file) as f:
            lines = f.readlines()

        # TODO: Find some more permanent solution (#545)
        if lines and lines[-1].endswith("\n"):
            lines[-1] += "\n"

        rand_gen = Random(self.seed)
        lines.append(randword(60, rand_gen) + "\n")

        with self._open_file(self.to_file, "w") as f:
            f.write("".join(lines))
