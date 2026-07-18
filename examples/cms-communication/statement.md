# Binary search

Ben is at a well-known festival. There, he notices a teddy-bear in one of the stands.
For winning a simple game, the teddy-bear can be his...

In the game, there are $N$ cups placed upside down, each containing a certain number of balls.
Ben's goal is to find a cup with $X$ balls (or say that no such cup exists).
He can then repeatedly peek into one of the cups, learning how many balls are in it.
Luckily, Ben knows that each cup contains at least as many balls as the cup to its left.
Can you help Ben win this game peeking into as few cups as possible?

## Implementation details — C / C++

You should implement the following function:
```
int solve(int n, int x)
```
which should return the position of the cup with $X$ balls. If there is no such cup, return -1.

You can use the following function to peek into the cups:
```
int peek(int pos)
```
Given position of the cup $p$ ($0 \leq p < n$), it returns the number of balls in the cup at position $p$.

## Implementation details — Python

First call the function:
```
load() -> tuple[int, int]
```
which returns $N$ and $X$ respectively.

Then you can make calls to:
```
peek(pos: int) -> int
```
which returns the number of balls in the cup at position $p$ ($0 \leq p < n$).

Afterwards, you should call the following function with the position of the cup with $X$ balls
(or with $-1$, if no such cup exists).
```
answer(pos: int) -> NoReturn
``` 

## Constraints

- $1 \leq N \leq 10^6$
- $1 \leq X \leq 10^9$
- For the number of balls in each cup $b_i$, it holds:
    - $1 \leq b_i \leq 10^9$ for all $0 \leq i < n$
    - $b_{i-1} \leq b_i$ for all $1 \leq i < n$

## Scoring

| Subtask | Score |   Additional constraints    |
| ------- | ----- | --------------------------- |
|    1    |   20  | $N \leq 10$                 |
|    2    |   30  | $N \leq 10^3$               |
|    3    |   50  | *no additional constraints* |
