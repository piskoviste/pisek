#include "binsearch.h"
#include <stdio.h>
#include <stdlib.h>

int main() {
    int n, x;
    scanf("%d %d", &n, &x);
    int answer = solve(n, x);
    printf("! %d\n", answer);
    fflush(stdout);
}

int peek(int pos) {
    printf("? %d\n", pos);
    fflush(stdout);
    int x;
    scanf("%d", &x);
    if (x == -1) exit(0);
    return x;
}

