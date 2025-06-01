use std::io::{BufRead, Write};

use anyhow::{Result, bail};
use token_read::TokenReader;

pub fn load_input(file: impl BufRead) -> Result<Vec<i64>> {
    let mut input = TokenReader::new(file);

    let (count,): (usize,) = input.line()?;
    let values: Vec<i64> = input.line()?;

    if values.len() != count {
        bail!("expected {count} numbers, got {real}", real = values.len());
    }

    Ok(values)
}

pub fn write_output(mut file: impl Write, value: i64) -> Result<()> {
    writeln!(file, "{value}")?;
    Ok(())
}
