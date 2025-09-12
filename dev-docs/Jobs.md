# Jobs
When testing a task all actions are run inside a pipeline - `JobPipeline`.
`JobPipeline` contains two types of `PipelineItem`s:
 - `Job`s - Actions to be done
 - `JobManger`s - Create `Job`s and look after them.

## PipelineItem
Both `Job` and `JobManager` share a few common traits.

### Name
Each `PipelineItem` has a name that's displayed to the user.

### State
Each item has a state that represent their progress:
 - `in_queue` - The item is waiting for previous items.
 - `running` - The item is running.
 - `succeeded` - The item has successfully ended.
 - `failed` - The task doesn't pass the checks this job tests.
 - `cancelled` - A prerequisite (see below) of this item has failed, therefore this item cannot be run.

### Failing
`PipelineItem`s can fail by raising `PipelineItemFailure`. Note that this is allowed
only in `Job._run`, `JobManager._get_jobs` and `JobManager._evaluate`.

### Prerequisites
Each item can have items that must be run before it. (E.g. Execution after compilation.) 
Prerequisites must be specified:
 - When creating `Job`s in `JobManager`
 - When creating `JobManager`s in `JobPipeline`'s init.

Additionally each prerequisite must be inserted into the pipeline before the given item.

## Jobs
`Job`s represent a single simple task.

To decrease run time `Job`'s inputs are monitored, and after `Job` has successfully finished,
it's result is cached. These are all inputs that `Job` can access:
 - `Job.__init__` parameters
 - `Job._env` variables
 - accessed files - **These are not logged automatically. Every file must passed to `Job._access_file` or accessed by pre-made functions!** Even files we write to must be logged as we need to run the job again if they are deleted.
 - other job's results - Must be added as named prerequisites. 

Next time if `Job` should be run with same inputs, the cached result is used instead.

(Job results are saved in `.pisek/cache` file.)

### Writing Jobs
A job can look like this (notice things in comments):
```py
class CopyFile(TaskJob): # We inherit from TaskJob, because it provides useful methods
    """Copies a file."""
    def __init__(self, env: Env, source: str, dest: str) -> None:
        # Note that second parameter of __init__ must be env, and all subsequent are cached
        self.source = source
        self.dest = dest
        super().__init__(env, f"Copy {source} to {dest}") # Here we give name of the job

    def _run(self):
        if self._env.verbose:  # Accessing a global variable
            self._print(f"Coping {self.source} to {self.dest}")  # For printing to terminal use Job._print
        
        if os.path.exists(self.dest):
            # Raise Failure if Job cannot be completed 
            raise PipelineItemFailure("Destination file already exists.")

        shutil.copy(self.source, self.dest)
        self._access_file(self.source)  # Access the source as the result depends on it
        self._access_file(self.dest)  # Also access destination as we need to run the job again if it has changed
        
        # Alternatively we can use `self._copy_file(self.source, self.dest)` with automatic logging
```

Jobs are created this way:
```py
Job(Env, *args, **kwargs)
```
Env must be second argument of every `__init__` (after `self`).
`*args` and `**kwargs` are cached.

## JobManager
Jobs are managed by a `JobManager` via the following interface:

1. `JobManager._get_jobs` creates a list of all jobs.
2. After a batch of `Job`s is finished / loaded from cache, `JobManager._update` is called. 
3. `JobManager.get_status` reports the state of the manager for printing to the console.
4. After all jobs have finished, `JobManager` can check for cross-job failures in `JobManager._evaluate`.
5. Finally, `JobManager._compute_result` is called and its result can be used by other `JobManager`s. 

Only `_get_jobs` and `_evaluate` can raise `PipelineItemFailure`.

### Writing JobManagers
```py
class ExampleManager(TaskJobManager):  # We inherit from TaskJobManager again for more methods
    def __init__(self):
        super().__init__("Doing something")

    def _get_jobs(self) -> list[Job]:
        # Create list of jobs to run
        jobs : list[Job] = [
            job1 := ExampleJob(self._env, "1"),
            job2 := ExampleJob(self._env, "2"),
        ]
        # Add prerequisites accordingly 
        job2.add_prerequisite(job1)

        return jobs
    
    # We don't need to override _get_status as we have a better one already
    # but as an example:
    def get_status(self) -> str:
        return f"{self.name} {len(self._jobs_with_state(State.succeeded))}/{len(self.jobs)}"

    # Finally we check for cross-job failures
    def _evaluate(self) -> Any:
        if self.jobs[0].result != self.jobs[1].result:
            raise PipelineItemFailure("Both jobs have to have the same result.")
```
