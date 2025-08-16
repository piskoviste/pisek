#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <iostream>

using namespace std;

void verdict(float pts, string msg){
	cout << pts << endl;
	cerr << msg << endl;
	exit(0);
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

        if (scanf("%lld", &contestant) < 1) {
            fprintf(stderr, "Invalid format");
            return 43;
        }

        assert(a + b == c);
        if (c != contestant) {
            fprintf(stderr, "Wrong answer", contestant);
            return 43;
        }
	}

    fprintf(stderr, "Correct answer");
	return 42;
}
