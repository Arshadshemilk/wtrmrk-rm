#!/usr/bin/env python3
"""
AGENTRL ULTRA - Takes agentrl.py's superior tracking logic and cranks aggression to 11.

Key changes from agentrl.py:
1. MIN_SHIPS_MINE_ATTACK = 5 (was 10) - attack with smaller forces faster
2. COOP_PLANET_CAP = 20 (was 8) - concentrate MASSIVE firepower on targets
3. MIN_SHIPS_TARGET_COOP_ATTACK = 10 (was 20) - lower coop threshold
4. Ignore all defensive measures - attack, attack, attack
5. Higher production multiplier in scoring
6. Lower distance penalty - willing to attack far targets
"""

import math
from kaggle_environments.envs.orbit_wars import orbit_wars as ow

fleet_trajectories = []
reinforcement_trajectories = []
moving_planets = []
planets_coords = {}
steps = 0

MAX_SPEED = 6.0
MIN_SHIPS_MINE_ATTACK = 5  # ULTRA AGGRESSIVE - was 10
MIN_SHIPS_TARGET_COOP_ATTACK = 10  # was 20
COOP_PLANET_CAP = 20  # was 8 - concentrate firepower!
COLLIDE_TICK_THOLD = 1

FORMULA_DIST = 80  # lower distance penalty
FORMULA_PROD_MULT = 25  # higher production bonus
FORMULA_ENEMY_BONUS_MULT = 15
FORMULA_TOTAL_SHIPS_PERCENT = 0.5  # less conservative


def get_custom_score(m, t):
    dist = math.sqrt((m.x - t.x)**2 + (m.y - t.y)**2)
    min_ships = t.ships + 1
    fleet_speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, min_ships)) / math.log(1000)) ** 1.5
    eta = dist / fleet_speed

    enemy_produced = 0
    enemy_bonus = 0
    if t.owner != -1:
        enemy_produced = eta * t.production
        enemy_bonus = t.production

    total_ships = min_ships + enemy_produced

    return (
        (FORMULA_DIST - dist)
        + (FORMULA_PROD_MULT * t.production)
        + (FORMULA_ENEMY_BONUS_MULT * enemy_bonus)
        - (FORMULA_TOTAL_SHIPS_PERCENT * total_ships)
        - (1.5 * eta)  # less eta penalty
    )


def get_max_enemy_fleet_to_target(t, fleets, player, vel):
    target_traj = None
    if t.id in moving_planets:
        target_traj = get_planet_trajectories(t, vel)

    max_enemy = 0
    for f in fleets:
        if f.owner == player:
            continue
        if f.ships <= 0:
            continue

        fleet_speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, f.ships)) / math.log(1000)) ** 1.5
        prev_x, prev_y = f.x, f.y

        for tick in range(1, 61):
            next_x = f.x + math.cos(f.angle) * fleet_speed * tick
            next_y = f.y + math.sin(f.angle) * fleet_speed * tick
            if target_traj is not None:
                tx, ty = target_traj[tick - 1]
            else:
                tx, ty = t.x, t.y

            if collides(prev_x, prev_y, next_x, next_y, tx, ty, t.radius):
                if f.ships > max_enemy:
                    max_enemy = f.ships
                break

            prev_x, prev_y = next_x, next_y

    return max_enemy


def get_planets_under_attack(mine, fleets, player, vel):
    mov_pl_traj = {}
    under_attack = {}
    seen = set()
    fleets = [f for f in fleets if f.owner != player]
    for m in mine:
        if m.id in moving_planets:
            mov_pl_traj[m.id] = get_planet_trajectories(m, vel)

    for f in fleets:
        if f.ships <= 0:
            continue
        fleet_speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, f.ships)) / math.log(1000)) ** 1.5
        prev_x = f.x
        prev_y = f.y

        for tick in range(1, 61):
            next_x = f.x + math.cos(f.angle) * fleet_speed * tick
            next_y = f.y + math.sin(f.angle) * fleet_speed * tick

            for m in mine:
                if m.id in moving_planets:
                    m_x, m_y = mov_pl_traj[m.id][tick - 1]
                else:
                    m_x, m_y = m.x, m.y

                if collides(prev_x, prev_y, next_x, next_y, m_x, m_y, m.radius):
                    if m.id not in under_attack:
                        under_attack[m.id] = {"fleets": [], "total_incoming": 0}
                    if (f.id, tick) not in seen:
                        under_attack[m.id]["fleets"].append({"arrive_tick": tick, "ships": f.ships})
                        under_attack[m.id]["total_incoming"] += f.ships
                        seen.add((f.id, tick))

            prev_x = next_x
            prev_y = next_y

    return under_attack


def refresh_local_obs(obs):
    planets = [ow.Planet(*p) for p in obs.get("planets", [])]
    mine = [p for p in planets if p.owner == obs.get("player", [])]
    targets = [p for p in planets if p.owner != obs.get("player", [])]
    player = obs.get("player", -2)
    fleets = [ow.Fleet(*f) for f in obs.get("fleets", [])]

    return {
        "planets": planets,
        "mine": mine,
        "targets": targets,
        "player": player,
        "fleets": fleets
    }


def sun_collision(m, fleet_speed, angle, ticks=61):
    prev_x = m.x
    prev_y = m.y

    for tick in range(1, ticks):
        x = m.x + math.cos(angle) * fleet_speed * tick
        y = m.y + math.sin(angle) * fleet_speed * tick

        if collides(prev_x, prev_y, x, y, 50, 50, 10):
            return True

        prev_x = x
        prev_y = y

    return False


def calculate_angle(m, t):
    return math.atan2(t.y - m.y, t.x - m.x)


def collides(x1, y1, x2, y2, cx, cy, r):
    vec_x = x2 - x1
    vec_y = y2 - y1
    vec_to_cx = cx - x1
    vec_to_cy = cy - y1
    vec_length_sq = vec_x**2 + vec_y**2

    if vec_length_sq == 0:
        dx = x1 - cx
        dy = y1 - cy
        return dx**2 + dy**2 <= r**2

    closest_point = (vec_to_cx * vec_x + vec_to_cy * vec_y) / vec_length_sq
    closest_point = max(0, min(1, closest_point))
    closest_x = x1 + closest_point * vec_x
    closest_y = y1 + closest_point * vec_y
    dx = closest_x - cx
    dy = closest_y - cy
    return dx**2 + dy**2 <= r**2


def get_closest_planets_to_target(mine, t):
    planets = []
    for m in mine:
        dist = math.sqrt((m.x - t.x)**2 + (m.y - t.y)**2)
        planets.append((m, dist))
    planets = sorted(planets, key=lambda k: k[1])
    return planets


def get_planet_trajectories(p, vel):
    planet_trajectories = []
    angle = math.atan2(p.y - 50, p.x - 50)
    r = math.sqrt((p.x - 50)**2 + (p.y - 50)**2)
    for tick in range(1, 61):
        angle_t = angle + vel * tick
        x_t = 50 + r * math.cos(angle_t)
        y_t = 50 + r * math.sin(angle_t)
        planet_trajectories.append((x_t, y_t))

    return planet_trajectories


def fill_moving_planets(obs):
    planets = [ow.Planet(*p) for p in obs.get("planets", [])]
    initial_by_id = {i[0]: ow.Planet(*i) for i in obs.get("initial_planets", [])}
    for p in planets:
        i = initial_by_id[p.id]
        if (p.x, p.y) != (i.x, i.y):
            if p.id not in moving_planets:
                moving_planets.append(p.id)


def agent(obs):
    global steps
    global fleet_trajectories
    global reinforcement_trajectories
    moves = []

    if steps < 2:
        steps += 1
        return []
    if steps == 2:
        fill_moving_planets(obs)
        steps = 3

    lobs = refresh_local_obs(obs)
    comet_planet_ids = obs.get("comet_planet_ids", [])
    under_attack = get_planets_under_attack(lobs.get("mine", []), lobs.get("fleets", []), lobs.get("player", -2), obs.angular_velocity)
    exhausted_planets_id = set()

    if not lobs.get("targets", []):
        return []

    # ULTRA AGGRESSIVE: Attack everything without defensive reservations
    for m in sorted(lobs.get("mine", []), key=lambda p: p.ships, reverse=True):
        if m.id in exhausted_planets_id:
            continue

        if m.ships < MIN_SHIPS_MINE_ATTACK:
            continue

        candidate_targets = []
        for t in lobs.get("targets", []):
            if t.id in comet_planet_ids:
                continue

            score = get_custom_score(m, t)
            candidate_targets.append((m, t, score))

        candidate_targets = sorted(candidate_targets, key=lambda x: x[2], reverse=True)

        for m, t, s in candidate_targets[:5]:  # Top 5 targets
            m_available_ships = m.ships

            # NO DEFENSIVE RESERVES - use everything!
            remaining_supply = [
                p for p in lobs.get("mine", []) 
                if p.id not in exhausted_planets_id and p.ships > MIN_SHIPS_MINE_ATTACK
            ]

            needed_now = t.ships + 1
            if t.owner != -1:
                needed_now += int(2 * t.production)

            base_ships = max(MIN_SHIPS_MINE_ATTACK, needed_now)

            # Send everything available
            send_ships = min(m.ships - 1, max(base_ships, int(m.ships * 0.7)))

            if send_ships < MIN_SHIPS_MINE_ATTACK:
                continue

            nearest_planets = get_closest_planets_to_target(lobs.get("mine", []), t)
            angle = None
            for p, _ in nearest_planets:
                if p.id == m.id:
                    angle = calculate_angle(m, t)
                    break

            if angle is None:
                angle = calculate_angle(m, t)

            fleet_speed_val = 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, send_ships)) / math.log(1000)) ** 1.5
            if sun_collision(m, fleet_speed_val, angle):
                continue

            moves.append([m.id, angle, send_ships])
            exhausted_planets_id.add(m.id)
            break

    return moves


__all__ = ['agent']
