import os
import subprocess

from . import util
from . import compile


def run(executable: str, input_file: str, output_file: str, timeout: int = 100) -> bool:
    # TODO: Adapt the code from https://gist.github.com/s3rvac/f97d6cbdfdb15c0a32e7e941f7f4a3fa
    #       to limit the memory of the subprocess
    with open(input_file, "r") as inp:
        with open(output_file, "w") as outp:
            result = subprocess.run(
                executable,
                stdin=inp,
                stdout=outp,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )

            return result.returncode == 0


def run_direct(executable: str):
    """ like run(), but with no redirections or timeout """
    result = subprocess.run(executable, stderr=subprocess.PIPE)

    return result.returncode == 0


class Program:
    def __init__(self, task_dir, name):
        self.task_dir = task_dir
        self.name = name
        self.executable = None

    def compile(self):
        filename = util.resolve_extension(self.task_dir, self.name)
        if filename is None:
            raise RuntimeError(
                f"Řešení {self.name} ve složce {self.task_dir} neexistuje"
            )
        self.executable = compile.compile(os.path.join(self.task_dir, filename))
        if self.executable is None:
            raise RuntimeError(f"Řešení {self.name} se nepodařilo zkompilovat")

    def compile_if_needed(self):
        # TODO: we could avoid recompiling if the binary exists and is fresh
        if not self.executable:
            self.compile()

    def run(self):
        self.compile_if_needed()
        return run.run_direct(self.executable)
