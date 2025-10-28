# Batch checker

The batch checker gets the contestant's output, the input, and the correct output.
It should determine whether the contestant's output is correct.

There are various types of checkers you can use:

- [tokens](#tokens-checker) – fast, versatile file equality checker
- [shuffle](#shuffle-checker) – similar to tokens, but allows permutations of tokens
- [diff](#diff-checker) – file equality checker based on the `diff` command line tool (avoid this option, as it has quadratic time complexity)
- [judge](#custom-judge) – custom checker

If there is only a single correct output (e.g. the minimum of an array), `tokens` is strongly recommended.
Otherwise, when there are multiple correct outputs (e.g. the shortest path in a graph),
writing a judge is necessary. Set `out_check` in the config accordingly.

## Tokens checker

A fast and versatile equality checker. Ignores whitespace, but not newlines.
(Ignores newlines only at the end of a file.)

Tokens are separated by (possibly multiple) whitespace characters.
For the output to be correct, the tokens need to be same as in the correct output file.

You can customize the tokens checker with `tokens_ignore_newlines` or `tokens_ignore_case`.
For comparing floats, set `tokens_float_rel_error` and `tokens_float_abs_error`.
Details can be found in [config-documentation](../config-docs.md).

## Shuffle checker

Similarly to the tokens checker, the shuffle checker compares the output with the correct output token-by-token.
Allows permutations of tokens (permutations can be configured with `shuffle_mode`).
Use `shuffle_ignore_case` for case insensitivity.

## Diff checker

An equality checker based on the `diff` tool. Runs `diff -Bbq` under the hood.
Ignores whitespace and empty lines.

??? danger "This `out_check` is not recommended"

    In some cases, `diff` has quadratic time complexity, leading to unexpectedly slow checking of outputs.

## Custom judge

If there can be multiple correct solutions, it is necessary to write a custom judge.
Set `out_judge` to the path to the source code of your judge, `judge_type` to the judge type (see below),
and `judge_needs_in`, `judge_needs_out` to `0`/`1`, depending on whether the judge needs the input and the correct output.

When writing a custom judge, you can choose from multiple judge types:

1. [cms-batch judge](#cms-batch-judge)
2. [opendata-v2](#opendata-v2-judge)
3. [opendata-v1](#opendata-v1-judge)

### CMS-batch judge

The CMS batch judge format as described in the [CMS documentation](https://cms.readthedocs.io/en/v1.4/Task%20types.html?highlight=Manager#checker).

It is run as follows (having filenames given as arguments):
```
./judge <input> <correct output> <contestant output>
```

The judge should print a relative number of points (a float between 0.0 and 1.0) to its stdout as a single line.
To its stderr it should write a single-line message to the contestant.
**Unlike what the CMS documentation specifies, the files should be single-line only.**
There will be a warning otherwise.

??? example "Example `cms-batch` judge"

	For a [task](https://github.com/piskoviste/pisek/blob/master/examples/cms-batch) of printing *N* positive integers that sum up to *K*,
	the judge may look like this:
    ```py
    --8<-- "examples/cms-batch/judge.py"
    ```

### Opendata-v2 judge

The opendata-v2 judge is run in this way:
```
./judge <test> <seed> < contestant-output
```
Where `test` is the testcase's test number and `seed` the testcase's generating seed.
(The arguments are the same as those given to the `opendata-v1` generator
this input has (probably) been generated with.)
If the input was not generated with a seed (static or unseeded), `seed` will be `-`.

If `judge_needs_in` is set, the judge will get the input filename in the `TEST_INPUT`
environment variable. Similarly, if `judge_needs_out` is set, the correct output
filename will be in the `TEST_OUTPUT` environment variable.

If the output is correct, the judge should exit with return code 42.
Otherwise, the judge should exit return code 43.

Optionally, the judge can write a one-line message for the contestant
to stderr (at most 255 bytes), followed by a sequence of lines with `KEY=value` pairs.
The following keys are allowed:

- `POINTS` – Number of points awarded for this test case (used only if the exit code says "OK").
- `LOG` – A message that should be logged.
- `NOTE` – An internal note recorded in the database, but not visible to contestants.

Values are again limited to 255 bytes.

### Opendata-v1 judge

The opendata-v1 judge is the same as opendata-v2, with the exception of using different
return codes, return code 0 for a correct output and return code 1 for a wrong output.

??? danger "This `judge_type` is not recommended"

    Return with exit code 1 is very common and is for example trigger by any exception in Python.
    This can lead to internal judge bugs disguising themselves as wrong answers.
