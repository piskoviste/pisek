use std::io::{BufWriter, stdin, stdout};

use anyhow::Result;
use minmax::max;
use solve::{load_input, write_output};

fn main() -> Result<()> {
    let input = load_input(stdin().lock())?;
    let output = max(&input)?;
    write_output(BufWriter::new(stdout().lock()), output)?;

    Ok(())
}
