#include "binsearch.h"
#include <iostream>

using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, x; cin >> n >> x;
    int answer = solve(n, x);
    cout << "! " << answer << endl;
}

int peek(int i) {
    cout << "? " << i << endl;
    int x;
    cin >> x;
    if (x == -1) exit(0);
    return x;
}

