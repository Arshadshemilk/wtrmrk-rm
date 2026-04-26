import json
import base64
from pathlib import Path

def _format_player_name(index, team_names):
    if team_names and index < len(team_names):
        return team_names[index]
    return f"Player {index}"


def _summarize_replay(replay_data, team_names=None):
    if team_names is None:
        team_names = replay_data.get("info", {}).get("TeamNames", [])

    rewards = replay_data.get("rewards", [])
    statuses = replay_data.get("statuses", [])
    step_count = len(replay_data.get("steps", []))
    num_players = max(len(rewards), len(statuses), len(team_names))
    names = [_format_player_name(i, team_names) for i in range(num_players)]

    winners = []
    if rewards:
        max_reward = max(rewards)
        winners = [i for i, r in enumerate(rewards) if r == max_reward]
        winner_text = (
            "Draw!" if len(winners) != 1 else f"{names[winners[0]]} wins!"
        )
    else:
        winner_text = "Winner unavailable"

    print("\n=== Orbit Wars Simulation Summary ===")
    print(f"Final step count: {step_count}")
    if rewards:
        print(f"Rewards: {rewards}")
    if statuses:
        print(f"Statuses: {statuses}")
    print(f"Result: {winner_text}")

    final_observation = None
    for step in reversed(replay_data.get("steps", [])):
        if isinstance(step, list):
            for entry in step:
                if isinstance(entry, dict) and "observation" in entry:
                    final_observation = entry["observation"]
                    break
        if final_observation is not None:
            break

    if final_observation is None:
        print("No final observation available for deeper summary.")
        return

    planets = final_observation.get("planets", [])
    fleets = final_observation.get("fleets", [])

    planet_stats = {}
    fleet_stats = {}
    for planet in planets:
        owner = planet[1]
        ships = planet[5]
        if owner >= 0:
            planet_stats.setdefault(owner, {"planets": 0, "planet_ships": 0, "production": 0})
            planet_stats[owner]["planets"] += 1
            planet_stats[owner]["planet_ships"] += ships
            planet_stats[owner]["production"] += planet[6]

    for fleet in fleets:
        owner = fleet[1]
        ships = fleet[6]
        if owner >= 0:
            fleet_stats.setdefault(owner, {"fleets": 0, "fleet_ships": 0})
            fleet_stats[owner]["fleets"] += 1
            fleet_stats[owner]["fleet_ships"] += ships

    print("\nFinal totals by player:")
    for i in range(num_players):
        label = names[i]
        planets_owned = planet_stats.get(i, {}).get("planets", 0)
        planet_ships = planet_stats.get(i, {}).get("planet_ships", 0)
        production = planet_stats.get(i, {}).get("production", 0)
        fleets_owned = fleet_stats.get(i, {}).get("fleets", 0)
        fleet_ships = fleet_stats.get(i, {}).get("fleet_ships", 0)
        total_ships = planet_ships + fleet_ships
        print(
            f"  {label}: planets={planets_owned}, fleets={fleets_owned}, "
            f"planet_ships={planet_ships}, fleet_ships={fleet_ships}, total_ships={total_ships}, "
            f"production={production}"
        )

    remaining_overage = final_observation.get("remainingOverageTime")
    if remaining_overage is not None:
        print(f"Remaining overage time: {remaining_overage}")
    print("=== End simulation summary ===\n")


def render(env_or_json, team_names=None):
    """
    Renders an Orbit Wars replay using the bundled visualizer.
    This works similarly to kaggle_environments env.render(mode='ipython').
    
    Args:
        env_or_json: Either a kaggle_environments.Environment instance, 
                     or a dictionary representing the JSON replay.
        team_names: Optional list of strings to display as player names.
    """
    from IPython.display import HTML, display
    import uuid
    
    if isinstance(env_or_json, dict):
        replay_data = env_or_json
    else:
        # Assume it's an Environment object
        replay_data = env_or_json.toJSON()
    _summarize_replay(replay_data, team_names)
        
    # Inject custom team names if provided
    if team_names is not None:
        if "info" not in replay_data:
            replay_data["info"] = {}
        replay_data["info"]["TeamNames"] = team_names
        
    viz_dir = Path(__file__).parent.parent.parent.parent / "viz"
    dist_dir = viz_dir / "dist"
    assets_dir = dist_dir / "assets"
    
    if not dist_dir.exists():
        display(HTML("<div style='color:red'>Visualizer not built. Please run 'npm run build' in the 'viz' directory.</div>"))
        return
        
    # Find built JS and CSS
    js_files = list(assets_dir.glob("index-*.js"))
    css_files = list(assets_dir.glob("index-*.css"))
    
    if not js_files or not css_files:
        display(HTML("<div style='color:red'>Visualizer assets not found.</div>"))
        return
        
    js_content = js_files[0].read_text(encoding="utf-8")
    css_content = css_files[0].read_text(encoding="utf-8")
    
    # Base64 encode assets to safely embed them without worrying about quotes/backticks
    js_b64 = base64.b64encode(js_content.encode('utf-8')).decode('utf-8')
    css_b64 = base64.b64encode(css_content.encode('utf-8')).decode('utf-8')
    
    replay_json_str = json.dumps(replay_data)
    app_id = f"orbit-wars-viz-{uuid.uuid4().hex[:8]}"
    
    html_template = f"""
    <div id="orbit-wars-viz-wrapper-{app_id}" class="orbit-wars-viz-wrapper" 
         style="width: 100%; height: 800px; border: 1px solid #333; overflow: hidden; background: #050510; position: relative; margin: 10px 0;">
        <div id="{app_id}" style="width: 100%; height: 100%;"></div>
        
        <script>
            (function() {{
                const APP_ID = "{app_id}";
                const REPLAY_DATA = {replay_json_str};
                
                window._mountOrbitWars = window._mountOrbitWars || ((appId, data, jsB64, cssB64) => {{
                    const decode = (b64) => decodeURIComponent(escape(window.atob(b64)));
                    
                    if (!window._orbitWarsAssetsInjected) {{
                        const style = document.createElement('style');
                        style.textContent = decode(cssB64) + `
                            .orbit-wars-viz-wrapper .sidebar {{ display: none !important; }}
                            .orbit-wars-viz-wrapper .renderer-container {{ padding-bottom: 50px !important; }}
                        `;
                        document.head.appendChild(style);
                        
                        const script = document.createElement('script');
                        script.type = 'module';
                        script.textContent = decode(jsB64);
                        document.head.appendChild(script);
                        window._orbitWarsAssetsInjected = true;
                    }}

                    const tryMount = () => {{
                        if (window.mountOrbitWarsVisualizer) {{
                            window.mountOrbitWarsVisualizer(data, appId);
                        }} else {{
                            setTimeout(tryMount, 50);
                        }}
                    }};
                    tryMount();
                }});

                window._mountOrbitWars(APP_ID, REPLAY_DATA, "{js_b64}", "{css_b64}");
            }})();
        </script>
    </div>
    """
    
    display(HTML(html_template))
