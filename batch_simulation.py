import argparse
import os
from simulate import get_replay_step_log, run_match, summarize_replay


def parse_opponents(opponents_str):
    if not opponents_str:
        return ['agent1.py', 'agent2.py', 'agent3.py']
    return [opp.strip() for opp in opponents_str.split(',') if opp.strip()]


def print_run_summary(agent, opponent, results):
    wins = sum(1 for r in results if r['winner'] == 0)
    losses = sum(1 for r in results if r['winner'] == 1)
    draws = sum(1 for r in results if isinstance(r['winner'], list) or r['winner'] is None)
    print(f"\n== Results vs {opponent} ({len(results)} matches) ==")
    print(f"  {agent} wins: {wins}")
    print(f"  {opponent} wins: {losses}")
    print(f"  Draws/Undecided: {draws}")
    for idx, result in enumerate(results, start=1):
        winner_text = result['winner_text']
        rewards = result['rewards']
        statuses = result['statuses']
        print(f"  Match {idx}: {winner_text} | rewards={rewards} | statuses={statuses}")


def main():
    parser = argparse.ArgumentParser(description='Batch run Orbit Wars 1v1 simulations for test.py against opponent agents.')
    parser.add_argument('--agent', default='test.py', help='Path to the first agent (default: test.py)')
    parser.add_argument('--opponents', default='agent1.py,agent2.py,agent3.py', help='Comma-separated list of opponent agent files')
    parser.add_argument('--count', type=int, default=5, help='Number of matches to run against each opponent')
    parser.add_argument('--render', action='store_true', help='Render each match in HTML (not recommended for batch runs)')
    parser.add_argument('--log-steps', action='store_true', help='Save per-step match logs to text files')
    parser.add_argument('--log-dir', default='batch_logs', help='Directory to write log files to')

    args = parser.parse_args()
    opponents = parse_opponents(args.opponents)
    if args.log_steps:
        os.makedirs(args.log_dir, exist_ok=True)
    agent = args.agent

    print(f"Running batch simulation: {agent} vs {opponents} ({args.count} matches each)")
    for opponent in opponents:
        if not os.path.exists(opponent):
            print(f"Warning: opponent file not found: {opponent}. Skipping.")
            continue
        results = []
        for i in range(args.count):
            print(f"\nRunning {agent} vs {opponent}: match {i+1}/{args.count}")
            if args.log_steps:
                replay = run_match(
                    agent_a=agent,
                    agent_b=opponent,
                    render_html=args.render,
                    team_names=[agent, opponent],
                    return_replay=True,
                )
                result = summarize_replay(replay, team_names=[agent, opponent])
                log_path = os.path.join(
                    args.log_dir,
                    f"batch_run_{os.path.splitext(os.path.basename(agent))[0]}_vs_{os.path.splitext(os.path.basename(opponent))[0]}_match_{i+1}_logs.txt",
                )
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write(get_replay_step_log(replay, team_names=[agent, opponent]))
                print(f"Saved log to: {log_path}")
            else:
                result = run_match(agent_a=agent, agent_b=opponent, render_html=args.render, team_names=[agent, opponent])
            results.append(result)
        print_run_summary(agent, opponent, results)


if __name__ == '__main__':
    main()