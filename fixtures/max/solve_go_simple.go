package main

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	in := bufio.NewReader(os.Stdin)
	var n int
	if _, err := fmt.Fscan(in, &n); err != nil {
		return
	}
	var x, max int
	for i := 0; i < n; i++ {
		fmt.Fscan(in, &x)
		if i == 0 || x > max {
			max = x
		}
	}
	fmt.Println(max)
}
