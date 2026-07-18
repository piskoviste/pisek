#include "binsearch.h"

using namespace std;

int solve(int n, int x) {
    int l = -1;
    int r = n;
    while (l+1 < r) {
        int mid = (l+r)/2;
        int element = peek(mid);
        if (element < x) {
            l = mid;
        } else if (element > x) {
            r = mid;
        } else {
            return mid;
        }
    }
    return -1;
}
