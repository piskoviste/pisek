from abc import ABC, abstractmethod
from collections import deque
import sys

from pisek.env import Env
from pisek.jobs.jobs import State, PipelineItem, Job, JobManager
from pisek.jobs.status import StatusJobManager
from pisek.jobs.cache import Cache

CLCU = "\x1b[1A\x1b[2K"  # clear line cursor up

class JobPipeline(ABC):
    """Runs given Jobs and JobManagers according to their prerequisites."""
    @abstractmethod
    def __init__(self, env):
        env.reserve()
        self.failed = False
        self._tmp_lines = 0

    def run_jobs(self, cache: Cache, env: Env) -> bool:
        self.job_managers : deque[JobManager] = deque()
        self.pipeline : deque[PipelineItem] = deque(self.pipeline)
        while len(self.pipeline) or len(self.job_managers):
            p_item = self.pipeline.popleft()
            if isinstance(p_item, JobManager):
                self.job_managers.append(p_item)
                self.pipeline.extendleft(reversed(p_item.create_jobs(env.fork())))
            elif isinstance(p_item, Job):
                p_item.run_job(cache)
                p_item.finish()
            else:
                raise TypeError(f"Objects in {self.__class__.__name__} should be either Job or JobManager.")
            self.failed |= not self._status_update(env)  # we really need to call status_update to update messages
            if self.failed and not env.full:
                break

        cache.export()  # Remove duplicate cache entries
        return self.failed

    def _status_update(self, env: Env) -> bool:
        """Display current progress. Return true if there were no failures."""
        for _ in range(self._tmp_lines):
            print(CLCU, end="")
        self._tmp_lines = 0

        while len(self.job_managers):
            job_man = self.job_managers.popleft()
            ongoing_msg = job_man.update()  # We are updating job_man's state with this call!
            if not env.full and job_man.any_failed():
                print(ongoing_msg)
                print(job_man.failures(), end='', file=sys.stderr)
                return False
            if job_man.state == State.failed or job_man.ready():
                msg = job_man.finalize()
                if msg:
                    print(msg)
                if job_man.state == State.failed:
                    print(job_man.failures(), end='', file=sys.stderr)
                    return False
            elif job_man.state == State.canceled:
                print(ongoing_msg)
            else:
                self._print_tmp(ongoing_msg)
                self.job_managers.appendleft(job_man)
                break
        
        if len(self.pipeline):
            self._print_tmp(f"Active job: {self.pipeline[0].name}")
        return True

    def _print_tmp(self, msg, *args, **kwargs):
        """Prints a text to be rewriten latter."""
        self._tmp_lines += msg.count('\n') + 1
        print(str(msg), *args, **kwargs)
