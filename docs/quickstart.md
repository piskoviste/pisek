# Usage

## Creating a task

First, you will need a task to test:

```bash
pisek init
```

You can either create a task skeleton or choose one of our example task to try out pisek on.

## What task looks like

Task is a single directory containing programs, task data and most importantly a `config` file.
It holds all the metadata for this task (how to run programs, scoring, limits, etc.).

Programs have their roles (generator, solution, judge,...) specified in `config`.
However, it is customary to give them self-descriptive names like `gen.py` or `solve_slow.cpp`.

Additionally static inputs (`*.in`) and outputs (`*.in`) are contained in top-level
or in `static_subdir` as specified in `config`. 

## Testing tasks

Tasks are tested by running:
```bash
pisek test
```

For testing only some solutions, you can use:
```bash
pisek test solutions solution1 solution2 ...
```

Similarly for only testing the generator:
```bash
pisek test generator
```

## Cleaning
During task testing, pisek generates binaries, testing data, caches, logs, etc.
You can remove all of them with:
```bash
pisek clean
```

## Visualization
Finally, you can visualize solution times and their closeness to the time limit:
```bash
pisek test --testing-log
pisek visualize
```
