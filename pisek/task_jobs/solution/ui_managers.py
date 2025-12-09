from pisek.jobs.jobs import Job
from pisek.task_jobs.task_manager import TaskJobManager
from pisek.task_jobs.data.data_manager import TEST_SEED


class EmptyLineManager(TaskJobManager):
    def __init__(self) -> None:
        super().__init__("Empty line")

    def _get_jobs(self) -> list[Job]:
        return []

    def get_status(self):
        return ""


class TestsHeaderManager(TaskJobManager):
    def __init__(self) -> None:
        super().__init__("Tests headers")

    def _get_jobs(self) -> list[Job]:
        return []

    def get_status(self):
        test_header = " " * len(self._solution_header_verbosity0("", 0, 0))
        for num, test in self._env.config.test_sections.items():
            length = sum(
                ti.repeat
                for ti in self._test_testcases(test)
                if test.new_in_test(ti.input_path(TEST_SEED).name)
            )
            if test.direct_predecessors:
                length += 3

            name = test.name
            if len(name) > length:
                name = str(num)
            if len(name) > length:
                name = ""

            test_header += "[" + name.center(length) + "]"
        return test_header
