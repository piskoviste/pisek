from dataclasses import dataclass
from decimal import Decimal

from pisek.task_jobs.data.testcase_info import TestcaseGenerationMode, TestcaseInfo
from pisek.task_jobs.solution.solution_result import Verdict


@dataclass
class OpendataTestcaseInfo:
    mode: TestcaseGenerationMode
    name: str
    repeat: int
    seeded: bool

    @staticmethod
    def from_testcase_info(testcase_info: TestcaseInfo) -> "OpendataTestcaseInfo":
        return OpendataTestcaseInfo(
            testcase_info.generation_mode,
            testcase_info.name,
            testcase_info.repeat,
            testcase_info.seeded,
        )


@dataclass
class OpendataVerdict:
    verdict: Verdict
    message: str | None
    points: Decimal
    log: str | None
    note: str | None
