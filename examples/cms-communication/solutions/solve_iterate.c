#include "binsearch.h"

int solve(int n, int x) {
    for (int i=0; i<n; i++) {
        if (peek(i) == x)
            return i;
    }
    return -1;
}
