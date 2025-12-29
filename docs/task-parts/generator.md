# Generator
The generator is used for generating inputs. Solutions are then run and judged on those.

## Generator type
There are currently 3 [`gen_type`](../config-v3-documentation.md#gen_type)s available:

- [pisek-v1](#pisek-v1)
- [cms-old](#cms-old)
- [opendata-v1](#opendata-v1)

However, we strongly recommend using the first (pisek-gen) type
for better debugging and easy conversion between open data and closed data tasks.

## Terminology
There are two requirements for generators:

- *Generators must be deterministic.* — For the same arguments, they should always generate the same input(s).
- *Generators must respect the seed* — If a generator takes a seed as an argument, the generator should generate different inputs for different seeds. This can be disabled in the with
[`checks.generator_respects_seed`](../config-v3-documentation.md#checksgenerator_respects_seed), but be careful.

## Pisek-v1
### Listing inputs
When run without arguments it should list all inputs it can generate in the following format:
```
input_name key1=value1 key2=value2
```
Where `input_name` is the name of the given input. The input will be generated into the file
`[input_name]_[seed].in` or `[input_name]` (depending whether the input is seeded).
This is followed by any number of key=value pairs separated by spaces.
The following keys are supported:

| Key    | Meaning                                        | Value type | Default value |
| ------ | ---------------------------------------------- | ---------- | ------------- |
| repeat | How many times should this input be generated? | int        | 1             |
| seeded | Is this input generated with a random seed?    | bool       | true          |

If the input is not seeded, repeat must be 1.

For example:
```
01_tree
02_random_graph repeat=10
02_complete_graph seeded=false
```

??? example "Example `pisek-v1` generator"

	For a [task](https://github.com/piskoviste/pisek/blob/master/examples/cms-batch) of printing *N* positive integers that sum up to *K*,
	the generator may look like this:
    ```py
    --8<-- "examples/cms-batch/gen.py"
    ```

### Generating inputs
The generator is then repeatedly asked to generate the input `input_name` from
the inputs list.

If `input_name` is seeded, the generator is run with:
```
./gen <input_name> <seed>
```
Where `seed` is a 16-digit hexadecimal number. The generator must be deterministic and
respect the seed.

If `input_name` is unseeded, the generator is called with
```
./gen <input_name>
```
The generator must be deterministic.

In either case, the generator should print the input to its stdout.

## Cms-old

The generator is run with:
```
./gen <directory>
```

The generator should generate all input files to this directory. The generator must be deterministic.

??? warning "This `gen_type` is not recommended"

    We don't recommend using this generator type for these reasons:

    - It's **hard to debug**, as you don't know during the generation of what input the bug occurs.
    - You need to write **your own management code** for which inputs to generate, how many times, and what seeds to use.

## Opendata-v1
The generator is run:
```
./gen <test> <seed>
```
Where `seed` is 16-digit hexadecimal number.

The generator should generate the input for this test to its stdout. The generator must be deterministic
and respect the given seed.

(Please note that the generator can generate only one input for each test.)

??? example "Example `opendata-v1` generator"

	For a [task](https://github.com/piskoviste/pisek/blob/master/examples/opendata) of printing *N* positive integers that sum up to *K*,
	the generator may look like this:
    ```py
    --8<-- "examples/opendata/gen.py"
    ```
