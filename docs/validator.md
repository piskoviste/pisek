# Validator
The validator is used for validating inputs, i.e. making sure they conform to the restrictions in the task statement.

The validator is run as follows:
```
./validate <test_num> < input
```
Where `test_num` is number of the test to which the input belongs.
If the input is valid, the validator should exit with returncode 0.
Otherwise, it should exit with any other returncode.
