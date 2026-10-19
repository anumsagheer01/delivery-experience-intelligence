"""Power analysis and sequential-monitoring boundaries.

sample_size_two_sample: standard two-arm normal approximation.
design_effect: variance inflation for clustered (customer-level) units.
obf_boundaries: group-sequential critical values under the Lan-DeMets
    O'Brien-Fleming alpha-spending function, via the canonical joint
    distribution of sequential z-statistics (grid recursion).
"""
import math

import numpy as np
from scipy.stats import norm


def sample_size_two_sample(std: float, mde: float, alpha: float = 0.05,
                           power: float = 0.80) -> float:
    """Units per arm for a two-sample comparison of means."""
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    return 2 * ((z_alpha + z_beta) * std / mde) ** 2


def design_effect(mean_cluster_size: float, icc: float) -> float:
    """Variance inflation when units are clusters (customers)."""
    return 1 + (mean_cluster_size - 1) * icc


def _obf_spending(t: float, alpha: float) -> float:
    if t <= 0:
        return 0.0
    z = norm.ppf(1 - alpha / 2)
    return 2 * (1 - norm.cdf(z / math.sqrt(t)))


def obf_boundaries(n_looks: int, alpha: float = 0.05,
                   grid_n: int = 1201, z_max: float = 8.0):
    """O'Brien-Fleming critical values at each of n_looks equally spaced looks.

    Returns (bounds, info_fractions, spent_alpha). Reject H0 at look k when
    |z_k| >= bounds[k]. This controls the family-wise type I error at alpha
    across all looks, which naive repeated testing does not.
    """
    info = [(k + 1) / n_looks for k in range(n_looks)]
    spent = [_obf_spending(t, alpha) for t in info]
    increments = [spent[0]] + [spent[k] - spent[k - 1]
                               for k in range(1, n_looks)]

    grid = np.linspace(-z_max, z_max, grid_n)
    dz = grid[1] - grid[0]
    phi = norm.pdf(grid)

    density = phi.copy()  # f_1
    bounds = []
    t_prev = 0.0
    for k in range(n_looks):
        t = info[k]
        if k > 0:
            # FIRST restrict to paths that survived the previous look,
            # THEN propagate: f_k(z) = E[ T(U -> z) ] over |U| < c_{k-1}.
            # (Truncating after propagation instead would count paths that
            # already crossed, making later bounds too liberal.)
            c_prev = bounds[-1]
            density[np.abs(grid) >= c_prev] = 0.0
            rho = math.sqrt(t_prev / t)
            sigma = math.sqrt(max(1e-12, 1 - rho ** 2))
            # transition: f_k(z) = E[ phi((z - rho*U)/sigma)/sigma ] over U
            diff = grid[None, :] - rho * grid[:, None]
            trans = norm.pdf(diff / sigma) / sigma
            density = (density * dz) @ trans
        # solve P(|Z_k| >= c) = increments[k] for c by bisection
        lo, hi = 0.05, z_max
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            tail = density[np.abs(grid) >= mid].sum() * dz
            if tail > increments[k]:
                lo = mid
            else:
                hi = mid
        bounds.append(0.5 * (lo + hi))
        t_prev = t
    return bounds, info, spent
