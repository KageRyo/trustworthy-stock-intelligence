# Experiment 020: Serving Replay and Calibration Reversal

## Question

Experiments 007 to 018 evaluate a fixed 252-date training window. Serving does something else: `predict_latest_baseline` trains on every labeled date before a 63-date Platt calibration window, holds out a 21-date drift window, and on-demand analysis fits that model on one ticker's history alone. This experiment replays the served scheme itself and asks:

1. How often does Platt calibration get a non-positive slope, which reverses the model's ranking?
1. Does a monotone fallback fix the reversal without hurting calibration?
1. How do single-ticker on-demand models compare with a model fitted on all tickers?
1. Does that comparison hold for tickers the pooled model never saw, which is the real on-demand case?

The question came from Experiment 019. In the S&P 100 fold that tests 2020-05-19 to 2020-08-17, the expanding-window logistic model ranks test rows at AUC 0.660, but its calibration window (the 2020 crash, 42% event rate) gives a Platt slope of -0.19 and a calibrated AUC of 0.340. The Experiment 007 audit had already found one reversed fold (fold 8, slope -0.798, 2018 test window), but serving was never guarded.

It is pilot research evidence, not investment advice or a trading-performance claim.

## Data

| Sample                         | Tickers |      Rows | Role                                 |
| ------------------------------ | ------: | --------: | ------------------------------------ |
| S&P 100                        |     101 |   283,289 | Discovery                            |
| Taiwan large caps (`tw_large`) |      53 |   150,935 | Market transfer check                |
| S&P 500 excluding S&P 100      |     402 | 1,105,354 | Unseen tickers for the S&P 100 model |
| TWSE holdout (`tw_holdout`)    |     200 |   572,199 | Unseen tickers for the Taiwan model  |

These are the Experiment 017 and 018 snapshots. Neither unseen sample shares a ticker with its training universe. Hashes are in [`run_manifest.json`](run_manifest.json).

## Protocol

- As-of dates start after 400 labeled dates and repeat every 21 trading dates, 113 per sample.
- At each as-of date the replay keeps only labels observable by then (rows dated at least 5 trading dates earlier) and applies the serving split with the served functions:
  - train: every earlier labeled date;
  - calibration: 63 dates;
  - drift: the latest 21 dates, held out as serving does.
- Two fits per as-of date:
  - **pooled**: one logistic model on all tickers, as the batch path does;
  - **single-ticker**: one logistic model per ticker with at least 400 labeled dates, as on-demand analysis does.
- Each fit scores the next 63 trading dates with raw probabilities, Platt calibration (`platt`), and the monotone fallback (`platt_monotone`).
- `platt_monotone` fits Platt scaling. If the slope is not positive, it keeps the model's ranking and shifts the raw log-odds so that the mean calibrated probability equals the calibration window's event rate.
- Per-ticker history AUC scores each row once, with the latest fit before it (the next 21 dates after every as-of date), and ranks one ticker's own dates over the whole replay.
- **Unseen tickers** (`--score-input`): the pooled model still trains on the universe, but single-ticker models and per-ticker history AUC use tickers from a second file on the same calendar. Every scored ticker is new to the pooled model, as on-demand tickers are.
- Features are `technical_range`, and the label is a drawdown of -5% or worse within 5 trading days.

## Result

### Pooled models

| Sample  | As-of dates | Slope ≤ 0 | AUC, Platt | AUC, monotone | Brier, Platt | Brier, monotone | ECE, Platt | ECE, monotone |
| ------- | ----------: | --------: | ---------: | ------------: | -----------: | --------------: | ---------: | ------------: |
| S&P 100 |         113 |         1 |     0.6556 |        0.6602 |       0.0929 |          0.0927 |     0.0534 |        0.0526 |
| Taiwan  |         113 |         0 |     0.7466 |        0.7466 |       0.0881 |          0.0881 |     0.0469 |        0.0469 |

The one S&P 100 reversal is the 2018-06-05 as-of date. Its calibration window ranked rows at AUC 0.450, Platt fitted a slope of -1.12, and the next 63 dates scored AUC 0.242 with Platt against 0.758 for the raw and monotone probabilities.

### Single-ticker models

| Sample  | Ticker-dates | Slope ≤ 0 | Median calibration positives | AUC, raw | AUC, Platt | Brier, Platt | Brier, monotone | ECE, Platt | ECE, monotone |
| ------- | -----------: | --------: | ---------------------------: | -------: | ---------: | -----------: | --------------: | ---------: | ------------: |
| S&P 100 |        6,927 |     51.4% |                            7 |   0.4976 |     0.5061 |       0.1277 |          0.1294 |     0.1036 |        0.1112 |
| Taiwan  |        3,355 |     50.2% |                            8 |   0.5089 |     0.5046 |       0.1376 |          0.1393 |     0.0999 |        0.1098 |

Every S&P 100 ticker but one, and every Taiwan ticker, had a non-positive slope at some as-of date.

### Per-ticker history AUC

| Sample  | Tickers | Pooled mean | Single-ticker mean | Pooled better |
| ------- | ------: | ----------: | -----------------: | ------------: |
| S&P 100 |     101 |       0.633 |              0.566 |         93.1% |
| Taiwan  |      51 |       0.672 |              0.632 |         80.4% |

### Unseen tickers

| Pooled model trained on | Scored tickers            | Tickers | Pooled history AUC | Single-ticker history AUC | Pooled better | Single slope ≤ 0 | Single AUC, raw | Single AUC, Platt |
| ----------------------- | ------------------------- | ------: | -----------------: | ------------------------: | ------------: | ---------------: | --------------: | ----------------: |
| S&P 100                 | S&P 500 excluding S&P 100 |     400 |              0.616 |                     0.549 |         93.5% |            53.1% |          0.4934 |            0.5059 |
| Taiwan large caps       | TWSE holdout              |     194 |              0.694 |                     0.656 |         90.7% |            39.7% |          0.5533 |            0.5163 |

These runs reuse the pooled fits of the S&P 100 and Taiwan runs, so their pooled-model results equal the first table.

## Findings

- **Calibration can reverse a working model.** When the latest calibration window is a regime break, Platt scaling can fit a negative slope and rank the riskiest rows as the safest. It is rare for the pooled model (1 of 226 as-of dates) but severe when it happens (AUC 0.758 to 0.242).
- **The monotone fallback fixes the pooled case at no cost.** It keeps every non-reversed result identical, restores the reversed date's ranking, and slightly improves the mean Brier score and ECE.
- **Single-ticker models carry no ranking signal within a 63-date window.** Their raw AUC is about 0.50, and the Platt slope sign is a coin flip. The fallback cannot help here: it keeps a ranking that has no signal, and its wider spread costs about 0.002 Brier and 0.008 ECE against Platt's near-flat fit.
- **A pooled model ranks a ticker's own history better.** Over the whole replay, the pooled model ranks a ticker's dates at AUC 0.633 (S&P 100) and 0.672 (Taiwan), against 0.566 and 0.632 for single-ticker models, and wins for 93% and 80% of tickers.
- **The advantage holds for tickers the pooled model never saw.** Scored by a model fitted on another universe, 400 S&P 500 tickers rank their own dates at 0.616 against 0.549 for their own models, and 194 TWSE holdout tickers at 0.694 against 0.656. The pooled model wins for 93.5% and 90.7% of them.
- **The fallback helps single-ticker models that do carry a signal.** TWSE holdout models rank their next 63 dates at 0.553 before calibration. Platt reverses 40% of them and lowers that to 0.516; the fallback restores 0.553 at the same Brier score.

## Decision for serving

- Serving and on-demand analysis default to `--calibration-method platt_monotone` ([ADR 0007](../../docs/decisions/0007-calibration-keeps-model-ranking.md)). `platt` remains available and is still the default for the research scripts, so earlier experiments reproduce unchanged.
- When the fallback is used, every row of that batch carries the reason code `calibration_slope_nonpositive`. The API and dashboard explain it in English and 正體中文.
- On-demand analysis should score new tickers with a pooled model instead of fitting one ticker alone. The unseen-ticker runs are the evidence for that change.

## Reproduce

```bash
python -m scripts.evaluate_serving_replay --input data/raw/sp100/ohlcv.csv \
  --output-dir experiments/020_serving_replay/runs/sp100
python -m scripts.evaluate_serving_replay --input data/raw/tw_large/ohlcv.csv \
  --output-dir experiments/020_serving_replay/runs/tw_large
python -m scripts.evaluate_serving_replay --input data/raw/sp100/ohlcv.csv \
  --score-input data/raw/sp500_ex_sp100/ohlcv.csv \
  --output-dir experiments/020_serving_replay/runs/sp100_on_sp500_ex_sp100
python -m scripts.evaluate_serving_replay --input data/raw/tw_large/ohlcv.csv \
  --score-input data/raw/tw_holdout/ohlcv.csv \
  --output-dir experiments/020_serving_replay/runs/tw_large_on_tw_holdout
```

The S&P 100 replay takes about 13 minutes on CPU and the Taiwan replay about 7 minutes, both while another experiment shared the CPU. The unseen-ticker runs took about 39 minutes (S&P 500) and 10 minutes (TWSE holdout). A repeated Taiwan run reproduced all four output files byte for byte. `single_as_of.csv` (per ticker-date metrics, about 2 MB per sample) is regenerated by these commands and is not committed; its hashes are in the manifest.

## Limitations

- Calibration reversals of the pooled model were replayed on two universes only.
- 2 of 402 S&P 500 tickers and 6 of 200 TWSE holdout tickers had too little labeled history or no scored rows for a single-ticker fit, so the per-ticker comparison leaves them out.
- The replay refits every 21 trading dates; serving refits on every run, so the reversal rate per serving day is estimated, not counted.
- Per-ticker history AUC compares raw probabilities across refits. Calibrated probabilities would change the cross-refit scale, not the within-refit ranking.
- Current-constituent samples carry survivorship bias (Issue #29).
