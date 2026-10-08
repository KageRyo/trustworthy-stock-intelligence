# Risk Labeling

## Labeling Objective

The first research task is 5-day drawdown risk warning. For each stock and each trading day `t`, the
label asks whether the stock will experience a material drawdown within the next `H` trading days.

Initial setting:

```text
H = 5 trading days
threshold = -5%
Risk = 1 if future 5-day max drawdown <= -5%
Risk = 0 otherwise
```

## Time Boundary

The most important rule is:

```text
Features may only use information available up to day t.
Labels may only use information from day t+1 through day t+H.
```

This boundary prevents look-ahead bias. Any feature that uses future price, future return, future
volume, future volatility, or future index movement is invalid.

## Future Drawdown Definition

For a stock with adjusted close price `P_t`, the future drawdown over horizon `H` is:

```text
future_drawdown(t, H) = min_{k in 1..H} (P_{t+k} / P_t - 1)
```

The binary risk label is:

```text
risk_label(t) = 1 if future_drawdown(t, H) <= threshold
risk_label(t) = 0 otherwise
```

With the first milestone settings:

```text
risk_label(t) = 1 if min_{k in 1..5} (P_{t+k} / P_t - 1) <= -0.05
```

## Example

If today's adjusted close is `100` and the next five adjusted closes are:

```text
98, 97, 94, 96, 95
```

The future drawdown values are:

```text
-2%, -3%, -6%, -4%, -5%
```

The future 5-day max drawdown is `-6%`, so:

```text
Risk = 1
```

## Data Requirements

The first version uses daily OHLCV data with this schema:

```text
date
ticker
open
high
low
close
adj_close
volume
```

The label should be computed from `adj_close` unless an experiment explicitly documents a different
price field.

## Invalid Rows

Rows near the end of each ticker's time series may not have enough future observations to compute a
full `H`-day label. These rows must be excluded from supervised training and evaluation.

Rows at train/calibration/test boundaries need a separate guard. The splitter must exclude at least
`H` dates between windows so an earlier label cannot use prices from the following window. Dropping
only the final unavailable labels does not prevent this boundary overlap. The labeler records
`label_end_date`, and the splitter checks it against the next window in addition to the date gap.

Rows with missing or non-positive adjusted close prices must also be excluded from label
computation.

## Leakage Checklist

Before using a labeled dataset, verify:

- technical indicators are computed using data up to `t`
- rolling windows do not include `t+1` or later
- normalization parameters are fit only on training windows
- calibration models are fit only on calibration windows
- labels use only `t+1` through `t+H`
- random train-test splits are not used for the main protocol

## Extensions

Future versions may add:

- volatility risk labels
- market-relative drawdown labels
- sector-relative drawdown labels
- multi-level warning labels
- event duration labels

These extensions should preserve the same time-boundary principle.
