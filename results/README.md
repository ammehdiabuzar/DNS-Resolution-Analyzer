# Results

`python scripts/run_experiments.py` generates the files in this folder. None of them is written by hand.

* `raw/<condition>_run<N>.csv`: every sample in long format (`condition, rtt_ms, loss_pct, run, metric, label, sample, value`).
* `raw/<condition>_run<N>.windows.json`: the time windows used for the capture analysis.
* `summary.csv`: the mean, std, min, max and number of runs per condition, metric and label.
* `experiment_table.md`: the experiment table used in the report.
* `plots/*.png`: the graphs.
