#include <stdio.h>
#include <math.h>

int main(void) {
    int n, m=0, x;
    scanf("%d", &n);
    for (int i=0; i<n; i++) {
        scanf("%d", &x);
        m = x > m ? x : m;
    }
    printf("%d\n", m);
    return 0;
}
