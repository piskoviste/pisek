use std::io;

fn main() {
    let mut input = String::new();
    io::stdin().read_line(&mut input).expect("Failed to read line");

    let parts: Vec<&str> = input.trim().split_whitespace().collect();
    if parts.len() != 2 {
        panic!("Please provide exactly two numbers: N and K");
    }

    let n: usize = parts[0].parse().expect("Invalid number for N");
    let k: usize = parts[1].parse().expect("Invalid number for K");

    let value = k / n;

    for _ in 0..n {
        print!("{} ", value);
    }
    println!();
}
