import random
import os
from typing import List

import pisek.util as util
from pisek.env import Env
from pisek.tests.jobs import State, Job, JobManager
from pisek.tests.parts.task_job import TaskJob
from pisek.tests.parts.general import Compile

from pisek.generator import OnlineGenerator

class OnlineGeneratorManager(JobManager):
    def __init__(self):
        super().__init__("Generator Manager")

    def _get_jobs(self, env: Env) -> List[Job]:
        generator = OnlineGenerator(env)
        
        jobs = [compile := Compile(generator, env)]

        random.seed(4)  # Reproducibility!
        seeds = random.sample(range(0, 16**4), env.inputs)
        for subtask in env.config.subtasks:
            last_gen = None
            for i, seed in enumerate(seeds):
                data_dir = env.config.get_data_dir()
                input_name = os.path.join(data_dir, util.get_input_name(seed, subtask))

                jobs.append(gen := OnlineGeneratorGenerate(generator, input_name, subtask, seed, env))
                gen.add_prerequisite(compile)
                if i == 0:
                    jobs.append(det := OnlineGeneratorDeterministic(generator, input_name, subtask, seed, env))
                    det.add_prerequisite(gen)
                elif i == 1:
                    jobs.append(rs := OnlineGeneratorRespectsSeed(subtask, last_gen.seed, gen.seed,
                                                                  last_gen.input_file, gen.input_file, env))
                    rs.add_prerequisite(last_gen)
                    rs.add_prerequisite(gen)
                last_gen = gen

        return jobs

    def _get_status(self) -> str:
        return ""

class GeneratorJob(TaskJob):
    def __init__(self, name: str, generator : OnlineGenerator, input_file: str, subtask: int, seed: int, env: Env) -> None:
        self.generator = generator
        self.subtask = subtask
        self.seed = seed
        self.input_file = input_file
        super().__init__(name, env)

    def _gen(self, input_file: str, seed: int, subtask: int) -> None:
        if not self.generator.generate(input_file, seed, subtask):
            return self.fail(
                f"Error when generating input {input_file} of subtask {self.subtask}"
                f" with seed {self.seed}"
            )

class OnlineGeneratorGenerate(GeneratorJob):
    def __init__(self, generator: OnlineGenerator, input_file: str, subtask: int, seed: int, env: Env) -> None:
        super().__init__(f"Generate {input_file}", generator, input_file, subtask, seed, env)

    def _run(self):
        self._gen(self.input_file, self.seed, self.subtask)


class OnlineGeneratorDeterministic(GeneratorJob):
    def __init__(self, generator: OnlineGenerator, input_file: str, subtask: int, seed: int, env: Env) -> None:
        super().__init__(
            f"Generator is deterministic (subtask {subtask}, seed {seed})",
            generator, input_file, subtask, seed, env
        )

    def _run(self):
        copy_file = os.path.join(self._env.config.get_data_dir(), util.get_output_name(self.input_file, "copy"))
        self._gen(copy_file, self.seed, self.subtask)
        if not self._files_equal(self.input_file, copy_file):
            return self.fail(
                f"Generator is not deterministic. Files {self.input_file} and {copy_file} differ "
                f"(subtask {self.subtask}, seed {self.seed})",
            )

class OnlineGeneratorRespectsSeed(TaskJob):
    def __init__(self, subtask: int, seed1: int, seed2: int, file1: str, file2: str, env: Env) -> None:
        self.file1, self.file2 = file1, file2
        self.subtask = subtask
        self.seed1, self.seed2 = seed1, seed2
        super().__init__(f"Generator respects seeds ({file1} and {file2} are different)", env)

    def _run(self):
        if self._files_equal(self.file1, self.file2):
            return self.fail(
                f"Generator doesn't respect seed."
                f"Files {self.file1} (seed {self.seed1}) and {self.file2} (seed {self.seed2}) are same."
            )
