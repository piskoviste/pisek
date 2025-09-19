# Cheatsheet

## Task creation

Create a task skeleton:
```bash
pisek init
```

## Task testing

Test a task:
```bash
pisek test
```

Test only specific solutions:
```bash
pisek test solutions solution1 solution2 ...
```

Test only generator:
```bash
pisek test generator
```

## Testing with flags

Show file **c**ontents on failure:
```bash
pisek test -C
```

Override time limit for solutions to 3 seconds:
```bash
pisek test -t 3
```

Test all inputs (don't skip those which do not matter):
```bash
pisek test -a
```

Be verbose:
```bash
pisek test -v
```

Do final pre-production check. Test all inputs, be verbose and interpret warnings as failures.
```bash
pisek test -a -v --strict
```

## Clean

Clean pisek cache and created files (executables in `build/` and test data in `tests/`):
```bash
pisek clean
```

## Visualization

Visualize all solutions and their closeness to time limit. Calculate valid time limits:
```bash
pisek test -af --testing-log
pisek visualize | less -R
```

## Configs
Update config to newest version
```bash
pisek config update
```
