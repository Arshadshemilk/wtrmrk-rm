import argparse
import concurrent.futures
import json
import os
import random
import re
import shutil
import tempfile
from pathlib import Path

from simulate import run_match

SUBMISSION_PATH = Path('submission.py')
DEFAULT_OPPONENTS = ['agent1.py', 'agent2.py', 'agent3.py']

# Provide a curated subset of parameters with safe tune ranges.
DEFAULT_PARAM_RANGES = {
    'SAFE_NEUTRAL_MARGIN': (1, 4, 'int'),
    'CONTESTED_NEUTRAL_MARGIN': (1, 4, 'int'),
    'ATTACK_COST_TURN_WEIGHT': (0.2, 0.8, 'float'),
    'SNIPE_COST_TURN_WEIGHT': (0.2, 0.8, 'float'),
    'INDIRECT_VALUE_SCALE': (0.05, 0.4, 'float'),
    'STATIC_NEUTRAL_VALUE_MULT': (1.0, 2.5, 'float'),
    'SAFE_NEUTRAL_VALUE_MULT': (0.8, 1.8, 'float'),
    'CONTESTED_NEUTRAL_VALUE_MULT': (0.4, 1.1, 'float'),
    'SWARM_VALUE_MULT': (0.8, 1.4, 'float'),
    'REINFORCE_VALUE_MULT': (1.0, 1.6, 'float'),
    'CRASH_EXPLOIT_VALUE_MULT': (1.0, 1.4, 'float'),
    'EXPOSED_PLANET_VALUE_MULT': (1.2, 2.5, 'float'),
    'NEUTRAL_MARGIN_BASE': (1, 5, 'int'),
    'HOSTILE_MARGIN_BASE': (2, 8, 'int'),
    'CONTESTED_TARGET_MARGIN': (2, 8, 'int'),
    'STATIC_TARGET_MARGIN': (3, 8, 'int'),
    'LONG_TRAVEL_MARGIN_START': (12, 24, 'int'),
    'FOLLOWUP_MIN_SHIPS': (4, 16, 'int'),
    'REAR_SOURCE_MIN_SHIPS': (10, 24, 'int'),
    'REAR_SEND_RATIO_FOUR_PLAYER': (0.55, 0.85, 'float'),
    'GANG_UP_VALUE_MULT': (1.0, 1.8, 'float'),
    'REINFORCE_SAFETY_MARGIN': (1, 4, 'int'),
}

CONSTANT_PATTERN = re.compile(r'^(?P<name>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<value>.+)$')


def load_submission_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def parse_defaults(text):
    defaults = {}
    for line in text.splitlines():
        match = CONSTANT_PATTERN.match(line)
        if not match:
            continue
        name = match.group('name')
        value_text = match.group('value').strip()
        if value_text.endswith('#'):
            value_text = value_text.split('#', 1)[0].strip()
        try:
            value = eval(value_text, {})
        except Exception:
            continue
        if isinstance(value, (int, float, bool)):
            defaults[name] = value
    return defaults


def format_value(value, value_type):
    if value_type == 'int':
        return str(int(value))
    if value_type == 'float':
        return repr(float(value))
    if value_type == 'bool':
        return 'True' if value else 'False'
    return str(value)


def render_candidate_text(base_text, candidate):
    edited_text = base_text
    for name, value in candidate.items():
        pattern = re.compile(rf'^(?P<lhs>{re.escape(name)}\s*=\s*).+$', re.MULTILINE)
        new_line = f"{name} = {value!r}"
        if pattern.search(edited_text):
            edited_text = pattern.sub(new_line, edited_text)
        else:
            raise ValueError(f'Parameter {name} not found in submission.py')
    return edited_text


def build_candidate_file(base_text, candidate, workspace):
    candidate_path = workspace / f'submission_candidate_{random.randint(100000, 999999)}.py'
    candidate_text = render_candidate_text(base_text, candidate)
    with open(candidate_path, 'w', encoding='utf-8') as f:
        f.write(candidate_text)
    return candidate_path


def random_value(range_tuple):
    lo, hi, value_type = range_tuple
    if value_type == 'int':
        return random.randint(int(lo), int(hi))
    if value_type == 'float':
        return random.uniform(float(lo), float(hi))
    if value_type == 'bool':
        return random.choice([True, False])
    raise ValueError(f'Unsupported parameter type: {value_type}')


def run_match_task(agent_path, opponent):
    summary = run_match(agent_a=agent_path, agent_b=opponent)
    return opponent, summary


def sample_candidate(param_ranges):
    return {name: random_value(settings) for name, settings in param_ranges.items()}


def score_match(summary):
    winner = summary.get('winner')
    if winner == 0:
        return 100
    if winner == 1:
        return -100
    return -10


def evaluate_candidate(candidate, opponents, matches_per_opponent, base_text, workers=1):
    with tempfile.TemporaryDirectory(prefix='param-tuner-') as tmp_dir:
        candidate_file = build_candidate_file(base_text, candidate, Path(tmp_dir))
        tasks = [
            (str(candidate_file), opponent)
            for opponent in opponents
            for _ in range(matches_per_opponent)
        ]
        total_score = 0
        results = []
        if workers == 1:
            for agent_path, opponent in tasks:
                _, summary = run_match_task(agent_path, opponent)
                score = score_match(summary)
                total_score += score
                results.append({'opponent': opponent, 'summary': summary, 'score': score})
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
                for opponent, summary in executor.map(lambda args: run_match_task(*args), tasks):
                    score = score_match(summary)
                    total_score += score
                    results.append({'opponent': opponent, 'summary': summary, 'score': score})
        return total_score, results


def improve_candidate(base_candidate, param_ranges, opponents, matches_per_opponent, base_text, workers=1, iterations=50):
    best_candidate = dict(base_candidate)
    best_score, _ = evaluate_candidate(best_candidate, opponents, matches_per_opponent, base_text, workers=workers)
    for _ in range(iterations):
        neighbor = dict(best_candidate)
        key = random.choice(list(param_ranges.keys()))
        lo, hi, value_type = param_ranges[key]
        current = neighbor[key]
        if value_type == 'int':
            step = max(1, int((hi - lo) * 0.15))
            neighbor[key] = max(lo, min(hi, current + random.choice([-step, step, step * 2, -step * 2])))
        else:
            step = (hi - lo) * 0.12
            neighbor[key] = max(lo, min(hi, current + random.uniform(-step, step)))
        score, _ = evaluate_candidate(neighbor, opponents, matches_per_opponent, base_text, workers=workers)
        if score > best_score:
            best_score, best_candidate = score, neighbor
    return best_score, best_candidate


def save_config(candidate, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(candidate, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Tune submission.py hyperparameters against local opponent agents.')
    parser.add_argument('--opponents', default=','.join(DEFAULT_OPPONENTS), help='Comma-separated opponent agent files')
    parser.add_argument('--matches', type=int, default=2, help='Matches per opponent per candidate')
    parser.add_argument('--trials', type=int, default=20, help='Random candidate trials to run')
    parser.add_argument('--seed', type=int, default=1234, help='Random seed for reproducibility')
    parser.add_argument('--params', default=','.join(DEFAULT_PARAM_RANGES.keys()), help='Comma-separated parameter names to tune')
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1), help='Number of parallel worker processes to use')
    parser.add_argument('--save-config', default='best_submission_params.json', help='Write the best parameter set to JSON')
    parser.add_argument('--output-agent', default='submission_tuned.py', help='Write a tuned agent Python file with the best parameters')
    parser.add_argument('--dry-run', action='store_true', help='Do not write output files')
    args = parser.parse_args()

    random.seed(args.seed)
    opponents = [opp.strip() for opp in args.opponents.split(',') if opp.strip()]
    if not opponents:
        opponents = list(DEFAULT_OPPONENTS)

    base_text = load_submission_text(SUBMISSION_PATH)
    all_defaults = parse_defaults(base_text)
    param_names = [name.strip() for name in args.params.split(',') if name.strip()]
    param_ranges = {}
    for name in param_names:
        if name in DEFAULT_PARAM_RANGES:
            param_ranges[name] = DEFAULT_PARAM_RANGES[name]
        elif name in all_defaults:
            default = all_defaults[name]
            if isinstance(default, bool):
                param_ranges[name] = (0, 1, 'bool')
            elif isinstance(default, int):
                lo = max(1, int(default * 0.5))
                hi = max(lo + 1, int(default * 1.5))
                param_ranges[name] = (lo, hi, 'int')
            else:
                lo = 0.0 if default <= 0 else default * 0.5
                hi = default * 1.5 if default > 0 else 1.0
                param_ranges[name] = (lo, hi, 'float')
        else:
            raise ValueError(f'Unknown parameter: {name}')

    print(f'Tuning parameters: {sorted(param_ranges.keys())}')
    print(f'Opponents: {opponents}')
    print(f'Matches per opponent: {args.matches}')
    print(f'Parallel workers: {args.workers}')

    best_candidate = None
    best_score = float('-inf')
    for trial in range(1, args.trials + 1):
        candidate = sample_candidate(param_ranges)
        score, results = evaluate_candidate(candidate, opponents, args.matches, base_text, workers=args.workers)
        print(f'Trial {trial}/{args.trials}: score={score} candidate={candidate}')
        if score > best_score:
            best_score = score
            best_candidate = candidate
            print(f'  New best score: {best_score}')

    print(f'Random search best score: {best_score}')
    print(f'Best candidate from random search: {best_candidate}')

    improved_score, improved_candidate = improve_candidate(
        best_candidate, param_ranges, opponents, args.matches, base_text, iterations=max(5, args.trials // 4)
    )
    print(f'Local search improved score: {improved_score}')
    print(f'Improved candidate: {improved_candidate}')

    if not args.dry_run:
        save_config(improved_candidate, args.save_config)
        candidate_text = render_candidate_text(base_text, improved_candidate)
        with open(args.output_agent, 'w', encoding='utf-8') as f:
            f.write(candidate_text)
        print(f'Wrote tuned parameters to {args.save_config} and tuned agent to {args.output_agent}')
    else:
        print('Dry run complete. No files were written.')


if __name__ == '__main__':
    main()
