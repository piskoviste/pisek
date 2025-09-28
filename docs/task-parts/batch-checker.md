# Batch checker

The batch checker gets the contestants output, the input and the correct output.
It should say whether the contestant output is correct.

There are various types of checkers you can use:

- `tokens` - fast, versatile file equality checker
- `diff` - file equality checker based on the `diff` command line tool (don't use, as it has a quadratic time complexity)
- `judge` - custom checker

If there is only a single correct output (eg. the minimum of an array), `tokens` is strongly recommended.
Otherwise, when there are multiple correct outputs (eg. the shortest path in a graph),
writing a judge is necessary. Set `out_check` in the config accordingly.

## Tokens judge

A fast and versatile equality checker. Ignores whitespace, but not newlines.
(Ignores newlines only at the end of file.)

Tokens are separated by (possibly multiple) whitespace characters.
For the output to be correct, the tokens need to be same as in the correct output file.

You can customize the tokens judge with `tokens_ignore_newlines` or `tokens_ignore_case`.
For comparing floats, set `tokens_float_rel_error` and `tokens_float_abs_error`.
Details can be found in [config-documentation](./config-docs).

## Shuffle judge

Similarly to the tokens judge, the shuffle judge compares the output with the correct output token-by-token.
Allows permutations of tokens (permutations can be configured with `shuffle_mode`).
Use `shuffle_ignore_case` for case insensitivity.

## Diff checker

An equality checker based on the `diff` tool. Runs `diff -Bbq` under the hood.
Ignores whitespace and empty lines.

**Use is strongly discouraged because of the quadratic complexity of `diff`.**

## Custom judge

If there can be multiple correct solutions, it is necessary to write a custom judge.
Set `out_judge` to the path to the source code of your judge, `judge_type` to *ehm* the judge type (see below),
and `judge_needs_in`, `judge_needs_out` to `0`/`1` depending whether the judge needs the input and the correct output.

When writing a custom judge, you can chose from multiple judge types: 

1. [cms-batch judge](#cms-batch-judge)
2. [opendata-v2](#opendata-v2-judge)
3. [opendata-v1](#opendata-v1-judge)

### Cms-batch judge

The CMS batch judge format as described in the [CMS documentation](https://cms.readthedocs.io/en/v1.4/Task%20types.html?highlight=Manager#checker).

It is run as follows (having filenames given as arguments):
```
./judge <input> <correct output> <contestant output>
```

The judge should print a relative number of points (a float between 0.0 and 1.0) to it's stdout as a single line.
To its stderr it should write a single-line message to the contestant.
**Unlike the CMS documentation specifies, the files should be single-line only.**
There will be a warning otherwise.

### Opendata-v2 judge

The opendata-v2 judge is run in this way:
```
./judge <test> <seed> < contestant-output
```
Where `test` is testcase's test number and `seed` testcase's generating seed.
(The arguments are the same as were given to the `opendata-v1` generator
this input has (probably) been generated with.)
If the input was not generated with a seed (static or unseeded), `seed` will be `-`.

If `judge_needs_in` is set, the judge will get the input filename in the `TEST_INPUT`
environment variable. Similarly, if `judge_needs_out` is set, the correct output
filename will be in the `TEST_OUTPUT` environment variable.

If the output is correct, the judge should exit with returncode 42.
Otherwise, the judge should exit returncode 43.

Optionally, the judge can write a one-line message for the contestant
to stderr (at most 255 bytes), followed by a sequence of lines with `KEY=value` pairs.
The following keys are allowed:

- `POINTS` — Number of points awarded for this test case (used only if the exit code says "OK").
- `LOG` — A message that should be logged.
- `NOTE` — An internal note recorded in the database, but not visible to contestants.

Values are again limited to 255 bytes.

### Opendata-v1 judge

The opendata-v1 judge is the same as opendata-v2, with the exception of using different
returncodes, returncode 0 for a correct output and returncode 1 for a wrong output.

However, usage of this judge type is discouraged as these returncodes can
also be the result of an internal judge bug.
