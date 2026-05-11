import math
import kaggle_environments.envs.orbit_wars.orbit_wars as ow
import numpy as np

fleet_trajectories = []
reinforcement_trajectories = []
moving_planets = []
planets_coords = {}
steps = 0

MAX_SPEED = 6.0
# TUNED FOR AGGRESSION: Lower minimums to attack more frequently and smaller fleets
MIN_SHIPS_MINE_ATTACK = 7  # was 10 - attack with smaller, faster forces
MIN_SHIPS_TARGET_COOP_ATTACK = 15  # was 20 - lower coop threshold
COOP_PLANET_CAP = 10  # was 8 - allow more planets attacking one target
COLLIDE_TICK_THOLD = 1

# SCORING: More aggressive production-seeking
FORMULA_DIST = 90  # was 100 - reward distance more (negative is good)
FORMULA_PROD_MULT = 18  # was 15 - aggressively seek production
FORMULA_ENEMY_BONUS_MULT = 12  # was 10 - capture enemy planets at higher priority
FORMULA_TOTAL_SHIPS_PERCENT = 0.6  # was 0.7 - less defensive


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
        - (1.8 * eta)  # was 2 - reward speed slightly
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


def update_fleet_trajectories(fleets):
    for f_t in fleet_trajectories[:]:
        found = False
        for f in fleets:
            if f.from_planet_id == f_t["mine"].id and abs(f.angle - f_t["angle"]) < 1e-3:
                found = True
                break

        if found:
            f_t["arrive_tick"] = max(0, f_t["arrive_tick"] - 1)

        if not found:
            fleet_trajectories.remove(f_t)


def update_reinforcement_trajectories(planets):
    planet_ids = {p.id for p in planets}

    for r_t in reinforcement_trajectories[:]:
        r_t["arrive_tick"] -= 1

        if r_t["arrive_tick"] <= 0:
            reinforcement_trajectories.remove(r_t)
            continue


def get_planet_trajectories(p, vel):
    planet_trajectories = []
    angle = math.atan2(p.y - 50, p.x - 50)
    r = math.sqrt((p.x - 50)**2 + (p.y - 50)**2)
    for tick in range(1, 61):  # max 60 ticks
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


def find_angle_to_moving_planet(p, t, ships, vel):
    fleet_speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, ships)) / math.log(1000)) ** 1.5
    planet_trajectories = get_planet_trajectories(t, vel)

    for tick, (tx, ty) in enumerate(planet_trajectories, start=1):
        dx = tx - p.x
        dy = ty - p.y
        dist_to_target = math.sqrt(dx**2 + dy**2) - p.radius

        travel_dist = fleet_speed * tick
        miss_dist = abs(travel_dist - dist_to_target)

        if miss_dist > t.radius:
            continue

        angle = math.atan2(dy, dx)

        if sun_collision(p, fleet_speed, angle):
            return None, None

        return angle, tick

    return None, None


def get_reinforcement_plans(mine, under_attack):
    reinforcement_plans = {}

    for p in mine:
        if p.id in under_attack:
            attacking_fleets = sorted(
                under_attack[p.id]["fleets"],
                key=lambda att: att["arrive_tick"]
            )

            incoming_reinforcements = sorted(
                [r for r in reinforcement_trajectories if r["target"].id == p.id],
                key=lambda r: r["arrive_tick"]
            )

            p_available_ships = p.ships
            previous_tick = 0
            r_idx = 0

            for att in attacking_fleets:
                deficit = att["ships"] - p_available_ships
                if deficit <= 0:
                    p_available_ships -= att["ships"]
                    continue

                while r_idx < len(incoming_reinforcements):
                    r = incoming_reinforcements[r_idx]

                    if r["arrive_tick"] <= att["arrive_tick"]:
                        p_available_ships += r["total_ships"]
                        r_idx += 1
                        continue

                    break

                if deficit > 0:
                    reinforcement_plans[p.id] = {
                        "ships_needed": deficit,
                        "needed_by_tick": att["arrive_tick"]
                    }
                    break

                p_available_ships -= att["ships"]

    return reinforcement_plans


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
    update_fleet_trajectories(lobs.get("fleets", []))
    update_reinforcement_trajectories(lobs.get("planets", []))
    comet_planet_ids = obs.get("comet_planet_ids", [])
    under_attack = get_planets_under_attack(lobs.get("mine", []), lobs.get("fleets", []), lobs.get("player", -2), obs.angular_velocity)
    exhausted_planets_id = set()

    if not lobs.get("targets", []):
        return []

    reinforcement_plans = get_reinforcement_plans(lobs.get("mine", []), under_attack)
    for p, plan in reinforcement_plans.items():
        already_reinforced = any(
            r["target"].id == p and r["arrive_tick"] >= 0
            for r in reinforcement_trajectories
        )

        if already_reinforced:
            continue

        ships_needed = plan["ships_needed"]
        needed_by_tick = plan["needed_by_tick"]
        nearest_planets = get_closest_planets_to_target(lobs.get("mine", []), p)

        for row in nearest_planets:
            p_np, _ = row

            if p_np.id == p or p_np.id in exhausted_planets_id:
                continue

            p_np_available_ships = p_np.ships

            reserved_reinforcement_ships = sum(
                r["total_ships"]
                for r in reinforcement_trajectories
                if r["mine"].id == p_np.id
            )

            p_np_available_ships -= reserved_reinforcement_ships

            if p_np.id in under_attack:
                p_np_under_attack_ships = under_attack.get(p_np.id, {}).get("total_incoming", 0)
                p_np_available_ships = max(0, p_np_available_ships - p_np_under_attack_ships)

            sent_reinforcements = max(MIN_SHIPS_MINE_ATTACK, ships_needed)

            if p_np_available_ships < sent_reinforcements:
                continue
            angle_np = None
            arrive_tick = None
            if p.id not in moving_planets:
                angle_np = calculate_angle(p_np, p)

            else:
                angle_np, arrive_tick = find_angle_to_moving_planet(p_np, p, sent_reinforcements, obs.angular_velocity)

            if angle_np is None or arrive_tick is None:
                continue

            moves.append([p_np.id, angle_np, sent_reinforcements])
            exhausted_planets_id.add(p_np.id)
            reinforcement_trajectories.append({
                "mine": p_np,
                "target": p,
                "angle": angle_np,
                "total_ships": sent_reinforcements,
                "arrive_tick": arrive_tick
            })
            break

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

        for m, t, s in candidate_targets[:3]:
            m_available_ships = m.ships

            if m.id in under_attack:
                m_under_attack_ships = under_attack.get(m.id, {}).get("total_incoming", 0)
                m_available_ships = max(0, m_available_ships - m_under_attack_ships)

            if m_available_ships < MIN_SHIPS_MINE_ATTACK:
                continue

            nearest_planets = get_closest_planets_to_target(lobs.get("mine", []), t)
            safe_nearest_planets = []
            for p, dist in nearest_planets:
                if p.id not in exhausted_planets_id and p.ships >= MIN_SHIPS_MINE_ATTACK:
                    safe_nearest_planets.append((p, dist))

            if not safe_nearest_planets:
                continue

            owned_count = len(lobs.get("mine", []))
            total_count = len(lobs.get("planets", []))

            en_route = 0
            if fleet_trajectories:
                for f_t in fleet_trajectories:
                    if f_t["target"].id == t.id:
                        en_route += f_t.get("ships", 0)

            needed_now = t.ships + 1
            if t.owner != -1:
                needed_now += t.production * 2

            enemy_competing = get_max_enemy_fleet_to_target(t, lobs.get("fleets", []), lobs.get("player", -2), obs.angular_velocity)
            if enemy_competing > 0:
                needed_now += enemy_competing * 1.5

            if owned_count < total_count * 0.75:
                needed_now += 3

            base_ships = max(MIN_SHIPS_MINE_ATTACK, needed_now - en_route)

            extra_ships = 0
            fleet_speed = 0
            angle = None
            arrive_tick = None

            contributing = 0
            for p, dist in safe_nearest_planets:
                if contributing >= COOP_PLANET_CAP:
                    break

                p_available_ships = p.ships

                reserved = sum(
                    r["total_ships"]
                    for r in reinforcement_trajectories
                    if r["mine"].id == p.id
                )

                p_available_ships -= reserved

                if p.id in under_attack:
                    p_under_attack_ships = under_attack.get(p.id, {}).get("total_incoming", 0)
                    p_available_ships = max(0, p_available_ships - p_under_attack_ships)

                p_available_ships = max(0, p_available_ships - 2)

                ships_to_send = 0
                if extra_ships > 0:
                    ships_to_send = min(p_available_ships, extra_ships)
                else:
                    if base_ships <= p_available_ships:
                        if p.id == m.id:
                            ships_to_send = base_ships
                        else:
                            ships_to_send = max(MIN_SHIPS_TARGET_COOP_ATTACK, base_ships // (COOP_PLANET_CAP - contributing))
                    else:
                        ships_to_send = p_available_ships

                if ships_to_send < MIN_SHIPS_MINE_ATTACK:
                    continue

                angle = calculate_angle(p, t)

                if t.id not in moving_planets:
                    pass
                else:
                    angle_result = find_angle_to_moving_planet(p, t, ships_to_send, obs.angular_velocity)
                    if angle_result is None:
                        angle = None
                    else:
                        angle, arrive_tick = angle_result

                if angle is None:
                    continue

                fleet_speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, ships_to_send)) / math.log(1000)) ** 1.5

                if sun_collision(p, fleet_speed, angle):
                    continue

                moves.append([p.id, angle, ships_to_send])
                exhausted_planets_id.add(p.id)

                extra_ships -= ships_to_send
                extra_ships += p_available_ships - ships_to_send
                contributing += 1

    return moves


__all__ = ['agent']
