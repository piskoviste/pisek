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

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future, wait

from pisek.env.env import Env
from pisek.jobs.jobs import State, Job, JobManager
from pisek.jobs.cache import Cache
from pisek.jobs.reporting import Reporter, CommandLineReporter


class JobPipeline(ABC):
    """Runs given Jobs and JobManagers according to their prerequisites."""

    @abstractmethod
    def __init__(self) -> None:
        self.job_managers: list[JobManager] = []
        self._tmp_lines: int = 0
        self.all_accessed_files: set[str] = set()

    def run_jobs(self, cache: Cache | None, env: Env) -> bool:
        self._reporter: Reporter = CommandLineReporter(env, self.job_managers)

        self._futures: dict[Future, Job] = {}
        self._queue: list[Job] = []
        self._envs: list[Env] = [env.model_copy(deep=True) for _ in range(env.jobs)]

        for job_man in self.job_managers:
            job_man.set_env(env)

        with ThreadPoolExecutor(max_workers=env.jobs) as self._thread_pool:
            self._update(cache, env)
            while not all(man.state.finished() for man in self.job_managers):
                done, _ = wait(
                    self._futures, timeout=0.1, return_when="FIRST_COMPLETED"
                )

                for future in done:
                    exception = future.exception()
                    if exception is not None:
                        raise exception

                    job = self._futures[future]
                    del self._futures[future]
                    self._envs.append(job._env)
                    self._finalize_job(job, cache)

                if not self._update(cache, env):
                    break

                self._reporter.update(list(self._futures.values()))

            for job in self._futures.values():
                if job.state == State.succeeded:
                    self._finalize_job(job, cache)
                else:
                    job.cancel()
            self._reporter.update([])

        if cache is not None:
            cache.export()  # Save last version of cache

        return any(man.state == State.failed for man in self.job_managers)

    def _update(self, cache: Cache | None, env: Env) -> bool:
        """Updates currently running JobManagers and Jobs, runs new ones
        and returns if we should continue in testing."""

        # Start new managers
        for manager in self.job_managers:
            if manager.state == State.in_queue and manager.prerequisites == 0:
                self._queue.extend(manager.create_jobs())
                if manager.any_failed():
                    manager.finalize()
                    self._reporter.report_manager(manager)
                    if not env.full:
                        return False
                break  # We don't want to start many managers at once because that can lead to UI freeze

        # Process new jobs
        new_queue: list[Job] = []
        to_run: list[tuple[Job, Env]] = []
        for job in self._queue:
            if len(self._envs) > 0 and job.prerequisites == 0:
                job.prepare(cache)
                if job.state.finished():
                    self._finalize_job(job, cache)
                elif job.state:
                    to_run.append((job, self._envs.pop()))
            else:
                new_queue.append(job)

        self._queue = new_queue

        # Update managers
        for manager in self.job_managers:
            if manager.state == State.running:
                manager.update()
                if manager.ready() or manager.any_failed():
                    manager.finalize()
                    self._reporter.report_manager(manager)
                if manager.any_failed() and not env.full:
                    return False

        # Start new jobs
        for job, env in to_run:
            if job.state == State.in_queue:
                self._futures[self._thread_pool.submit(job.run, env)] = job
            else:
                self._envs.append(env)

        return True

    def _finalize_job(self, job: Job, cache: Cache | None) -> None:
        job.finalize(cache)
        self.all_accessed_files |= job.accessed_files
        self._reporter.report_job(job)
