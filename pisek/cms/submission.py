# pisek cms - Tool for importing tasks from Pisek into CMS.
#
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import Optional
from cms.db.contest import Contest
from cms.db.task import Task
from cms.db.user import Participation, User
from cms.db.submission import Submission, File
from cms.db.filecacher import FileCacher
from cms.grading.language import Language
from cms.grading.languagemanager import get_language
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import Session
from os import path
from datetime import datetime, timezone

from pisek.env.env import Env
from pisek.config.task_config import SolutionSection
from pisek.utils.colors import ColorSettings
from pisek.utils.paths import TaskPath
from pisek.utils.text import eprint


def get_participation(session: Session, task: Task, username: str) -> Participation:
    if task.contest_id is None:
        raise RuntimeError("The task is not part of any contest")

    try:
        return (
            session.query(Participation)
            .join(User)
            .filter(Participation.contest_id == task.contest_id)
            .filter(User.username == username)
            .one()
        )
    except NoResultFound as e:
        raise RuntimeError(
            f'There is no user named "{username}" in the given contest'
        ) from e


def submit_all(
    session: Session, env: Env, task: Task, participation: Participation
) -> list[tuple[str, Submission]]:
    config = env.config

    files = FileCacher()
    submissions = []

    for name, solution in config.solutions.items():
        submission = submit(session, files, env, solution, task, participation)
        if submission is not None:
            submissions.append((name, submission))

    return submissions


def submit(
    session: Session,
    files: FileCacher,
    env: Env,
    solution: SolutionSection,
    task: Task,
    participation: Participation,
) -> Submission:
    resolved = resolve_solution(task.contest, env, solution)
    if resolved is None:
        return None
    file_path, language = resolved

    if len(task.submission_format) != 1:
        raise RuntimeError(
            "Cannot submit solutions to tasks that require multiple files"
        )

    digest = files.put_file_from_path(file_path.path, f"Solution to task {task.id}")
    submission = get_submission_of_digest(session, digest, language, task)

    if submission is not None:
        return submission

    submission = Submission(
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        language=language.name,
        participation=participation,
        task=task,
        comment=solution.name,
    )
    session.add(submission)

    filename = task.submission_format[0]
    session.add(File(filename=filename, digest=digest, submission=submission))

    return submission


def get_submission(
    session: Session,
    files: FileCacher,
    env: Env,
    solution: SolutionSection,
    task: Task,
) -> Optional[Submission]:
    if task.contest is None:
        raise RuntimeError("The task is not part of any contest")

    resolved = resolve_solution(task.contest, env, solution)
    if resolved is None:
        return None
    file_path, language = resolved

    digest = files.put_file_from_path(file_path.path, f"Solution to task {task.name}")

    return get_submission_of_digest(session, digest, language, task)


def get_submission_of_digest(
    session: Session,
    digest: str,
    language: Language,
    task: Task,
) -> Optional[Submission]:
    return (
        session.query(Submission)
        .join(File)
        .filter(Submission.task == task)
        .filter(Submission.language == language.name)
        .filter(File.digest == digest)
        .order_by(Submission.timestamp.desc())
        .first()
    )


def resolve_solution(
    contest: Contest, env: Env, solution: SolutionSection
) -> Optional[tuple[TaskPath, Language]]:
    sources = solution.run.build.sources
    if len(sources) != 1:
        eprint(
            ColorSettings.colored(
                "For CMS import there must be exactly one source:\n  "
                + " ".join(map(lambda p: p.col(env), sources)),
                "yellow",
            )
        )
        return None

    source: TaskPath = sources[0]

    for language_name in contest.languages:
        language: Language = get_language(language_name)

        for ext in language.source_extensions:
            if source.name.endswith(ext):
                return source, language

            file_path = source.replace_suffix(ext)

            if path.isfile(file_path.path):
                return file_path, language

    eprint(
        ColorSettings.colored(
            f"Skipping {source}, as it isn't available in any enabled language",
            "yellow",
        )
    )
    return None
