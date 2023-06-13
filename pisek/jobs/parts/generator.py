import random
import os
from typing import List

import pisek.util as util
from pisek.env import Env
from pisek.jobs.jobs import State, Job
from pisek.jobs.parts.task_job import TaskJob, TaskJobManager
from pisek.jobs.parts.program import RunResultKind, ProgramJob, Compile

from pisek.generator import OnlineGenerator

class OnlineGeneratorManager(TaskJobManager):
    def __init__(self):
        super().__init__("Generator Manager")

    def _get_jobs(self) -> List[Job]:
        generator = self._resolve_path(self._env.config.generator)

        jobs = [compile := Compile(generator, self._env.fork())]

        random.seed(4)  # Reproducibility!
        seeds = random.sample(range(0, 16**4), self._env.get_without_log('inputs'))
        for subtask in self._env.config.subtasks:
            if subtask == 0:
                continue  # skip samples
            last_gen = None
            for i, seed in enumerate(seeds):
                data_dir = self._env.config.get_data_dir()
                input_name = util.get_input_name(seed, subtask)

                jobs.append(gen := OnlineGeneratorGenerate(generator, input_name, subtask, seed, self._env.fork()))
                gen.add_prerequisite(compile)
                if i == 0:
                    jobs.append(det := OnlineGeneratorDeterministic(generator, input_name, subtask, seed, self._env.fork()))
                    det.add_prerequisite(gen)
                elif i == 1:
                    jobs.append(rs := OnlineGeneratorRespectsSeed(subtask, last_gen.seed, gen.seed,
                                                                  last_gen.input_file, gen.input_file, self._env.fork()))
                    rs.add_prerequisite(last_gen)
                    rs.add_prerequisite(gen)
                last_gen = gen

        return jobs


class OnlineGeneratorJob(ProgramJob):
    def __init__(self, name: str, generator : str, input_file: str, subtask: int, seed: int, env: Env) -> None:
        self.subtask = subtask
        self.seed = seed
        super().__init__(name, generator, env)
        self.input_name = input_file
        self.input_file = self._data(input_file)

    def _gen(self, input_file: str, seed: int, subtask: int) -> None:
        if not self._load_compiled():
            return None
        if seed < 0:
            return self.fail(f"Seed {seed} is negative.")

        input_dir = os.path.dirname(input_file)
        os.makedirs(input_dir, exist_ok=True)

        difficulty = str(subtask)
        hexa_seed = f"{seed:x}"

        result = self._run_program(
            [difficulty, hexa_seed],
            stdout=input_file,
        )
        if result is None:
            return
        if result.kind != RunResultKind.OK:
            return self.fail(
                f"{self.program} failed on subtask {subtask}, seed {seed:x}:\n" +
                result.msg
            )
        
        return result


class OnlineGeneratorGenerate(OnlineGeneratorJob):
    def __init__(self, generator: OnlineGenerator, input_file: str, subtask: int, seed: int, env: Env) -> None:
        super().__init__(f"Generate {input_file}", generator, input_file, subtask, seed, env)

    def _run(self):
        self._gen(self.input_file, self.seed, self.subtask)
        

class OnlineGeneratorDeterministic(OnlineGeneratorJob):
    def __init__(self, generator: OnlineGenerator, input_file: str, subtask: int, seed: int, env: Env) -> None:
        super().__init__(
            f"Generator is deterministic (subtask {subtask}, seed {seed:x})",
            generator, input_file, subtask, seed, env
        )

    def _run(self):
        copy_file = self.input_file.replace(".in", ".copy")
        if not self._gen(copy_file, self.seed, self.subtask):
            return
        if not self._files_equal(self.input_file, copy_file):
            return self.fail(
                f"Generator is not deterministic. Files {self.input_name} and {os.path.basename(copy_file)} differ "
                f"(subtask {self.subtask}, seed {self.seed})",
            )

class OnlineGeneratorRespectsSeed(TaskJob):
    def __init__(self, subtask: int, seed1: int, seed2: int, file1: str, file2: str, env: Env) -> None:
        self.file1, self.file2 = file1, file2
        self.file1_name, self.file2_name = map(os.path.basename, (file1, file2))
        self.subtask = subtask
        self.seed1, self.seed2 = seed1, seed2
        super().__init__(f"Generator respects seeds ({self.file1_name} and {self.file2_name} are different)", env)

    def _run(self):
        if self._files_equal(self.file1, self.file2):
            return self.fail(
                f"Generator doesn't respect seed."
                f"Files {self.file1_name} (seed {self.seed1:x}) and {self.file2_name} (seed {self.seed2:x}) are same."
            )
