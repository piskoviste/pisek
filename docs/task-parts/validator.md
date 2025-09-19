# Validator
The validator is used for validating inputs, i.e. making sure they conform to the restrictions in the task statement.

## Validator type
There are currently 2 validator types available:

- [simple-42](#simple-42)
- [simple-0](#simple-0)

### Simple-42
The simple-42 validator is run as follows:
```
./validate <test_num> < input
```
Where `test_num` is number of the test to which the input belongs.
If the input is valid, the validator should exit with **returncode 42**.
Otherwise, it should exit with any other returncode.

??? example "Example `simple-42` validator"

	For a [task](https://github.com/piskoviste/pisek/blob/master/examples/cms-batch) of printing *N* positive integers that sum up to *K*,
	the validator may look like this:
    ```py
    --8<-- "examples/cms-batch/validate.py"
    ```

### Simple-0
The simple-0 validator is run as follows:
```
./validate <test_num> < input
```
Where `test_num` is number of the test to which the input belongs.
If the input is valid, the validator should exit with **returncode 0**.
Otherwise, it should exit with any other returncode.

??? warning "This `validator_type` is not recommended"

    Return with exitcode 0 can be sometimes caused by libraries.
    It is better to avoid this pitfall and use the simple-42 validator type instead.
