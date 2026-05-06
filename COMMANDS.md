# Orbit Wars Simulation Command Reference

This file documents the command-line scripts created in this workspace and how to use them.

## Scripts

### `simulate.py`
Runs one or more Orbit Wars simulation matches between two agent files.

#### Usage

```bash
python simulate.py [options]
```

#### Options

- `--agent`: Path to the first agent file. Default: `test.py`
- `--opponent`: Path to the opponent agent file. Default: `agent1.py`
- `--count`: Number of matches to run. Default: `1`
- `--render`: Render the match in HTML after completion. Requires the `vizar-orbit-data` dataset to be available at `/workspaces/wtrmrk-rm/vizar-orbit-data`
- `--no-summary`: Suppress summary output in the console
- `--log-steps`: Save per-step replay logs to text files
- `--log-dir`: Output directory for log files. Default: `batch_logs`

#### Examples

Run a single match:

```bash
python simulate.py --agent test.py --opponent agent1.py
```

Run 5 matches and print a summary for each:

```bash
python simulate.py --agent test.py --opponent agent2.py --count 5
```

Run 3 matches and save detailed step logs:

```bash
python simulate.py --agent test.py --opponent agent3.py --count 3 --log-steps --log-dir batch_logs
```

Render the match result in HTML after simulation:

```bash
python simulate.py --agent test.py --opponent agent1.py --render
```


### `batch_simulation.py`
Runs `test.py` against multiple opponent agents in a batch and prints aggregated results.

#### Usage

```bash
python batch_simulation.py [options]
```

#### Options

- `--agent`: Path to the primary agent file. Default: `test.py`
- `--opponents`: Comma-separated list of opponent agent files. Default: `agent1.py,agent2.py,agent3.py`
- `--count`: Number of matches to run against each opponent. Default: `5`
- `--render`: Render each match in HTML after completion (not recommended for batch runs)
- `--log-steps`: Save per-step match logs to text files
- `--log-dir`: Output directory for log files. Default: `batch_logs`

#### Examples

Run the default batch of opponents 5 times each:

```bash
python batch_simulation.py --count 5
```

Run only against `agent2.py` and `agent3.py`:

```bash
python batch_simulation.py --opponents agent2.py,agent3.py --count 5
```

Run batch matches and save per-step logs:

```bash
python batch_simulation.py --count 3 --log-steps --log-dir batch_logs
```


### `parameter_tuner.py`
Tunes hyperparameters in `submission.py` by running simulations against opponent agents and optimizing for win rate.

#### Usage

```bash
python parameter_tuner.py [options]
```

#### Options

- `--opponents`: Comma-separated list of opponent agent files. Default: `agent1.py,agent2.py,agent3.py`
- `--matches`: Number of matches per opponent per candidate. Default: `2`
- `--trials`: Number of random candidate trials to run. Default: `20`
- `--seed`: Random seed for reproducibility. Default: `1234`
- `--params`: Comma-separated parameter names to tune. Default: curated list of key parameters
- `--save-config`: Path to save the best parameter set as JSON. Default: `best_submission_params.json`
- `--output-agent`: Path to write the tuned agent Python file. Default: `submission_tuned.py`
- `--dry-run`: Do not write output files

#### Examples

Run tuning with default settings (20 trials, 2 matches each):

```bash
python parameter_tuner.py
```

Tune specific parameters with more trials:

```bash
python parameter_tuner.py --params SAFE_NEUTRAL_MARGIN,ATTACK_COST_TURN_WEIGHT --trials 50 --matches 3
```

Tune against specific opponents and save results:

```bash
python parameter_tuner.py --opponents agent1.py,agent2.py --save-config tuned_params.json --output-agent tuned_agent.py
```

Perform a dry run to see what would be done without writing files:

```bash
python parameter_tuner.py --dry-run --trials 5
```


## Log output

When `--log-steps` is enabled, logs are written to files in the specified output directory.

Example log file names:

- `batch_logs/batch_run_test_vs_agent1_match_1_logs.txt`
- `batch_logs/batch_run_test_vs_agent2_match_2_logs.txt`

The log files contain a step-by-step summary of the replay, including each player’s status, reward, action, planet counts, fleet counts, and ship totals.
