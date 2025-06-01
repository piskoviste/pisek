use anyhow::{Result, bail};

pub fn min(list: &[i64]) -> Result<i64> {
    let Some(&answer) = list.iter().min() else {
        bail!("minimum is not finite");
    };

    Ok(answer)
}

pub fn max(list: &[i64]) -> Result<i64> {
    let Some(&answer) = list.iter().max() else {
        bail!("maximum is not finite");
    };

    Ok(answer)
}
