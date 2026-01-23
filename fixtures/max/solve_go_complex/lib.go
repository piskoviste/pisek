package main

func max(nums []int) int {
	result := nums[0]
	for _, num := range nums {
		if num > result {
			result = num
		}
	}
	return result
}
