#include <iostream>
#include <unistd.h>
using namespace std;

int main() {
    long long a, b;
    cin >> a >> b;
    if (a > (long long) 1e9) {
        // Simulate a slow algorithm
        while (true) {}
    }
    cout << (a + b) << endl;
}
