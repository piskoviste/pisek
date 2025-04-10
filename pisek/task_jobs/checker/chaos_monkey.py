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

import random
import string

from pisek.env.env import Env
from pisek.utils.paths import TaskPath
from pisek.task_jobs.task_job import TaskJob


class Invalidate(TaskJob):
    """Abstract Job for invalidating an output."""

    def __init__(
        self, env: Env, name: str, from_file: TaskPath, to_file: TaskPath, seed: int
    ) -> None:
        super().__init__(env, name)
        self.seed = seed
        self.from_file = from_file
        self.to_file = to_file


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

        rand_gen = random.Random(self.seed)
        if len(lines):
            lines = lines[: rand_gen.randint(0, len(lines) - 1)]

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
        rand_gen = random.Random(self.seed)

        def randword(length: int):
            letters = string.ascii_lowercase
            return "".join(rand_gen.choice(letters) for _ in range(length))

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
            lambda _: randword(rand_gen.randint(1, 10)),
        ]
        CHANGE_MODIFIERS = [
            lambda x: f"{x} {x}",
            lambda _: "",
            lambda x: randword(len(x)),
            lambda x: randword(len(x) + 1),
            lambda x: randword(len(x) - 1),
        ]

        lines = []
        with self._open_file(self.from_file) as f:
            for line in f.readlines():
                lines.append(line.rstrip("\n").split(" "))

        if len(lines) == 0:
            lines = [[str(rand_gen.choice(CREATE_MODIFIERS)(""))]]
        else:
            if len(lines) <= 2 or rand_gen.randint(1, 10) == 1:
                line = random.randint(0, len(lines) - 1)
            else:
                line = random.randint(2, len(lines) - 1)
            token = random.randint(0, len(lines[line]) - 1)

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
