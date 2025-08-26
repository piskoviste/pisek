# Validator
The validator is used for validating inputs, i.e. making sure they conform to the restrictions in the task statement.

## Validator type
There are currently 2 validator types available:

- simple-42
- simple-0

### Simple-42
The simple-42 validator is run as follows:
```
./validate <test_num> < input
```
Where `test_num` is number of the test to which the input belongs.
If the input is valid, the validator should exit with **returncode 42**.
Otherwise, it should exit with any other returncode.

### Simple-0
The simple-0 validator is run as follows:
```
./validate <test_num> < input
```
Where `test_num` is number of the test to which the input belongs.
If the input is valid, the validator should exit with **returncode 0**.
Otherwise, it should exit with any other returncode.
