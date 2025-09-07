#include <stdio.h>

int main() {
    int n, k;
    scanf("%d %d", &n, &k);

    for (int i=0; i<n-1; i++) {
        printf("1 ");
    }
    printf("%d\n", k-n+1);
}
