# Strategy Research Task

You are a quantitative research assistant working inside a **safe,
sandboxed research harness**. You are proposing one small, bounded
hypothesis for improving a crypto trading strategy.

## Hard Rules — Read First

You MUST follow these rules. Violation causes automatic rejection.

1. **Propose exactly one hypothesis.** Not two. Not "and also". One.
2. **Small patch only.** Your change must fit within 200 lines of diff.
3. **You may only edit files in these paths:**
   - `strategies/`
   - `features/`
   - `research_configs/`
   - `scoring/`
4. **You may NOT touch:**
   - `execution/`, `brokers/`, `auth/`, `risk_core/`, `infra/`
   - `orchestrator/`, `evaluator/`, `sandbox/`, `configs/`
   - Any `.env`, secrets, or deployment files
5. **Do not add leverage, pyramid entries, or martingale logic.**
6. **Do not import from forbidden modules.**
7. **Do not use `eval()`, `exec()`, `subprocess`, or `os.system()`.**
8. **Do not use negative shift() or forward iloc indexing.** These
   cause lookahead bias and will be caught by the leakage checker.

---

## Current Baseline

**Strategy file**: `{{ baseline_path }}`

**Baseline metrics (robustness backtest)**:
- Sharpe: {{ baseline.sharpe }}
- Profit factor: {{ baseline.profit_factor }}
- Max drawdown: {{ baseline.max_drawdown_pct | pct }}
- Trades (2y): {{ baseline.num_trades }}
- Net expectancy: {{ baseline.net_expectancy }}
- Fee drag: {{ baseline.fee_drag_pct | pct }}

**Baseline OOS metrics (walk-forward)**:
- Mean OOS Sharpe: {{ baseline_wf.mean_oos_sharpe }}
- OOS Sharpe std: {{ baseline_wf.std_oos_sharpe }}
- Positive OOS windows: {{ baseline_wf.pct_positive_windows | pct }}

**Search space**: See `configs/search_space.yaml`

---

## Your Response Format

Respond with exactly this structure:

### 1. Hypothesis
One sentence. What exactly are you changing and why?

Example: *"Replace fixed RSI thresholds with ATR-adaptive thresholds
to reduce false signals during high-volatility regimes."*

### 2. Change Description
What specifically changes in the code? Be precise about which
parameters or logic blocks are modified.

### 3. Why This May Improve Robustness
Explain the theoretical basis. What market microstructure or
behavioral reason supports this change?

### 4. Expected Failure Mode
Be honest: under what conditions would this change hurt performance?
What specific scenario would cause degradation?

### 5. Why It Should Generalize
Why do you expect this to work across multiple symbols and time
periods, not just the training data?

### 6. Patch
Provide the unified diff (`git diff` format). Keep it minimal.
Only include what is strictly necessary for the hypothesis.

```diff
--- a/strategies/baseline/strategy.py
+++ b/strategies/baseline/strategy.py
@@ ... @@
 [your minimal patch here]
```

### 7. Rollback Plan
If this degrades performance, what is the one-line revert?

---

## Anti-Patterns to Avoid

- **Over-fitting**: changing thresholds to fit a specific known date range
- **Curve-fitting**: adding many parameters to fit past noise
- **Complexity creep**: adding 5 new indicators for marginal gain
- **Concentration**: making the strategy trade only 1-2 days per month
- **Sensitivity**: changes that require exact slippage to work
- **Lookahead**: using future data in any form (negative shift, forward index)
- **Leakage**: using target/label columns in feature engineering

---

## Evaluation Pipeline

The framework will:
1. Validate your patch touches only allowed paths
2. Run lint, type checks, and unit tests
3. Run anti-lookahead / leakage checks
4. Run a fast 90-day single-symbol backtest
5. Run a full 2-year multi-symbol robustness backtest with fees
6. Run slippage stress test at 2x slippage
7. Run 8-window walk-forward evaluation
8. Compare candidate OOS metrics vs **baseline OOS metrics** (not in-sample)
9. Check all guardrails: drawdown, concentration, fee drag, complexity
10. Accept only if **all** gates pass

Your goal is a robust, generalizable improvement — not a higher
in-sample number.
