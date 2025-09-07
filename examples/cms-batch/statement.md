# Building sandcastles

Timmy is at the beach and he wants to build sandcastles for his little kingdom.
He has already dug up $K$ piles of sand and wants to use **all** of them to build $N$ sandcastles. 
Tell him how many piles of sand should end up in each castle. 

## Input format

On the only line of input you will get two positive integers — $N$ and $K$.

## Output format

Output a single line with $N$ positive integers — the size of each sandcastle. 
The sizes of the sandcastles should sum up to $K$.

## Constraints

- $1 \leq N \leq 10^5$
- $1 \leq K \leq 10^9$
- There is enough sand to build $N$ sandcastles, i.e. $K \geq N$

## Scoring

| Subtask | Score |   Additional constraints   |
| ------- | ----- | -------------------------- |
|    1    |   20  | $N = K$                    |
|    2    |   30  | $K \leq 10^5$              |
|    3    |   50  | No additional constraints. |

You can get half of the points for every subtask by using at least half of the sand.
In other words, if the sizes of your sandcastles sum up to at least $K/2$. 
