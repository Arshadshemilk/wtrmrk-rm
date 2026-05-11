"""Strong greedy Orbit Wars agent with aggressive early pressure and reinforcement planning."""
import math
from kaggle_environments.envs.orbit_wars import orbit_wars as ow

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_R = 10.0
MAX_SPEED = 6.0
SUN_CLEARANCE = 1.5
MIN_SEND_SHIPS = 6
EARLY_RUSH_TURNS = 3
DEFAULT_RESERVE = 4

_step = 0


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def fleet_speed(ships):
    ships = max(1, ships)
    ratio = math.log(ships) / math.log(1000.0)
    ratio = max(0.0, min(1.0, ratio))
    return 1.0 + (MAX_SPEED - 1.0) * (ratio ** 1.5)


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-9:
        return dist(px, py, x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return dist(px, py, proj_x, proj_y)


def segment_hits_sun(x1, y1, x2, y2, safety=SUN_CLEARANCE):
    return point_to_segment_distance(CENTER_X, CENTER_Y, x1, y1, x2, y2) < SUN_R + safety


def launch_point(sx, sy, sr, angle):
    clearance = sr + 0.05
    return sx + math.cos(angle) * clearance, sy + math.sin(angle) * clearance


def actual_path_geometry(sx, sy, sr, tx, ty, tr):
    angle = math.atan2(ty - sy, tx - sx)
    start_x, start_y = launch_point(sx, sy, sr, angle)
    distance_to_target = max(0.0, dist(sx, sy, tx, ty) - (sr + 0.05) - tr)
    end_x = start_x + math.cos(angle) * distance_to_target
    end_y = start_y + math.sin(angle) * distance_to_target
    return angle, start_x, start_y, end_x, end_y, distance_to_target


def safe_angle_and_distance(sx, sy, sr, tx, ty, tr):
    angle, start_x, start_y, end_x, end_y, travel_distance = actual_path_geometry(
        sx, sy, sr, tx, ty, tr
    )
    if segment_hits_sun(start_x, start_y, end_x, end_y):
        return None
    return angle, travel_distance


def estimate_arrival(src, target, ships):
    result = safe_angle_and_distance(src.x, src.y, src.radius, target.x, target.y, target.radius)
    if result is None:
        return None
    angle, travel_distance = result
    turns = max(1, int(math.ceil(travel_distance / fleet_speed(ships))))
    return angle, turns


def collides(x1, y1, x2, y2, cx, cy, r):
    return point_to_segment_distance(cx, cy, x1, y1, x2, y2) <= r


def parse_observation(obs):
    planets = [ow.Planet(*p) for p in obs.get('planets', [])]
    fleets = [ow.Fleet(*f) for f in obs.get('fleets', [])]
    return planets, fleets


def enemy_fleet_threats(my_planets, fleets):
    threats = {p.id: 0 for p in my_planets}
    for fleet in fleets:
        if fleet.owner < 0:
            continue
        for p in my_planets:
            if collides(fleet.x, fleet.y,
                        fleet.x + math.cos(fleet.angle) * fleet_speed(fleet.ships) * 60,
                        fleet.y + math.sin(fleet.angle) * fleet_speed(fleet.ships) * 60,
                        p.x, p.y, p.radius):
                threats[p.id] += fleet.ships
    return threats


def capture_value(src, tgt, turns, ships, step):
    base = tgt.production * 150
    if tgt.owner == -1:
        base += 50 + tgt.production * 12
    else:
        base += 120 + tgt.production * 20
    base += max(0, 25 - turns) * 2
    distance = dist(src.x, src.y, tgt.x, tgt.y)
    base -= distance * 0.2
    if step <= EARLY_RUSH_TURNS and tgt.owner == -1:
        base += 60
    if tgt.production >= 3:
        base += 30
    score = base - ships * 0.8
    return score / max(1, turns)


def choose_best_attacks(my_planets, targets, step):
    moves = []
    for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        available = max(0, src.ships - (1 if step <= EARLY_RUSH_TURNS else DEFAULT_RESERVE))
        if available <= 0:
            continue
        best = None
        best_score = -1e9
        for tgt in targets:
            needed = tgt.ships + 1
            if tgt.owner != -1:
                needed += tgt.production * (3 if step <= EARLY_RUSH_TURNS else 2)
                needed += 3
            sent = min(available, max(MIN_SEND_SHIPS, needed))
            if sent > available and tgt.owner == -1:
                sent = available
            if sent > available:
                continue
            result = estimate_arrival(src, tgt, sent)
            if result is None:
                continue
            angle, turns = result
            score = capture_value(src, tgt, turns, sent, step)
            if score > best_score:
                best_score = score
                best = (tgt, angle, turns, sent)
        if best is not None:
            tgt, angle, _, sent = best
            moves.append((best_score, src, tgt, angle, sent))
    moves.sort(key=lambda item: item[0], reverse=True)
    return [(src, tgt, angle, sent) for _, src, tgt, angle, sent in moves]


def plan_reinforcements(my_planets, enemy_fleets):
    if not enemy_fleets:
        return []
    targets = []
    for p in my_planets:
        danger = 0
        for f in enemy_fleets:
            if collides(f.x, f.y,
                        f.x + math.cos(f.angle) * fleet_speed(f.ships) * 60,
                        f.y + math.sin(f.angle) * fleet_speed(f.ships) * 60,
                        p.x, p.y, p.radius):
                danger += f.ships
        if danger > p.ships + 2:
            targets.append((p, danger - p.ships))
    reinforcements = []
    for planet, needed in sorted(targets, key=lambda x: x[1], reverse=True):
        sources = sorted(
            [p for p in my_planets if p.id != planet.id and p.ships > MIN_SEND_SHIPS],
            key=lambda p: dist(p.x, p.y, planet.x, planet.y)
        )
        remainder = needed + 1
        for src in sources:
            available = max(0, src.ships - DEFAULT_RESERVE)
            if available < MIN_SEND_SHIPS:
                continue
            send = min(available, remainder)
            result = estimate_arrival(src, planet, send)
            if result is None:
                continue
            angle, _ = result
            reinforcements.append((src, planet, angle, send))
            remainder -= send
            if remainder <= 0:
                break
    return reinforcements


def agent(obs):
    global _step
    _step += 1
    planets, fleets = parse_observation(obs)
    my_player = obs.get('player', 0)
    my_planets = [p for p in planets if p.owner == my_player]
    if not my_planets:
        return []
    enemy_planets = [p for p in planets if p.owner != my_player]
    enemy_fleets = [f for f in fleets if f.owner != my_player and f.owner >= 0]
    moves = []

    reinforcements = plan_reinforcements(my_planets, enemy_fleets)
    reinforcement_sources = set()
    for src, tgt, angle, send in reinforcements:
        if src.ships >= send + 1:
            moves.append([src.id, angle, send])
            reinforcement_sources.add(src.id)

    targets = sorted(enemy_planets, key=lambda p: (p.owner == -1, p.production, -p.ships), reverse=True)
    attack_sources = [p for p in my_planets if p.id not in reinforcement_sources]
    attacks = choose_best_attacks(attack_sources, targets, _step)
    used_sources = set(reinforcement_sources)
    for src, tgt, angle, send in attacks:
        if src.id in used_sources:
            continue
        if send <= 0 or src.ships < send:
            continue
        moves.append([src.id, angle, send])
        used_sources.add(src.id)
    return moves


__all__ = ['agent']
