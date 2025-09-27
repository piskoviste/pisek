# Usage

## Creating a task

First, you will need a task to test. You can create a task skeleton by running:

```bash
pisek init
```

You can also choose one of our [example tasks](https://github.com/piskoviste/pisek/tree/master/examples)
to try pisek on.

## What a task looks like

A task is a single directory containing programs, task data, and most importantly a `config` file
which holds all the metadata for the task (scoring, limits, how to run programs, etc.).

Programs have their roles (generator, solution, judge, …) specified in the `config`.
However, it is customary to also give them self-descriptive names such as `gen.py` or `solve_slow.cpp`.

Additionally, static inputs (`*.in`) and outputs (`*.out`) are contained in the top-level folder
or in `static_subdir`, as specified in the `config`.

## Testing tasks

The task is tested by running:
```bash
pisek test
```

For testing only some solutions, you can use:
```bash
pisek test solutions solution1 solution2 ...
```

Similarly, for testing just the generator:
```bash
pisek test generator
```

## Cleaning
During task testing, pisek generates binaries, testing data, caches, logs, etc.
You can remove all these files with:
```bash
pisek clean
```

## Visualization
Finally, you can visualize solution times and their closeness to the time limit:
```bash
pisek test --testing-log
pisek visualize
```
