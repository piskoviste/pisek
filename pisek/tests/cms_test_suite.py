import glob
import unittest
import os
from typing import Optional, List
import shutil

from . import test_case
from ..task_config import TaskConfig
from .. import util
from ..generator import OfflineGenerator
from ..judge import make_judge, Judge
from ..program import RunResult


def inputs_for_subtask(subtask: int, config: TaskConfig):
    data_dir = config.get_data_dir()
    globs = config.subtasks[subtask].in_globs

    res: List[str] = []
    for g in globs:
        res += [os.path.basename(f) for f in glob.glob(os.path.join(data_dir, g))]

    return sorted(res)


class GeneratorWorks(test_case.GeneratorTestCase):
    def __init__(self, task_config, generator: OfflineGenerator):
        super().__init__(task_config, generator)

    def runTest(self):
        data_dir = self.task_config.get_data_dir()
        result = self.generator.generate(test_dir=data_dir)

        generator_output = util.quote_process_output(result)
        self.assertTrue(
            result.returncode == 0,
            f"Chyba při generování vstupu.\n{generator_output}",
        )

        test_files = glob.glob(os.path.join(data_dir, "*.in"))
        self.assertTrue(
            test_files,
            f"Generátor nevygeneroval žádné vstupní soubory\n{generator_output}",
        )

        for subtask in self.task_config.subtasks:
            self.assertTrue(
                inputs_for_subtask(subtask, self.task_config),
                f"Chybí vstupní soubory pro subtask {subtask}.\n{generator_output}",
            )

    def __str__(self):
        return f"Generátor {self.generator.name} funguje"


class SolutionWorks(test_case.SolutionTestCase):
    def __init__(self, task_config, solution_name, timeout, in_self_test=False):
        super().__init__(task_config, solution_name)
        self.run_config = {"timeout": timeout}
        self.judge: Judge = make_judge(self.task_config)
        self.in_self_test = in_self_test

    def test_passes_samples(self):
        samples_dir = self.task_config.get_samples_dir()
        data_dir = self.task_config.get_data_dir()

        for sample_in, sample_out in util.get_samples(samples_dir):
            data_sample_in = os.path.join(data_dir, os.path.basename(sample_in))
            data_sample_out = os.path.join(data_dir, os.path.basename(sample_out))
            # Copy the samples into the data (tests) directory for consistency
            # with the other tests
            shutil.copy(sample_in, data_sample_in)
            shutil.copy(sample_out, data_sample_out)

            pts, verdict = self.judge.evaluate(
                self.solution, data_sample_in, data_sample_out, self.run_config
            )
            self.assertEqual(
                verdict.result,
                RunResult.OK,
                f"Chyba při spouštění {self.solution.name} na {sample_in}: {verdict}",
            )
            self.assertEqual(
                pts,
                1.0,
                f"Špatná odpověď řešení {self.solution.name} na {sample_in}: {verdict}",
            )

    def get_subtask_score(self, subtask):
        data_dir = self.task_config.get_data_dir()
        inputs = inputs_for_subtask(subtask, self.task_config)
        model_solution_name = self.task_config.solutions[0]

        # TODO: possible optimization for the model solution?
        judge_score = 1.0
        for input_file in inputs:
            model_output_filename = util.get_output_name(
                input_file,
                solution_name=model_solution_name,
            )

            pts, verdict = self.judge.evaluate(
                self.solution,
                input_file=os.path.join(data_dir, input_file),
                correct_output=os.path.join(data_dir, model_output_filename),
                run_config=self.run_config,
            )

            result_chars = {
                RunResult.TIMEOUT: "T",
                RunResult.NONZERO_EXIT_CODE: "!",
            }
            if verdict.result == RunResult.OK:
                c = "·" if pts == 1 else "W" if pts == 0 else "P"
            else:
                c = result_chars[verdict.result]

            self.log(c, end="")

            judge_score = min(judge_score, pts)

            if judge_score == 0:
                break

        return judge_score

    def runTest(self):
        expected_score = util.get_expected_score(self.solution.name, self.task_config)
        max_score = self.task_config.get_maximum_score()

        if expected_score == max_score:
            # Solutions which don't pass one of the subtasks might not even pass
            # the samples. For example, the sample might contain tests which would
            # not appear in the easy version
            self.test_passes_samples()

        score = 0
        for i, subtask in enumerate(self.task_config.subtasks):
            self.log("|", end="")
            max_subtask_score = self.task_config.subtasks[subtask].score
            judge_score = self.get_subtask_score(subtask)
            score += judge_score * max_subtask_score
        self.log("| ", end="")

        # TODO: document this somewhere
        score = round(score)

        # TODO: add diffs
        self.assertEqual(
            score,
            expected_score,
            f"Řešení {self.solution.name} mělo získat {expected_score}b,"
            f" ale získalo {score}b",
        )

    def __str__(self):
        return "Řešení {} získá {}b".format(
            self.solution.name,
            util.get_expected_score(self.solution.name, self.task_config),
        )

    def log(self, msg, *args, **kwargs):
        if not self.in_self_test:
            super().log(msg, *args, **kwargs)


def cms_test_suite(
    task_dir: str,
    solutions: Optional[List[str]] = None,
    timeout=None,
    in_self_test=False,
    **_ignored,  # Some arguments are relevant in kasiopea_test_suite but not here
):
    """
    Tests a task. Generates test cases using the generator, then runs each solution
    in `solutions` (or all of them if `solutions == None`) and verifies
    that they get the expected number of points.
    """

    config = TaskConfig(task_dir)
    util.clean_data_dir(task_dir)

    if timeout is None:
        timeout = config.timeout_other_solutions or util.DEFAULT_TIMEOUT

    timeout_model_solution = config.timeout_model_solution or timeout

    suite = unittest.TestSuite()

    if solutions:
        # No need to check for samples when only testing generator
        suite.addTest(test_case.SampleExists(config.get_samples_dir()))

    generator = OfflineGenerator(task_dir, config.generator)
    suite.addTest(GeneratorWorks(config, generator))

    if solutions is None:
        solutions = config.solutions

    if not solutions:
        # This might be desirable if we only want to test the generator
        return suite

    if solutions[0] != config.solutions[0]:
        # Make sure that the model solution comes first even if we are not testing
        # all of the solutions
        solutions = [config.solutions[0]] + solutions

    for i, solution_name in enumerate(solutions):
        cur_timeout = timeout_model_solution if i == 0 else timeout
        suite.addTest(
            SolutionWorks(
                config, solution_name, timeout=cur_timeout, in_self_test=in_self_test
            )
        )

    return suite
