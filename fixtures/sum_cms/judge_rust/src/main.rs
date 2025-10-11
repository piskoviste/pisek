use std::{env::args_os, ffi::OsString, fs::read_to_string, process::exit, str::FromStr};

fn main() {
    let [_program, input, _reference, contestant] = args_os().collect::<Vec<OsString>>().try_into().unwrap();

    let [a, b] = read_to_string(input)
        .unwrap()
        .split_whitespace()
        .map(i64::from_str)
        .collect::<Result<Vec<_>, _>>()
        .unwrap()
        .try_into()
        .unwrap();

    match read_to_string(contestant).unwrap().trim().parse::<i64>() {
        Ok(answer) => {
            if answer == a + b {
                report("translate:correct", 1.0);
            } else if answer == a.abs() + b.abs() {
                report("translate:partial", 0.5);
            } else {
                report("translate:wrong", 0.0);
            }
        }
        Err(_) => report("translate:wrong", 0.0),
    }
}

fn report(message: &str, points: f64) {
    println!("{points}");
    eprintln!("{message}");

    exit(0)
}
