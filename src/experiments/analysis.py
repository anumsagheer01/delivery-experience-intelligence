"""Statistical analysis for the outreach experiment.

welch_ttest: difference in means with confidence interval.
proportion_test: difference in low-review rates with CI.
cuped_adjust / cuped_gate: covariate adjustment, applied only when the
    covariate earns it on historical data (variance reduction gate).
sequential_decision: compare observed z-statistics against pre-registered
    O'Brien-Fleming boundaries.
"""
import numpy as np
from scipy import stats

from .design import CUPED_MIN_VARIANCE_REDUCTION


def welch_ttest(treatment, control, alpha=0.05):
    """Difference in means (treatment minus control) with CI."""
    t = np.asarray(treatment, dtype=float)
    c = np.asarray(control, dtype=float)
    res = stats.ttest_ind(t, c, equal_var=False)
    diff = t.mean() - c.mean()
    # standard error recovered from t = diff / se
    se = abs(diff / res.statistic) if res.statistic else float("nan")
    z = stats.norm.ppf(1 - alpha / 2)
    return {
        "diff": float(diff),
        "se": float(se),
        "t_stat": float(res.statistic),
        "p_value": float(res.pvalue),
        "ci_low": float(diff - z * se),
        "ci_high": float(diff + z * se),
        "n_treatment": int(len(t)),
        "n_control": int(len(c)),
    }


def math_sqrt(x):
    import math
    return math.sqrt(max(x, 0.0))


def proportion_test(treatment_success, n_treatment,
                    control_success, n_control, alpha=0.05):
    """Difference in proportions (treatment minus control) with Wald CI."""
    p_t = treatment_success / n_treatment
    p_c = control_success / n_control
    diff = p_t - p_c
    se = math_sqrt(p_t * (1 - p_t) / n_treatment
                   + p_c * (1 - p_c) / n_control)
    z = stats.norm.ppf(1 - alpha / 2)
    z_stat = diff / se if se > 0 else 0.0
    return {
        "diff": float(diff),
        "se": float(se),
        "z_stat": float(z_stat),
        "p_value": float(2 * (1 - stats.norm.cdf(abs(z_stat)))),
        "ci_low": float(diff - z * se),
        "ci_high": float(diff + z * se),
    }


def cuped_adjust(outcome, covariate):
    """CUPED adjustment. Returns (adjusted_outcome, theta, var_reduction)."""
    y = np.asarray(outcome, dtype=float)
    x = np.asarray(covariate, dtype=float)
    mask = np.isfinite(y) & np.isfinite(x)
    y, x = y[mask], x[mask]
    if x.var() == 0 or len(y) < 10:
        return y, 0.0, 0.0
    theta = np.cov(y, x, ddof=1)[0, 1] / x.var()
    y_adj = y - theta * (x - x.mean())
    reduction = 1 - y_adj.var() / y.var() if y.var() > 0 else 0.0
    return y_adj, float(theta), float(reduction)


def cuped_gate(outcome, covariate,
               min_reduction=CUPED_MIN_VARIANCE_REDUCTION):
    """Decide whether the covariate earns its place.

    A covariate is valid only if it is pre-treatment (known before the
    message is sent) and only useful if it actually cuts variance on
    historical data. Returns (use_it, theta, var_reduction).
    """
    _, theta, reduction = cuped_adjust(outcome, covariate)
    return reduction >= min_reduction, theta, reduction


def sequential_decision(z_stats, bounds):
    """Apply pre-registered OBF boundaries to observed z-statistics.

    Returns a list of per-look dicts with the decision at each look:
    'reject' (efficacy), or 'continue'. Stopping for futility is not
    implemented; the plan runs to the final look unless efficacy is shown.
    """
    out = []
    for k, (z, b) in enumerate(zip(z_stats, bounds)):
        decision = "reject" if abs(z) >= b else "continue"
        out.append({"look": k + 1, "z": float(z), "bound": float(b),
                    "decision": decision})
        if decision == "reject":
            break
    return out
