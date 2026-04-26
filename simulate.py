import argparse
import os
import sys
from pathlib import Path
from kaggle_environments import make

VIZ_PATH = Path('/workspaces/wtrmrk-rm/vizar-orbit-data')


def _ensure_viz_path():
    if not VIZ_PATH.exists():
        raise FileNotFoundError(
            f"Visualizer dataset not found at {VIZ_PATH}. Install or attach the dataset to use HTML rendering."
        )
    if str(VIZ_PATH) not in sys.path:
        sys.path.append(str(VIZ_PATH))


def _summarize_replay(replay, team_names=None):
    replay_info = {
        'step_count': len(replay.get('steps', [])),
        'rewards': replay.get('rewards', []),
        'statuses': replay.get('statuses', []),
        'team_names': list(team_names) if team_names is not None else replay.get('info', {}).get('TeamNames', []),
    }

    if replay_info['team_names'] is None:
        replay_info['team_names'] = []

    if replay_info['rewards']:
        max_reward = max(replay_info['rewards'])
        winners = [i for i, r in enumerate(replay_info['rewards']) if r == max_reward]
        if len(winners) == 1:
            replay_info['winner'] = winners[0]
            replay_info['winner_text'] = f"{replay_info['team_names'][winners[0]] if winners[0] < len(replay_info['team_names']) else f'Player {winners[0]}'} wins!"
        else:
            replay_info['winner'] = winners
            replay_info['winner_text'] = 'Draw'
    else:
        replay_info['winner'] = None
        replay_info['winner_text'] = 'Unavailable'

    final_observation = None
    for step in reversed(replay.get('steps', [])):
        if isinstance(step, list):
            for entry in step:
                if isinstance(entry, dict) and 'observation' in entry:
                    final_observation = entry['observation']
                    break
        if final_observation is not None:
            break

    replay_info['final_observation'] = final_observation
    return replay_info


def _print_summary(summary):
    team_names = summary['team_names']
    print('\n=== Orbit Wars Run Summary ===')
    print(f"Final step count: {summary['step_count']}")
    if summary['rewards']:
        print(f"Rewards: {summary['rewards']}")
    if summary['statuses']:
        print(f"Statuses: {summary['statuses']}")
    print(f"Result: {summary['winner_text']}")

    final_observation = summary.get('final_observation')
    if final_observation is None:
        print('No final observation available for deeper summary.')
        print('=== End run summary ===\n')
        return

    planet_stats = {}
    fleet_stats = {}
    for planet in final_observation.get('planets', []):
        owner = planet[1]
        ships = planet[5]
        if owner >= 0:
            planet_stats.setdefault(owner, {'planets': 0, 'planet_ships': 0, 'production': 0})
            planet_stats[owner]['planets'] += 1
            planet_stats[owner]['planet_ships'] += ships
            planet_stats[owner]['production'] += planet[6]

    for fleet in final_observation.get('fleets', []):
        owner = fleet[1]
        ships = fleet[6]
        if owner >= 0:
            fleet_stats.setdefault(owner, {'fleets': 0, 'fleet_ships': 0})
            fleet_stats[owner]['fleets'] += 1
            fleet_stats[owner]['fleet_ships'] += ships

    print('\nFinal totals by player:')
    for i in range(max(len(team_names), len(summary['rewards']), len(summary['statuses']))):
        name = team_names[i] if i < len(team_names) else f'Player {i}'
        planet_count = planet_stats.get(i, {}).get('planets', 0)
        planet_ships = planet_stats.get(i, {}).get('planet_ships', 0)
        production = planet_stats.get(i, {}).get('production', 0)
        fleet_count = fleet_stats.get(i, {}).get('fleets', 0)
        fleet_ships = fleet_stats.get(i, {}).get('fleet_ships', 0)
        total_ships = planet_ships + fleet_ships
        print(
            f"  {name}: planets={planet_count}, fleets={fleet_count}, "
            f"planet_ships={planet_ships}, fleet_ships={fleet_ships}, total_ships={total_ships}, production={production}"
        )

    remaining_overage = final_observation.get('remainingOverageTime')
    if remaining_overage is not None:
        print(f"Remaining overage time: {remaining_overage}")
    print('=== End run summary ===\n')


def run_match(agent_a='test.py', agent_b='agent1.py', render_html=False, team_names=None, return_replay=False):
    env = make('orbit_wars', debug=True)
    env.run([agent_a, agent_b])
    replay = env.toJSON()
    if render_html:
        _ensure_viz_path()
        from orbit_wars.core.viz.embed import render
        render(env, team_names=team_names or [agent_a, agent_b])
    if return_replay:
        return replay
    return _summarize_replay(replay, team_names=team_names or [agent_a, agent_b])

def summarize_replay(replay, team_names=None):
    return _summarize_replay(replay, team_names=team_names)

def _format_action(action):
    if not action:
        return 'none'
    if isinstance(action, dict):
        return str(action)
    if isinstance(action, (list, tuple)):
        if len(action) == 3 and all(isinstance(x, (int, float)) for x in action):
            return f"[{action[0]}, {action[1]:.2f}, {action[2]}]"
        if all(isinstance(x, (list, tuple)) for x in action):
            return '; '.join(
                f"[{move[0]}, {move[1]:.2f}, {move[2]}]" for move in action if len(move) == 3
            )
    return str(action)

def _summarize_observation(observation):
    planet_counts = {}
    fleet_counts = {}
    total_planet_ships = {}
    total_fleet_ships = {}

    for planet in observation.get('planets', []):
        owner = planet[1]
        ships = planet[5]
        if owner >= 0:
            planet_counts[owner] = planet_counts.get(owner, 0) + 1
            total_planet_ships[owner] = total_planet_ships.get(owner, 0) + ships

    for fleet in observation.get('fleets', []):
        owner = fleet[1]
        ships = fleet[6]
        if owner >= 0:
            fleet_counts[owner] = fleet_counts.get(owner, 0) + 1
            total_fleet_ships[owner] = total_fleet_ships.get(owner, 0) + ships

    return {
        'planet_counts': planet_counts,
        'fleet_counts': fleet_counts,
        'planet_ships': total_planet_ships,
        'fleet_ships': total_fleet_ships,
    }

def _format_step_log(step_index, step, team_names):
    lines = [f"=== Step {step_index + 1} ==="]
    for player_index, entry in enumerate(step):
        name = team_names[player_index] if player_index < len(team_names) else f"Player {player_index}"
        status = entry.get('status')
        reward = entry.get('reward')
        action = _format_action(entry.get('action'))
        observation = entry.get('observation', {})
        summary = _summarize_observation(observation)
        planet_count = summary['planet_counts'].get(player_index, 0)
        fleet_count = summary['fleet_counts'].get(player_index, 0)
        planet_ships = summary['planet_ships'].get(player_index, 0)
        fleet_ships = summary['fleet_ships'].get(player_index, 0)
        total_ships = planet_ships + fleet_ships
        lines.append(
            f"{name} | status={status} | reward={reward} | action={action} | "
            f"planets={planet_count}, planet_ships={planet_ships} | "
            f"fleets={fleet_count}, fleet_ships={fleet_ships} | total_ships={total_ships}"
        )
        if fleet_count:
            fleets = [f for f in observation.get('fleets', []) if f[1] == player_index]
            fleets_sorted = sorted(fleets, key=lambda f: f[6], reverse=True)[:3]
            fleet_strings = [
                f"id={f[0]} size={f[6]} pos=({f[2]:.1f},{f[3]:.1f}) angle={f[4]:.2f}"
                for f in fleets_sorted
            ]
            lines.append(f"  Top fleets: {', '.join(fleet_strings)}")
    return '\n'.join(lines)

def get_replay_step_log(replay, team_names=None):
    if team_names is None:
        team_names = replay.get('info', {}).get('TeamNames', []) or []
    lines = [f"Logging {len(replay.get('steps', []))} replay steps...\n"]
    for index, step in enumerate(replay.get('steps', [])):
        lines.append(_format_step_log(index, step, team_names))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Run a single Orbit Wars simulation test match.')
    parser.add_argument('--agent', default='test.py', help='Path to the attacker agent file (default: test.py)')
    parser.add_argument('--opponent', default='agent1.py', help='Path to the opponent agent file (default: agent1.py)')
    parser.add_argument('--count', type=int, default=1, help='Number of matches to run (default: 1)')
    parser.add_argument('--render', action='store_true', help='Render the match in HTML after completion')
    parser.add_argument('--no-summary', action='store_true', help='Suppress summary output')
    parser.add_argument('--log-steps', action='store_true', help='Save per-step match logs to text files')
    parser.add_argument('--log-dir', default='batch_logs', help='Directory to write log files to')

    args = parser.parse_args()
    os.makedirs(args.log_dir, exist_ok=True)
    results = []
    for i in range(args.count):
        replay = run_match(
            agent_a=args.agent,
            agent_b=args.opponent,
            render_html=args.render,
            team_names=[args.agent, args.opponent],
            return_replay=True,
        )
        summary = summarize_replay(replay, team_names=[args.agent, args.opponent])
        results.append(summary)
        if not args.no_summary:
            print(f"\nMatch {i + 1}/{args.count}: {args.agent} vs {args.opponent}")
            _print_summary(summary)
        if args.log_steps:
            log_path = os.path.join(
                args.log_dir,
                f"batch_run_{os.path.splitext(os.path.basename(args.agent))[0]}_vs_{os.path.splitext(os.path.basename(args.opponent))[0]}_match_{i+1}_logs.txt"
            )
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(get_replay_step_log(replay, team_names=[args.agent, args.opponent]))
            print(f"Saved log to: {log_path}")

    if args.count > 1 and not args.no_summary:
        win_count = sum(1 for r in results if r['winner'] == 0)
        draw_count = sum(1 for r in results if isinstance(r['winner'], list) or r['winner'] is None)
        loss_count = sum(1 for r in results if r['winner'] == 1)
        print('=== Aggregated Results ===')
        print(f"Wins for {args.agent}: {win_count}")
        print(f"Losses for {args.agent}: {loss_count}")
        print(f"Draws/Undecided: {draw_count}")


if __name__ == '__main__':
    main()
