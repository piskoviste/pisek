#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <iostream>

using namespace std;

void verdict(bool ok, const char *msg){
    fprintf(stderr, msg);
	exit(ok ? 42 : 43);
}

int main(int argc, char** argv) {
	FILE* fin = fopen(getenv("TEST_INPUT"), "r");
	FILE* fcorrect = fopen(getenv("TEST_OUTPUT"), "r");

	assert(fin && fcorrect);

    int t;
    fscanf(fin, "%d", &t);

    for (int i = 0; i < t; i++) {
        long long a, b, c, contestant;

        fscanf(fin, "%lld%lld", &a, &b);
        fscanf(fcorrect, "%lld", &c);

        if (scanf("%lld", &contestant) < 1)
            verdict(false, "Invalid format");

        assert(a + b == c);
        if (c != contestant)
            verdict(false, "Wrong answer");
	}

	char trailing;
	if (scanf(" %c", &trailing) == 1)
        verdict(false, "Wrong answer");

    verdict(true, "Correct answer");
}
