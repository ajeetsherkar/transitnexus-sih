import numpy as np


def bootstrap_ci(x, stat=np.median, n=5000, alpha=0.05, seed=0):
    """
    Estimate a confidence interval using bootstrap resampling.

    Resampling with replacement means that each new sample is
    randomly selected from the original data, and the same
    observation can be selected more than once.

    Args:
        x: Original sample data.
        stat: Statistic to estimate (default: median).
        n: Number of bootstrap samples.
        alpha: Significance level (0.05 gives a 95% CI).
        seed: Random seed for reproducibility.

    Returns:
        Lower and upper bounds of the bootstrap confidence interval.
    """
    x = np.asarray(x)
    rng = np.random.default_rng(seed)

    boots = [
        stat(rng.choice(x, size=len(x), replace=True))
        for _ in range(n)
    ]

    return np.percentile(
        boots,
        [100 * alpha / 2, 100 * (1 - alpha / 2)]
    )
