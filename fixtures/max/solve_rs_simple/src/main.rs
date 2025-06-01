use std::{
    error::Error,
    io::{self, BufRead, Write, stdin, stdout},
};

fn main() -> Result<(), Box<dyn Error>> {
    let mut lines = stdin().lock().lines();

    let count: usize = lines
        .next()
        .ok_or(io::Error::from(io::ErrorKind::UnexpectedEof))??
        .parse()?;

    let line = lines
        .next()
        .ok_or(io::Error::from(io::ErrorKind::UnexpectedEof))??;

    let numbers: Vec<i64> = line
        .split(' ')
        .map(|s| s.parse())
        .collect::<Result<_, _>>()?;

    if numbers.len() != count {
        return Err("got an unexpected number of numbers".into());
    }

    let max = *numbers
        .iter()
        .max()
        .ok_or("cannot compute maximum of 0 numbers")?;

    writeln!(stdout().lock(), "{max}")?;

    Ok(())
}
