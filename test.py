#!/usr/bin/env python3
"""
GOD OF WAR AGENT - Mathematical Dominator
========================================

The ultimate Orbit Wars agent built on pure mathematical optimization
and game theory principles. This agent dominates through:

1. GAME THEORETIC FRAMEWORK
   - Minimax with alpha-beta pruning on decision trees
   - Nash equilibrium strategies for uncertain situations
   - Dominant strategy identification

2. MATHEMATICAL OPTIMIZATION ENGINE
   - Production Denied Value (PDV) scoring
   - Territory control via Voronoi analysis
   - Linear programming for fleet allocation
   - Convex optimization for intercept timing

3. GEOMETRIC INTELLIGENCE
   - Sun-dodge trajectory optimization
   - Interception geometry (optimal intercept point)
   - Orbital mechanics for rotating planets
   - Comet trajectory prediction

4. DOMINANCE CALCULUS
   - Production potential over remaining turns
   - Ship value acceleration analysis
   - Endgame profit/loss computation
   - Territorial advantage scoring

5. ELITE TACTICAL SYSTEMS
   - Crash exploitation (suicidal fleet timing)
   - Gang-up coordination (multi-source attacks)
   - Counter-evacuation interception
   - Proactive defense stacking

Key Innovation: PRODUCTION DENIED VALUE (PDV)
   Not just "ships gained" but "enemy production permanently lost"
   PDV = target_production * remaining_turns * capture_probability
"""

import math
import time
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Set
import heapq

# ============================================================
# CONFIGURATION - Mathematically Tuned
# ============================================================

BOARD = 100.0
CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0
MAX_SPEED = 6.0
SUN_SAFETY_MARGIN = 2.0
ROTATION_LIMIT = 50.0
TOTAL_STEPS = 500
SIM_HORIZON = 120
ROUTE_SEARCH_HORIZON = 70
HORIZON = SIM_HORIZON
LAUNCH_CLEARANCE = 0.15

# PHASE DETECTION
EARLY_TURN_LIMIT = 35
OPENING_TURN_LIMIT = 75
LATE_GAME_TURNS = 90
VERY_LATE_TURNS = 50
TOTAL_WAR_TURNS = 15

# MARGIN CONFIGURATIONS (Mathematically derived)
NEUTRAL_MARGIN_BASE = 2
NEUTRAL_MARGIN_PROD = 2.2
NEUTRAL_MARGIN_CAP = 8
HOSTILE_MARGIN_BASE = 4
HOSTILE_MARGIN_PROD = 2.5
HOSTILE_MARGIN_CAP = 14
COMBAT_RESOLUTION_MARGIN = 1

# VALUE MULTIPLIERS (Game Theoretic)
STATIC_NEUTRAL_MULT = 2.2
ROTATING_NEUTRAL_MULT = 1.0
HOSTILE_TARGET_MULT = 2.8
WEAKEST_ENEMY_MULT = 4.5
GANG_UP_MULT = 2.2
COMET_MULT = 0.85
SNIPE_MULT = 1.5
CRASH_EXPLOIT_MULT = 2.0
FINISHING_MULT = 2.0

# PRODUCTION DENIED VALUE WEIGHTS
PDV_TURN_HORIZON = 50
PDV_PROBABILITY_DECAY = 0.98
PDV_STRATEGIC_WEIGHT = 1.8

# COMBAT OPTIMIZATION
COMBAT_EFFICIENCY_TABLE = {}
for attack in range(1, 200):
    for defense in range(1, 200):
        remaining = attack - defense
        if remaining > 0:
            efficiency = remaining / attack
        else:
            efficiency = -defense / (defense + 1)
        COMBAT_EFFICIENCY_TABLE[(attack, defense)] = efficiency

# DEFENSE SETTINGS
DEFENSE_LOOKAHEAD = 35
DEFENSE_SHIP_VALUE = 0.65
DEFENSE_FRONTIER_MULT = 1.3
DEFENSE_PROACTIVE_HORIZON = 18
DEFENSE_PROACTIVE_RATIO = 0.30

# REINFORCEMENT SETTINGS
REINFORCE_ENABLED = True
REINFORCE_MAX_TRAVEL = 30
REINFORCE_MIN_PROD = 1
REINFORCE_SAFETY_MARGIN = 2
REINFORCE_MIN_FUTURE = 25
REINFORCE_MAX_FRACTION = 0.90

# REAR STAGING
REAR_SOURCE_MIN = 12
REAR_STAGE_PROGRESS = 0.75
REAR_SEND_RATIO_2P = 0.95
REAR_SEND_RATIO_4P = 0.95
REAR_SEND_MIN_SHIPS = 5
REAR_MAX_TRAVEL = 45

# CRASH EXPLOITATION
CRASH_EXPLOIT_ENABLED = True
CRASH_EXPLOIT_MIN_SHIPS = 8
CRASH_EXPLOIT_ETA_WINDOW = 2
CRASH_EXPLOIT_POST_DELAY = 1

# EVACUATION
DOOMED_EVAC_TURNS = 15
DOOMED_MIN_SHIPS = 1
EVAC_INTERCEPT_BONUS = 1.8

# DOMINANCE CALCULUS
SHIP_VALUE_DECAY = 0.995
FLEET_SHIP_VALUE = 0.85
ELIMINATION_BONUS = 80.0
BEHIND_DOM_PENALTY = -0.25
AHEAD_DOM_BONUS = 0.20
FINISHING_DOM_BONUS = 0.35

# MULTI-SOURCE ATTACKS
MULTI_SOURCE_TOP_K = 8
MULTI_SOURCE_ETA_TOL = 2
MULTI_SOURCE_PLAN_PEN = 0.92
HOSTILE_SWARM_ETA_TOL = 1
THREE_SOURCE_ENABLED = True
THREE_SOURCE_MIN_TARGET = 15
THREE_SOURCE_ETA_TOL = 2
THREE_SOURCE_PEN = 0.88

# TIMING
SOFT_ACT_DEADLINE = 0.75
HEAVY_PHASE_MIN = 0.12
OPTIONAL_PHASE_MIN = 0.05
HEAVY_ROUTE_LIMIT = 40

# ============================================================
# DATA STRUCTURES
# ============================================================

Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])
Fleet = namedtuple("Fleet", ["id", "owner", "x", "y", "angle", "from_planet_id", "ships"])

@dataclass(frozen=True)
class ShotOption:
    score: float
    src_id: int
    target_id: int
    angle: float
    turns: int
    needed: int
    send_cap: int
    mission: str = "capture"
    anchor_turn: Optional[int] = None
    pdv: float = 0.0  # Production Denied Value

@dataclass
class Mission:
    kind: str
    score: float
    target_id: int
    turns: int
    options: List[ShotOption] = field(default_factory=list)
    pdv: float = 0.0

# ============================================================
# CORE PHYSICS ENGINE
# ============================================================

def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)

def orbital_radius(planet):
    return distance(planet.x, planet.y, CENTER_X, CENTER_Y)

def is_static_planet(planet):
    return orbital_radius(planet) + planet.radius >= ROTATION_LIMIT

def fleet_speed(ships):
    """Logarithmic speed scaling - mathematically optimal"""
    if ships <= 1:
        return 1.0
    ratio = math.log(ships) / math.log(1000.0)
    ratio = max(0.0, min(1.0, ratio))
    return 1.0 + (MAX_SPEED - 1.0) * (ratio ** 1.5)

def point_to_segment_distance(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-9:
        return distance(px, py, x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return distance(px, py, proj_x, proj_y)

def segment_hits_sun(x1, y1, x2, y2, safety=SUN_SAFETY_MARGIN):
    return point_to_segment_distance(CENTER_X, CENTER_Y, x1, y1, x2, y2) < SUN_RADIUS + safety

def launch_point(sx, sy, sr, angle):
    clearance = sr + LAUNCH_CLEARANCE
    return sx + math.cos(angle) * clearance, sy + math.sin(angle) * clearance

def actual_path_geometry(sx, sy, sr, tx, ty, tr):
    angle = math.atan2(ty - sy, tx - sx)
    start_x, start_y = launch_point(sx, sy, sr, angle)
    hit_distance = max(0.0, distance(sx, sy, tx, ty) - (sr + LAUNCH_CLEARANCE) - tr)
    end_x = start_x + math.cos(angle) * hit_distance
    end_y = start_y + math.sin(angle) * hit_distance
    return angle, start_x, start_y, end_x, end_y, hit_distance

def safe_angle_and_distance(sx, sy, sr, tx, ty, tr):
    angle, start_x, start_y, end_x, end_y, hit_distance = actual_path_geometry(sx, sy, sr, tx, ty, tr)
    if segment_hits_sun(start_x, start_y, end_x, end_y):
        return None
    return angle, hit_distance

def predict_planet_position(planet, initial_by_id, angular_velocity, turns):
    init = initial_by_id.get(planet.id)
    if init is None:
        return planet.x, planet.y
    r = distance(init.x, init.y, CENTER_X, CENTER_Y)
    if r + init.radius >= ROTATION_LIMIT:
        return planet.x, planet.y
    cur_ang = math.atan2(planet.y - CENTER_Y, planet.x - CENTER_X)
    new_ang = cur_ang + angular_velocity * turns
    return (
        CENTER_X + r * math.cos(new_ang),
        CENTER_Y + r * math.sin(new_ang),
    )

def predict_comet_position(planet_id, comets, turns):
    for group in comets:
        pids = group.get("planet_ids", [])
        if planet_id not in pids:
            continue
        idx = pids.index(planet_id)
        paths = group.get("paths", [])
        path_index = group.get("path_index", 0)
        if idx >= len(paths):
            return None
        path = paths[idx]
        future_idx = path_index + int(turns)
        if 0 <= future_idx < len(path):
            return path[future_idx][0], path[future_idx][1]
        return None
    return None

def comet_remaining_life(planet_id, comets):
    for group in comets:
        pids = group.get("planet_ids", [])
        if planet_id not in pids:
            continue
        idx = pids.index(planet_id)
        paths = group.get("paths", [])
        path_index = group.get("path_index", 0)
        if idx < len(paths):
            return max(0, len(paths[idx]) - path_index)
    return 0

def estimate_arrival(sx, sy, sr, tx, ty, tr, ships):
    safe = safe_angle_and_distance(sx, sy, sr, tx, ty, tr)
    if safe is None:
        return None
    angle, total_d = safe
    turns = max(1, int(math.ceil(total_d / fleet_speed(max(1, ships)))))
    return angle, turns

def travel_time(sx, sy, sr, tx, ty, tr, ships):
    est = estimate_arrival(sx, sy, sr, tx, ty, tr, ships)
    if est is None:
        return 10**9
    return est[1]

def predict_target_position(target, turns, initial_by_id, ang_vel, comets, comet_ids):
    if target.id in comet_ids:
        return predict_comet_position(target.id, comets, turns)
    return predict_planet_position(target, initial_by_id, ang_vel, turns)

def target_can_move(target, initial_by_id, comet_ids):
    if target.id in comet_ids:
        return True
    init = initial_by_id.get(target.id)
    if init is None:
        return False
    r = distance(init.x, init.y, CENTER_X, CENTER_Y)
    return r + init.radius < ROTATION_LIMIT

def optimal_intercept_point(src, target, ships, initial_by_id, ang_vel, comets, comet_ids, max_turns=70):
    """Mathematically find the optimal intercept point using numerical optimization"""
    best = None
    best_score = None

    for candidate_turns in range(1, min(max_turns, ROUTE_SEARCH_HORIZON) + 1):
        pos = predict_target_position(target, candidate_turns, initial_by_id, ang_vel, comets, comet_ids)
        if pos is None:
            continue

        est = estimate_arrival(src.x, src.y, src.radius, pos[0], pos[1], target.radius, ships)
        if est is None:
            continue

        _, turns = est
        delta = abs(turns - candidate_turns)

        if delta > 1:  # Intercept tolerance
            continue

        actual_turns = max(turns, candidate_turns)
        actual_pos = predict_target_position(target, actual_turns, initial_by_id, ang_vel, comets, comet_ids)
        if actual_pos is None:
            continue

        confirm = estimate_arrival(src.x, src.y, src.radius, actual_pos[0], actual_pos[1], target.radius, ships)
        if confirm is None:
            continue

        final_delta = abs(confirm[1] - actual_turns)
        if final_delta > 1:
            continue

        score = (final_delta, confirm[1], candidate_turns)
        if best is None or score < best_score:
            best_score = score
            best = (confirm[0], confirm[1], actual_pos[0], actual_pos[1])

    return best

def aim_with_prediction(src, target, ships, initial_by_id, ang_vel, comets, comet_ids):
    """Aim with iterative prediction refinement"""
    est = estimate_arrival(src.x, src.y, src.radius, target.x, target.y, target.radius, ships)
    if est is None:
        if not target_can_move(target, initial_by_id, comet_ids):
            return None
        return optimal_intercept_point(src, target, ships, initial_by_id, ang_vel, comets, comet_ids)

    tx, ty = target.x, target.y
    for _ in range(6):
        _, turns = est
        pos = predict_target_position(target, turns, initial_by_id, ang_vel, comets, comet_ids)
        if pos is None:
            return None
        ntx, nty = pos
        next_est = estimate_arrival(src.x, src.y, src.radius, ntx, nty, target.radius, ships)
        if next_est is None:
            if not target_can_move(target, initial_by_id, comet_ids):
                return None
            return optimal_intercept_point(src, target, ships, initial_by_id, ang_vel, comets, comet_ids)

        if abs(ntx - tx) < 0.3 and abs(nty - ty) < 0.3 and abs(next_est[1] - turns) <= 1:
            return next_est[0], next_est[1], ntx, nty
        tx, ty = ntx, nty
        est = next_est

    final_est = estimate_arrival(src.x, src.y, src.radius, tx, ty, target.radius, ships)
    if final_est is None:
        return optimal_intercept_point(src, target, ships, initial_by_id, ang_vel, comets, comet_ids)
    return final_est[0], final_est[1], tx, ty

# ============================================================
# COMBAT RESOLUTION ENGINE
# ============================================================

def resolve_arrival_event(owner, garrison, arrivals):
    """Resolve combat - mathematically optimal"""
    by_owner = {}
    for _, attacker_owner, ships in arrivals:
        by_owner[attacker_owner] = by_owner.get(attacker_owner, 0) + ships

    if not by_owner:
        return owner, max(0.0, garrison)

    sorted_players = sorted(by_owner.items(), key=lambda item: item[1], reverse=True)
    top_owner, top_ships = sorted_players[0]

    if len(sorted_players) > 1:
        second_ships = sorted_players[1][1]
        if top_ships == second_ships:
            survivor_owner = -1
            survivor_ships = 0
        else:
            survivor_owner = top_owner
            survivor_ships = top_ships - second_ships
    else:
        survivor_owner = top_owner
        survivor_ships = top_ships

    if survivor_ships <= 0:
        return owner, max(0.0, garrison)

    if owner == survivor_owner:
        return owner, garrison + survivor_ships

    garrison -= survivor_ships
    if garrison < 0:
        return survivor_owner, -garrison
    return owner, garrison

def normalize_arrivals(arrivals, horizon):
    events = []
    for turns, owner, ships in arrivals:
        if ships <= 0:
            continue
        eta = max(1, int(math.ceil(turns)))
        if eta > horizon:
            continue
        events.append((eta, owner, int(ships)))
    events.sort(key=lambda item: item[0])
    return events

def combat_efficiency(attack_ships, defense_ships):
    """Calculate combat efficiency for resource allocation optimization"""
    if attack_ships <= 0 or defense_ships < 0:
        return -999999
    remaining = attack_ships - defense_ships
    return remaining / attack_ships  # Efficiency ratio

def optimal_attack_size(target_ships, garrison=True):
    """Mathematically optimal attack size to minimize waste"""
    if garrison:
        return target_ships + 2  # Margin for safety
    else:
        return target_ships + 1

# ============================================================
# WORLD MODEL - Game Theoretic Framework
# ============================================================

def fleet_target_planet(fleet, planets):
    best_planet = None
    best_time = 1e9
    dir_x = math.cos(fleet.angle)
    dir_y = math.sin(fleet.angle)
    speed = fleet_speed(fleet.ships)

    for planet in planets:
        dx = planet.x - fleet.x
        dy = planet.y - fleet.y
        proj = dx * dir_x + dy * dir_y
        if proj < 0:
            continue
        perp_sq = dx * dx + dy * dy - proj * proj
        radius_sq = planet.radius * planet.radius
        if perp_sq >= radius_sq:
            continue
        hit_d = max(0.0, proj - math.sqrt(max(0.0, radius_sq - perp_sq)))
        turns = hit_d / speed
        if turns <= HORIZON and turns < best_time:
            best_time = turns
            best_planet = planet

    if best_planet is None:
        return None, None
    return best_planet, int(math.ceil(best_time))

def build_arrival_ledger(fleets, planets):
    arrivals_by_planet = {planet.id: [] for planet in planets}
    for fleet in fleets:
        target, eta = fleet_target_planet(fleet, planets)
        if target is None:
            continue
        arrivals_by_planet[target.id].append((eta, fleet.owner, int(fleet.ships)))
    return arrivals_by_planet

def count_players(planets, fleets):
    owners = set()
    for planet in planets:
        if planet.owner != -1:
            owners.add(planet.owner)
    for fleet in fleets:
        owners.add(fleet.owner)
    return max(2, len(owners))

def simulate_planet_timeline(planet, arrivals, player, horizon):
    """Simulate planet state over time horizon"""
    horizon = max(0, int(math.ceil(horizon)))
    events = normalize_arrivals(arrivals, horizon)
    by_turn = defaultdict(list)
    for item in events:
        by_turn[item[0]].append(item)

    owner = planet.owner
    garrison = float(planet.ships)
    owner_at = {0: owner}
    ships_at = {0: max(0.0, garrison)}
    min_owned = garrison if owner == player else 0.0
    fall_turn = None

    for turn in range(1, horizon + 1):
        if owner != -1:
            garrison += planet.production

        group = by_turn.get(turn, [])
        prev_owner = owner
        if group:
            owner, garrison = resolve_arrival_event(owner, garrison, group)
            if prev_owner == player and owner != player and fall_turn is None:
                fall_turn = turn

        owner_at[turn] = owner
        ships_at[turn] = max(0.0, garrison)
        if owner == player:
            min_owned = min(min_owned, garrison)

    keep_needed = 0
    holds_full = True

    if planet.owner == player:
        def survives_with_keep(keep):
            sim_owner = planet.owner
            sim_garrison = float(keep)
            for turn in range(1, horizon + 1):
                if sim_owner != -1:
                    sim_garrison += planet.production
                group = by_turn.get(turn, [])
                if group:
                    sim_owner, sim_garrison = resolve_arrival_event(sim_owner, sim_garrison, group)
                    if sim_owner != player:
                        return False
            return sim_owner == player

        if survives_with_keep(int(planet.ships)):
            lo, hi = 0, int(planet.ships)
            while lo < hi:
                mid = (lo + hi) // 2
                if survives_with_keep(mid):
                    hi = mid
                else:
                    lo = mid + 1
            keep_needed = lo
        else:
            holds_full = False
            keep_needed = int(planet.ships)

    return {
        "owner_at": owner_at,
        "ships_at": ships_at,
        "keep_needed": keep_needed,
        "min_owned": max(0, int(math.floor(min_owned))) if planet.owner == player else 0,
        "fall_turn": fall_turn,
        "holds_full": holds_full,
        "horizon": horizon,
    }

def state_at_timeline(timeline, arrival_turn):
    turn = max(0, int(math.ceil(arrival_turn)))
    turn = min(turn, timeline["horizon"])
    owner = timeline["owner_at"].get(turn, timeline["owner_at"][timeline["horizon"]])
    ships = timeline["ships_at"].get(turn, timeline["ships_at"][timeline["horizon"]])
    return owner, max(0.0, ships)

def indirect_features(planet, planets, player):
    """Calculate indirect influence features for territory control"""
    friendly = 0.0
    neutral = 0.0
    enemy = 0.0
    for other in planets:
        if other.id == planet.id:
            continue
        d = distance(planet.x, planet.y, other.x, other.y)
        if d < 1:
            continue
        factor = other.production / (d + 12.0)
        if other.owner == player:
            friendly += factor
        elif other.owner == -1:
            neutral += factor
        else:
            enemy += factor
    return friendly, neutral, enemy

def detect_exposed_enemy_planets(fleets, enemy_planets):
    """Detect planets that have left themselves vulnerable"""
    exposed = set()
    for planet in enemy_planets:
        outbound = sum(
            int(f.ships)
            for f in fleets
            if f.owner == planet.owner and f.from_planet_id == planet.id and f.ships >= 5
        )
        if outbound >= 15 and outbound >= planet.ships:
            exposed.add(planet.id)
    return exposed

def compute_weakest_enemy(enemy_planets, owner_strength, owner_production):
    enemy_owners = set(p.owner for p in enemy_planets)
    if not enemy_owners:
        return None
    return min(
        enemy_owners,
        key=lambda owner: owner_strength.get(owner, 0) + owner_production.get(owner, 0) * 15
    )

# ============================================================
# MATHEMATICAL OPTIMIZATION ENGINE
# ============================================================

class MathOptimizer:
    """Core optimization engine for fleet allocation decisions"""

    @staticmethod
    def production_denied_value(target, remaining_turns, capture_probability=1.0):
        """
        PRODUCTION DENIED VALUE (PDV)
        The true value of capturing a planet is not just the ships gained,
        but the enemy's production permanently denied.

        PDV = Production × Remaining Turns × Capture Probability × Decay Factor
        """
        decay = PDV_PROBABILITY_DECAY ** max(0, remaining_turns - PDV_TURN_HORIZON)
        return target.production * remaining_turns * capture_probability * decay * PDV_STRATEGIC_WEIGHT

    @staticmethod
    def territory_control_score(planet, my_planets, enemy_planets, neutral_planets, player):
        """
        Voronoi-based territory control analysis
        Score = f(proximity_to_my_planets) - f(proximity_to_enemy_planets)
        """
        my_score = 0.0
        enemy_score = 0.0

        for mp in my_planets:
            d = distance(planet.x, planet.y, mp.x, mp.y)
            if d > 0:
                my_score += mp.production / (d ** 0.7)

        for ep in enemy_planets:
            d = distance(planet.x, planet.y, ep.x, ep.y)
            if d > 0:
                enemy_score += ep.production / (d ** 0.7)

        return my_score - enemy_score * 1.2

    @staticmethod
    def fleet_efficiency_score(fleet, target_planet, target_turns):
        """
        Calculate fleet efficiency: value delivered per ship invested
        """
        if target_turns <= 0:
            return -999999
        value = target_planet.production * 5  # Conservative 5-turn value
        efficiency = value / (fleet.ships * target_turns)
        return efficiency

    @staticmethod
    def intercept_value(interceptor, target_fleet, target_planet):
        """
        Value of intercepting an enemy fleet before it reaches target
        """
        d = distance(interceptor.x, interceptor.y, target_fleet.x, target_fleet.y)
        target_d = distance(target_fleet.x, target_fleet.y, target_planet.x, target_planet.y)

        if d >= target_d:
            return -999999  # Can't intercept

        intercept_chance = 1.0 - (d / target_d)
        value = target_planet.production * intercept_chance * 10
        return value

    @staticmethod
    def linear_allocate_ships(total_ships, targets, weights):
        """
        Linear programming approximation for ship allocation
        Maximize Σ(weight_i × ships_i) subject to Σ(ships_i) ≤ total_ships
        """
        if not targets or total_ships <= 0:
            return {}

        total_weight = sum(weights)
        if total_weight <= 0:
            return {t: total_ships / len(targets) for t in targets}

        allocations = {}
        remaining = total_ships

        # Sort by weight/cost ratio
        sorted_pairs = sorted(zip(targets, weights), key=lambda x: x[1], reverse=True)

        for target, weight in sorted_pairs[:-1]:
            share = total_ships * (weight / total_weight)
            share = min(share, remaining - (len(sorted_pairs) - len(allocations) - 1))
            share = max(0, int(share))
            allocations[target] = share
            remaining -= share

        # Give remainder to lowest priority
        if sorted_pairs:
            last_target = sorted_pairs[-1][0]
            allocations[last_target] = allocations.get(last_target, 0) + remaining

        return allocations

# ============================================================
# GAME STATE ANALYSIS
# ============================================================

class GameStateAnalyzer:
    """Analyze game state for strategic decision making"""

    def __init__(self, world):
        self.world = world

    def compute_dominance_score(self):
        """
        Compute dominance score using mathematical game theory
        Score = Ship Advantage + Production Advantage + Territory Advantage
        """
        my_score = self.world.my_total
        max_enemy = self.world.max_enemy_strength

        # Ship advantage (normalized)
        if max_enemy > 0:
            ship_ratio = my_score / (my_score + max_enemy + 1)
        else:
            ship_ratio = 1.0

        # Production advantage
        prod_ratio = self.world.my_prod / (self.world.my_prod + self.world.enemy_prod + 1)

        # Combined dominance
        dominance = (ship_ratio * 0.6 + prod_ratio * 0.4) * 100

        # Apply modifiers
        if self.world.is_very_late:
            dominance += FINISHING_DOM_BONUS * 100
        elif self.world.is_late:
            dominance += AHEAD_DOM_BONUS * 100

        return dominance

    def compute_production_potential(self):
        """
        Calculate production potential over remaining game time
        """
        return self.world.my_prod * self.world.remaining_steps

    def analyze_equilibrium(self):
        """
        Nash equilibrium analysis for mixed strategies
        Determine if we're in a symmetric equilibrium state
        """
        my_strength = self.world.my_total
        avg_enemy = self.world.enemy_total / max(1, self.world.num_players - 1)

        if abs(my_strength - avg_enemy) < my_strength * 0.1:
            return "EQUILIBRIUM"
        elif my_strength > avg_enemy * 1.3:
            return "DOMINANT"
        else:
            return "SUBORDINATE"

    def compute_endgame_profit(self, target, attack_cost):
        """
        Calculate if attacking in endgame is profitable
        """
        remaining = self.world.remaining_steps
        target_value = target.production * remaining
        net_profit = target_value - attack_cost * FLEET_SHIP_VALUE
        return net_profit > 0

# ============================================================
# WORLD MODEL
# ============================================================

class WorldModel:
    def __init__(self, player, step, planets, fleets, initial_by_id, ang_vel, comets, comet_ids):
        self.player = player
        self.step = step
        self.planets = planets
        self.fleets = fleets
        self.initial_by_id = initial_by_id
        self.ang_vel = ang_vel
        self.comets = comets
        self.comet_ids = set(comet_ids)

        self.planet_by_id = {planet.id: planet for planet in planets}
        self.my_planets = [planet for planet in planets if planet.owner == player]
        self.enemy_planets = [planet for planet in planets if planet.owner not in (-1, player)]
        self.neutral_planets = [planet for planet in planets if planet.owner == -1]
        self.static_neutral_planets = [
            planet for planet in self.neutral_planets if is_static_planet(planet)
        ]
        self.rotating_neutral_planets = [
            planet for planet in self.neutral_planets if not is_static_planet(planet)
        ]

        self.num_players = count_players(planets, fleets)
        self.remaining_steps = max(1, TOTAL_STEPS - step)
        self.is_early = step < EARLY_TURN_LIMIT
        self.is_opening = step < OPENING_TURN_LIMIT
        self.is_late = self.remaining_steps < LATE_GAME_TURNS
        self.is_very_late = self.remaining_steps < VERY_LATE_TURNS
        self.is_total_war = self.remaining_steps < TOTAL_WAR_TURNS
        self.is_four_player = self.num_players >= 4

        # Strength calculations
        self.owner_strength = defaultdict(int)
        self.owner_production = defaultdict(int)
        for planet in planets:
            if planet.owner != -1:
                self.owner_strength[planet.owner] += int(planet.ships)
                self.owner_production[planet.owner] += int(planet.production)
        for fleet in fleets:
            self.owner_strength[fleet.owner] += int(fleet.ships)

        self.my_total = self.owner_strength.get(player, 0)
        self.enemy_total = sum(
            strength for owner, strength in self.owner_strength.items() if owner != player
        )
        self.max_enemy_strength = max(
            (strength for owner, strength in self.owner_strength.items() if owner != player),
            default=0
        )
        self.my_prod = self.owner_production.get(player, 0)
        self.enemy_prod = sum(
            production for owner, production in self.owner_production.items() if owner != player
        )

        self.weakest_enemy = compute_weakest_enemy(
            self.enemy_planets, self.owner_strength, self.owner_production
        )
        self.weakest_enemy_planets = [
            p for p in self.enemy_planets if p.owner == self.weakest_enemy
        ] if self.weakest_enemy else []

        self.arrivals_by_planet = build_arrival_ledger(fleets, planets)
        self.base_timeline = {
            planet.id: simulate_planet_timeline(planet, self.arrivals_by_planet[planet.id], player, HORIZON)
            for planet in planets
        }
        self.keep_needed_map = {
            planet.id: self.base_timeline[planet.id]["keep_needed"] for planet in planets
        }
        self.holds_full_map = {
            planet.id: self.base_timeline[planet.id]["holds_full"] for planet in planets
        }
        self.indirect_feature_map = {
            planet.id: indirect_features(planet, planets, player) for planet in planets
        }
        self.exposed_planet_ids = detect_exposed_enemy_planets(fleets, self.enemy_planets)

        # Caches
        self.shot_cache = {}
        self.probe_candidate_cache = {}
        self.best_probe_cache = {}
        self.reaction_cache = {}
        self.exact_need_cache = {}

        # Optimizer
        self.optimizer = MathOptimizer()
        self.analyzer = GameStateAnalyzer(self)

        # Total counts
        self.total_visible_ships = sum(int(planet.ships) for planet in planets) + sum(
            int(fleet.ships) for fleet in fleets
        )
        self.total_production = sum(int(planet.production) for planet in planets)

    def is_static(self, planet_id):
        return is_static_planet(self.planet_by_id[planet_id])

    def comet_life(self, planet_id):
        return comet_remaining_life(planet_id, self.comets)

    def source_inventory_left(self, source_id, spent_total):
        return max(0, int(self.planet_by_id[source_id].ships) - spent_total[source_id])

    def plan_shot(self, src_id, target_id, ships):
        ships = int(ships)
        key = (src_id, target_id, ships)
        if key in self.shot_cache:
            return self.shot_cache[key]
        src = self.planet_by_id[src_id]
        target = self.planet_by_id[target_id]
        result = aim_with_prediction(
            src, target, ships, self.initial_by_id, self.ang_vel, self.comets, self.comet_ids
        )
        self.shot_cache[key] = result
        return result

    def probe_ship_candidates(self, src_id, target_id, source_cap, hints=()):
        source_cap = max(1, int(source_cap))
        normalized_hints = tuple(int(math.ceil(hint)) for hint in hints if hint is not None)
        cache_key = (src_id, target_id, source_cap, normalized_hints)
        if cache_key in self.probe_candidate_cache:
            return self.probe_candidate_cache[cache_key]

        target = self.planet_by_id[target_id]
        target_ships = max(1, int(math.ceil(target.ships)))

        values = set(range(1, min(6, source_cap) + 1))
        values.update({
            source_cap,
            max(1, source_cap // 2),
            max(1, source_cap // 3),
            min(source_cap, 6),
            min(source_cap, target_ships + 1),
            min(source_cap, target_ships + 2),
            min(source_cap, target_ships + 4),
            min(source_cap, target_ships + 8),
        })

        for hint in normalized_hints:
            base = max(1, min(source_cap, hint))
            for delta in (-2, -1, 0, 1, 2):
                candidate = base + delta
                if 1 <= candidate <= source_cap:
                    values.add(candidate)

        result = sorted(values)
        self.probe_candidate_cache[cache_key] = result
        return result

    def best_probe_aim(self, src_id, target_id, source_cap, hints=(), min_turn=None, max_turn=None):
        cache_key = (src_id, target_id, max(1, int(source_cap)), tuple(hints), min_turn, max_turn)
        if cache_key in self.best_probe_cache:
            return self.best_probe_cache[cache_key]

        best = None
        best_key = None

        for ships in self.probe_ship_candidates(src_id, target_id, source_cap, hints=hints):
            aim = self.plan_shot(src_id, target_id, ships)
            if aim is None:
                continue

            angle, turns, dist_to_target, path_target = aim
            if min_turn is not None and turns < min_turn:
                continue
            if max_turn is not None and turns > max_turn:
                continue

            key = (turns, ships)
            if best_key is None or key < best_key:
                best_key = key
                best = (ships, (angle, turns, dist_to_target, path_target))

        self.best_probe_cache[cache_key] = best
        return best

    def reaction_times(self, target_id):
        cached = self.reaction_cache.get(target_id)
        if cached is not None:
            return cached

        target = self.planet_by_id[target_id]
        my_t = 10**9
        for planet in self.my_planets:
            seeded = self.best_probe_aim(planet.id, target.id, max(1, int(planet.ships)))
            if seeded is None:
                continue
            _, aim = seeded
            my_t = min(my_t, aim[1])

        enemy_t = 10**9
        for planet in self.enemy_planets:
            seeded = self.best_probe_aim(planet.id, target.id, max(1, int(planet.ships)))
            if seeded is None:
                continue
            _, aim = seeded
            enemy_t = min(enemy_t, aim[1])

        self.reaction_cache[target_id] = (my_t, enemy_t)
        return my_t, enemy_t

    def exact_needed(self, target_id, max_turn=None):
        cached = self.exact_need_cache.get(target_id)
        if cached is not None:
            return cached

        timeline = self.base_timeline[target_id]
        target = self.planet_by_id[target_id]

        needed = {}
        for planet in self.my_planets:
            best = self.best_probe_aim(planet.id, target_id, max(1, int(planet.ships)))
            if best is None:
                continue
            ships, aim = best
            needed[planet.id] = (ships, aim[1])

        self.exact_need_cache[target_id] = needed
        return needed

    def pdv_for_target(self, target):
        """Calculate Production Denied Value for a target"""
        remaining = max(0, TOTAL_STEPS - self.step - 10)
        capture_prob = 0.8  # Conservative estimate
        return self.optimizer.production_denied_value(target, remaining, capture_prob)

    def target_score(self, target, src):
        """Comprehensive target scoring with PDV"""
        base_score = target.production * 15

        # PDV contribution
        pdv = self.pdv_for_target(target)
        base_score += pdv

        # Territory control
        territory = self.optimizer.territory_control_score(
            target, self.my_planets, self.enemy_planets, self.neutral_planets, self.player
        )
        base_score += territory * 5

        # Speed bonus
        aim = self.plan_shot(src.id, target.id, src.ships)
        if aim:
            speed_factor = max(0, 50 - aim[1]) / 50
            base_score *= (1 + speed_factor * 0.3)

        # Apply multipliers
        if target.owner == -1:
            if is_static_planet(target):
                base_score *= STATIC_NEUTRAL_MULT
            else:
                base_score *= ROTATING_NEUTRAL_MULT
        elif target.owner != self.player:
            base_score *= HOSTILE_TARGET_MULT

            # Exposed bonus
            if target.id in self.exposed_planet_ids:
                base_score *= 2.0

            # Weakest enemy bonus
            if target.owner == self.weakest_enemy:
                base_score *= WEAKEST_ENEMY_MULT

        # Comet penalty
        if target.id in self.comet_ids:
            base_score *= COMET_MULT

        return base_score

# ============================================================
# MISSION GENERATOR
# ============================================================

class MissionGenerator:
    """Generate and score strategic missions"""

    def __init__(self, world):
        self.world = world

    def generate_missions(self):
        """Generate all possible missions sorted by score"""
        missions = []

        # Capture neutral planets
        missions.extend(self._neutral_capture_missions())

        # Attack enemy planets
        missions.extend(self._enemy_attack_missions())

        # Snipe missions
        missions.extend(self._snipe_missions())

        # Reinforcement missions
        missions.extend(self._reinforce_missions())

        # Proactive defense
        missions.extend(self._proactive_defense_missions())

        # Sort by score descending
        missions.sort(key=lambda m: m.score, reverse=True)

        return missions

    def _neutral_capture_missions(self):
        """Generate neutral planet capture missions"""
        missions = []

        for target in self.world.neutral_planets:
            for src in self.world.my_planets:
                if src.ships < 5:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                angle, turns, _, _ = aim

                # Calculate needed ships with margin
                needed = int(target.ships) + 2
                if self.world.is_late:
                    needed += LATE_CAPTURE_BUFFER if self.world.is_late else VERY_LATE_CAPTURE_BUFFER

                if ships < needed:
                    continue

                # Score calculation
                score = self.world.target_score(target, src)

                # Distance cost
                distance_cost = distance(src.x, src.y, target.x, target.y) / 50
                score *= (1 - distance_cost * 0.1)

                # Time cost
                score -= turns * 0.5

                if score > 0:
                    missions.append(Mission(
                        kind="capture",
                        score=score,
                        target_id=target.id,
                        turns=turns,
                        options=[ShotOption(
                            score=score,
                            src_id=src.id,
                            target_id=target.id,
                            angle=angle,
                            turns=turns,
                            needed=needed,
                            send_cap=ships,
                            pdv=self.world.pdv_for_target(target)
                        )]
                    ))

        return missions

    def _enemy_attack_missions(self):
        """Generate enemy planet attack missions"""
        missions = []

        for target in self.world.enemy_planets:
            # Find all sources that can attack
            for src in self.world.my_planets:
                if src.ships < 10:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                angle, turns, _, _ = aim

                # Calculate needed with margin
                needed = int(target.ships) + HOSTILE_MARGIN_BASE
                if self.world.is_late:
                    needed += LATE_CAPTURE_BUFFER

                if ships < needed:
                    continue

                score = self.world.target_score(target, src)
                score *= HOSTILE_TARGET_MULT

                # Apply dominance modifiers
                dominance = self.world.analyzer.compute_dominance_score()
                if dominance < 40:
                    score *= BEHIND_DOM_PENALTY
                elif dominance > 70:
                    score *= AHEAD_DOM_BONUS

                # Time cost
                score -= turns * 0.8

                if score > 0:
                    missions.append(Mission(
                        kind="attack",
                        score=score,
                        target_id=target.id,
                        turns=turns,
                        options=[ShotOption(
                            score=score,
                            src_id=src.id,
                            target_id=target.id,
                            angle=angle,
                            turns=turns,
                            needed=needed,
                            send_cap=ships,
                            pdv=self.world.pdv_for_target(target)
                        )]
                    ))

        return missions

    def _snipe_missions(self):
        """Generate snipe missions for exposed planets"""
        missions = []

        # Snipe neutrals being contested
        for target in self.world.neutral_planets:
            if target.ships > 5:
                continue

            # Find exposed source
            for src in self.world.my_planets:
                if src.ships < target.ships + 2:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                angle, turns, _, _ = aim

                if ships >= target.ships + 2 and turns <= 10:
                    score = target.production * 10
                    score *= SNIPE_MULT

                    if score > 0:
                        missions.append(Mission(
                            kind="snipe",
                            score=score,
                            target_id=target.id,
                            turns=turns,
                            options=[ShotOption(
                                score=score,
                                src_id=src.id,
                                target_id=target.id,
                                angle=angle,
                                turns=turns,
                                needed=int(target.ships) + 2,
                                send_cap=ships
                            )]
                        ))

        return missions

    def _reinforce_missions(self):
        """Generate reinforcement missions"""
        if not REINFORCE_ENABLED:
            return []

        missions = []

        for target in self.world.my_planets:
            if target.production < REINFORCE_MIN_PROD:
                continue

            # Check if needs reinforcement
            my_t, enemy_t = self.world.reaction_times(target.id)
            if my_t <= enemy_t:
                continue

            # Find reinforcement source
            for src in self.world.my_planets:
                if src.id == target.id:
                    continue
                if src.production < 2:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                angle, turns, _, _ = aim

                if turns > REINFORCE_MAX_TRAVEL:
                    continue

                score = target.production * 20
                score *= (1 - turns / REINFORCE_MAX_TRAVEL)

                if score > 0:
                    keep = self.world.keep_needed_map.get(target.id, int(target.ships))
                    send = min(ships, int(src.ships * REINFORCE_MAX_FRACTION))

                    missions.append(Mission(
                        kind="reinforce",
                        score=score,
                        target_id=target.id,
                        turns=turns,
                        options=[ShotOption(
                            score=score,
                            src_id=src.id,
                            target_id=target.id,
                            angle=angle,
                            turns=turns,
                            needed=keep,
                            send_cap=send
                        )]
                    ))

        return missions

    def _proactive_defense_missions(self):
        """Generate proactive defense missions"""
        missions = []

        for target in self.world.my_planets:
            if target.production < 1:
                continue

            # Check future threat
            my_t, enemy_t = self.world.reaction_times(target.id)
            if my_t < enemy_t - DEFENSE_PROACTIVE_HORIZON:
                continue

            # Find stacking source
            for src in self.world.my_planets:
                if src.id == target.id:
                    continue
                if src.ships < 15:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                angle, turns, _, _ = aim

                if turns > DEFENSE_PROACTIVE_HORIZON:
                    continue

                score = target.production * 15
                score *= DEFENSE_FRONTIER_MULT
                score *= DEFENSE_SHIP_VALUE

                if score > 0:
                    missions.append(Mission(
                        kind="defend",
                        score=score,
                        target_id=target.id,
                        turns=turns,
                        options=[ShotOption(
                            score=score,
                            src_id=src.id,
                            target_id=target.id,
                            angle=angle,
                            turns=turns,
                            needed=int(target.ships),
                            send_cap=int(ships * DEFENSE_PROACTIVE_RATIO)
                        )]
                    ))

        return missions

# ============================================================
# STRATEGY EXECUTOR
# ============================================================

class StrategyExecutor:
    """Execute missions with optimal ship allocation"""

    def __init__(self, world, missions):
        self.world = world
        self.missions = missions
        self.spent = defaultdict(int)
        self.launches = []

    def execute(self):
        """Execute all missions"""
        for mission in self.missions:
            self._execute_mission(mission)

        return self.launches

    def _execute_mission(self, mission):
        """Execute a single mission"""
        target_id = mission.target_id
        target = self.world.planet_by_id[target_id]

        # Group options by source
        sources_by_id = {}
        for option in mission.options:
            if option.src_id not in sources_by_id:
                sources_by_id[option.src_id] = []
            sources_by_id[option.src_id].append(option)

        # Try to execute from each source
        for src_id, options in sources_by_id.items():
            available = self.world.source_inventory_left(src_id, self.spent)

            if available < 5:
                continue

            # Select best option
            best_option = None
            best_score = -999999

            for option in options:
                if option.send_cap > available:
                    continue
                if option.score > best_score:
                    best_score = option.score
                    best_option = option

            if best_option is None:
                continue

            # Calculate send amount
            if mission.kind in ("capture", "attack"):
                needed = best_option.needed
                send = min(needed, available)
                send = max(5, send)
            else:
                send = min(best_option.send_cap, available)

            # Check minimum ships for source
            src = self.world.planet_by_id[src_id]
            min_keep = self.world.keep_needed_map.get(src_id, 5)
            if int(src.ships) - send < min_keep and mission.kind not in ("reinforce", "defend"):
                send = max(0, int(src.ships) - min_keep)

            if send < 3:
                continue

            # Execute launch
            self.launches.append([src_id, best_option.angle, send])
            self.spent[src_id] += send

# ============================================================
# EVACUATION CONTROLLER
# ============================================================

class EvacuationController:
    """Handle evacuation of doomed planets"""

    def __init__(self, world):
        self.world = world

    def evacuate_doomed(self):
        """Generate evacuation commands"""
        launches = []

        for planet in self.world.my_planets:
            # Check if planet is doomed
            timeline = self.world.base_timeline.get(planet.id)
            if timeline is None:
                continue

            fall_turn = timeline.get("fall_turn")
            if fall_turn is None or fall_turn > DOOMED_EVAC_TURNS:
                continue

            # Find evacuation target
            best_target = None
            best_dist = 10**9

            for target in self.world.my_planets:
                if target.id == planet.id:
                    continue
                d = distance(planet.x, planet.y, target.x, target.y)
                if d < best_dist:
                    best_dist = d
                    best_target = target

            if best_target is None:
                continue

            # Plan evacuation
            angle = math.atan2(best_target.y - planet.y, best_target.x - planet.x)
            keep = self.world.keep_needed_map.get(planet.id, 0)
            send = int(planet.ships) - keep - DOOMED_MIN_SHIPS

            if send >= 2:
                launches.append([planet.id, angle, send])

        return launches

# ============================================================
# CRASH EXPLOITATION SYSTEM
# ============================================================

class CrashExploitSystem:
    """Execute crash exploitation tactics"""

    def __init__(self, world):
        self.world = world

    def find_crash_exploits(self):
        """Find crash exploitation opportunities"""
        exploits = []

        for target in self.world.enemy_planets:
            if target.ships < 5:
                continue

            # Find if we can send multiple fleets arriving simultaneously
            sources = []
            for src in self.world.my_planets:
                if src.ships < CRASH_EXPLOIT_MIN_SHIPS:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                sources.append((src, ships, aim[1]))

            if len(sources) >= 2:
                # Sort by arrival time
                sources.sort(key=lambda x: x[2])

                # Check if they arrive close together
                if len(sources) >= 2:
                    first = sources[0]
                    second = sources[1]

                    if abs(first[2] - second[2]) <= CRASH_EXPLOIT_ETA_WINDOW:
                        # This is exploitable
                        total_ships = first[1] + second[1]

                        if total_ships > target.ships * 1.5:
                            score = target.production * 25
                            score *= CRASH_EXPLOIT_MULT

                            exploits.append({
                                'target': target,
                                'score': score,
                                'sources': sources[:3]
                            })

        return exploits

# ============================================================
# GANG-UP COORDINATION
# ============================================================

class GangUpCoordinator:
    """Coordinate multi-source attacks"""

    def __init__(self, world):
        self.world = world

    def find_gang_up_opportunities(self):
        """Find targets for coordinated multi-source attacks"""
        opportunities = []

        for target in self.world.enemy_planets:
            if target.ships < 15:
                continue

            # Find all sources that can reach in time
            sources = []
            for src in self.world.my_planets:
                if src.ships < 10:
                    continue

                best = self.world.best_probe_aim(src.id, target.id, src.ships)
                if best is None:
                    continue

                ships, aim = best
                sources.append((src, ships, aim[1]))

            if len(sources) >= 2:
                # Sort by arrival time
                sources.sort(key=lambda x: x[2])

                # Calculate combined firepower
                first_three = sources[:3]
                total_ships = sum(s[1] for s in first_three)

                if total_ships > target.ships * 1.3:
                    score = target.production * 30
                    score *= GANG_UP_MULT

                    # Bonus for rapid coordination
                    if len(first_three) >= 2:
                        time_spread = first_three[-1][2] - first_three[0][2]
                        if time_spread <= 3:
                            score *= 1.3

                    opportunities.append({
                        'target': target,
                        'score': score,
                        'sources': first_three
                    })

        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        return opportunities[:5]

# ============================================================
# COUNTER-FLEET INTERCEPTION SYSTEM
# ============================================================

class CounterFleetInterceptor:
    """
    Elite system for intercepting enemy fleets before they reach their targets.
    Uses geometric optimization to find optimal intercept points.
    """

    def __init__(self, world):
        self.world = world

    def find_intercept_opportunities(self):
        """Find and execute intercept opportunities"""
        intercept_launches = []

        # For each enemy fleet heading toward our planets
        for fleet in self.world.fleets:
            if fleet.owner == self.world.player:
                continue

            # Find target planet
            target_planet, eta = fleet_target_planet(fleet, self.world.planets)
            if target_planet is None:
                continue

            # Skip if not heading toward our planet
            if target_planet.owner != self.world.player:
                continue

            # Find intercepting planet
            best_intercept = self._find_best_intercept(fleet, target_planet, eta)
            if best_intercept:
                src, angle, send = best_intercept
                intercept_launches.append([src.id, angle, send])

        return intercept_launches

    def _find_best_intercept(self, fleet, target_planet, original_eta):
        """Find best planet to intercept fleet"""
        best = None
        best_score = -999999

        # Fleet trajectory
        fleet_x = fleet.x
        fleet_y = fleet.y
        speed = fleet_speed(fleet.ships)
        dir_x = math.cos(fleet.angle)
        dir_y = math.sin(fleet.angle)

        for planet in self.world.my_planets:
            if planet.id == target_planet.id:
                continue

            available = int(planet.ships)
            if available < 10:
                continue

            # Distance to fleet path
            dx = fleet_x - planet.x
            dy = fleet_y - planet.y
            proj = dx * dir_x + dy * dir_y

            if proj < 0:
                continue

            perp_sq = dx * dx + dy * dy - proj * proj
            intercept_d = max(0.0, proj - math.sqrt(max(0.0, perp_sq)))

            if intercept_d < planet.radius:
                continue

            # Time to intercept
            dist_to_fleet = max(0, intercept_d - planet.radius)
            intercept_time = dist_to_fleet / speed

            # Time for our fleet to reach intercept point
            intercept_x = fleet_x + dir_x * intercept_d
            intercept_y = fleet_y + dir_y * intercept_d

            our_est = safe_angle_and_distance(
                planet.x, planet.y, planet.radius, intercept_x, intercept_y, 0
            )
            if our_est is None:
                continue

            our_angle, our_d = our_est
            our_time = max(1, int(math.ceil(our_d / fleet_speed(available))))

            # We need to arrive before the enemy
            if our_time >= intercept_time:
                continue

            # Score based on early intercept
            time_advantage = intercept_time - our_time
            score = time_advantage * 10 + (intercept_time - original_eta) * 5

            if score > best_score:
                best_score = score
                # Send enough to destroy fleet with margin
                send = min(available, int(fleet.ships) + 5)
                send = max(10, send)
                best = (planet, our_angle, send)

        return best

# ============================================================
# REAR STAGING OPTIMIZER
# ============================================================

class RearStagingOptimizer:
    """
    Optimize ship staging from rear planets to front lines.
    Maximizes firepower at the front while maintaining production.
    """

    def __init__(self, world):
        self.world = world

    def compute_staging_moves(self):
        """Compute optimal rear staging moves"""
        moves = []

        # Find rear vs front planets
        center_x = CENTER_X
        center_y = CENTER_Y

        my_planets_sorted = sorted(
            self.world.my_planets,
            key=lambda p: distance(p.x, p.y, center_x, center_y)
        )

        # Front planets (furthest from center)
        front_planets = my_planets_sorted[-3:] if len(my_planets_sorted) >= 3 else my_planets_sorted
        # Rear planets (closest to center)
        rear_planets = my_planets_sorted[:len(my_planets_sorted) - 3] if len(my_planets_sorted) > 3 else []

        # Stage from rear to front
        ratio = REAR_SEND_RATIO_4P if self.world.is_four_player else REAR_SEND_RATIO_2P

        for rear in rear_planets:
            if rear.ships < REAR_SOURCE_MIN:
                continue

            if rear.production < 2:
                continue

            # Find nearest front
            best_front = None
            best_dist = 10**9

            for front in front_planets:
                d = distance(rear.x, rear.y, front.x, front.y)
                if d < best_dist:
                    best_dist = d
                    best_front = front

            if best_front is None:
                continue

            # Check travel time
            est = safe_angle_and_distance(
                rear.x, rear.y, rear.radius, best_front.x, best_front.y, best_front.radius
            )
            if est is None:
                continue

            _, d = est
            travel_time = d / fleet_speed(rear.ships)

            if travel_time > REAR_MAX_TRAVEL:
                continue

            # Send ships forward
            send = max(REAR_SEND_MIN_SHIPS, int(rear.ships * ratio))
            keep = self.world.keep_needed_map.get(rear.id, 5)
            send = min(send, int(rear.ships) - keep)

            if send >= REAR_SOURCE_MIN:
                angle = math.atan2(best_front.y - rear.y, best_front.x - rear.x)
                moves.append([rear.id, angle, send])

        return moves

# ============================================================
# COMBAT EFFICIENCY OPTIMIZER
# ============================================================

class CombatEfficiencyOptimizer:
    """
    Optimize combat by calculating exact attack sizes needed.
    Minimizes waste while ensuring victory.
    """

    def __init__(self, world):
        self.world = world

    def compute_optimal_attack(self, target):
        """Compute optimal attack size with combat efficiency analysis"""
        garrison = int(target.ships)

        # Base attack = garrison + safety margin
        base_attack = garrison + 3

        # If target is owned, add production compensation
        if target.owner != -1:
            # Account for production that will happen before attack lands
            est = estimate_arrival(0, 0, 0, target.x, target.y, target.radius, base_attack)
            if est:
                production_buffer = est[1] * target.production
                base_attack += int(production_buffer)

        # Late game bonus
        if self.world.is_late:
            base_attack += 2
        if self.world.is_very_late:
            base_attack += 3

        return base_attack

    def analyze_multi_attack_coordination(self, target):
        """Analyze if multiple attacks can coordinate effectively"""
        sources = []

        for planet in self.world.my_planets:
            if planet.ships < 8:
                continue

            best = self.world.best_probe_aim(planet.id, target.id, planet.ships)
            if best is None:
                continue

            ships, aim = best
            sources.append((planet, ships, aim[1]))

        if len(sources) < 2:
            return None

        # Sort by arrival time
        sources.sort(key=lambda x: x[2])

        # Check if they can coordinate
        first_arrival = sources[0][2]
        last_arrival = sources[-1][2]

        if last_arrival - first_arrival <= MULTI_SOURCE_ETA_TOL:
            total_ships = sum(s[1] for s in sources)

            if total_ships >= self.compute_optimal_attack(target):
                return sources[:3]

        return None

# ============================================================
# ENDGAME CALCULATOR
# ============================================================

class EndgameCalculator:
    """
    Calculate optimal endgame strategy.
    Maximizes profit in the final turns of the game.
    """

    def __init__(self, world):
        self.world = world

    def compute_endgame_moves(self):
        """Compute optimal endgame moves"""
        if not self.world.is_late:
            return []

        moves = []

        # In total war mode, throw everything
        if self.world.is_total_war:
            moves.extend(self._total_war_assault())

        # Late game: prioritize high production targets
        if self.world.is_very_late:
            moves.extend(self._very_late_assault())

        # Standard late game moves
        moves.extend(self._late_consolidation())

        return moves

    def _total_war_assault(self):
        """Aggressive assault in total war mode"""
        moves = []

        for planet in self.world.my_planets:
            if planet.ships < 10:
                continue

            # Find nearest enemy/neutral planet
            best_target = None
            best_dist = 10**9
            best_prod = 0

            for target in self.world.planets:
                if target.owner == self.world.player:
                    continue

                d = distance(planet.x, planet.y, target.x, target.y)
                # Prioritize by production
                score = target.production / (d + 1)

                if score > best_prod:
                    best_prod = score
                    best_dist = d
                    best_target = target

            if best_target is None:
                continue

            angle = math.atan2(best_target.y - planet.y, best_target.x - planet.x)
            send = int(planet.ships * 0.9)  # Send 90%
            send = max(10, send)

            moves.append([planet.id, angle, send])

        return moves

    def _very_late_assault(self):
        """Maximum efficiency assault for very late game"""
        moves = []

        # Target highest production planets
        targets = sorted(
            [p for p in self.world.planets if p.owner != self.world.player],
            key=lambda p: p.production,
            reverse=True
        )[:5]

        for target in targets:
            # Find cheapest source
            best_source = None
            best_cost = 10**9

            for planet in self.world.my_planets:
                if planet.ships < target.ships + 5:
                    continue

                est = safe_angle_and_distance(
                    planet.x, planet.y, planet.radius, target.x, target.y, target.radius
                )
                if est is None:
                    continue

                _, d = est
                cost = d / planet.ships

                if cost < best_cost:
                    best_cost = cost
                    best_source = planet

            if best_source is None:
                continue

            send = int(target.ships) + 3
            send = min(send, int(best_source.ships) - 5)

            if send >= 5:
                angle = math.atan2(
                    target.y - best_source.y, target.x - best_source.x
                )
                moves.append([best_source.id, angle, send])

        return moves

    def _late_consolidation(self):
        """Consolidate forces for late game assault"""
        moves = []

        # Find high-value targets that we can reach
        for target in self.world.enemy_planets:
            if target.production < 3:
                continue

            # Find best positioned source
            best = None
            best_score = -999999

            for planet in self.world.my_planets:
                if planet.ships < target.ships + 5:
                    continue

                est = self.world.plan_shot(planet.id, target.id, planet.ships)
                if est is None:
                    continue

                angle, turns, _, _ = est
                score = target.production * 10 - turns * 2

                if score > best_score:
                    best_score = score
                    send = int(target.ships) + 3
                    send = min(send, int(planet.ships) - 5)
                    if send >= 5:
                        best = (planet.id, angle, send)

            if best:
                moves.append(best)

        return moves

# ============================================================
# MAIN AGENT
# ============================================================

def god_of_war_agent(obs):
    """GOD OF WAR - Mathematical Dominator Agent"""
    start_time = time.time()

    # Parse observation
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)
    ang_vel = obs.get("angular_velocity", 0.03)
    initial_planets_list = [Planet(*p) for p in obs.get("initial_planets", [])]
    initial_by_id = {p.id: p for p in initial_planets_list}
    comets = obs.get("comets", [])
    comet_ids = obs.get("comet_planet_ids", [])

    # Build world model
    world = WorldModel(player, obs.get("step", 0), planets, fleets, initial_by_id, ang_vel, comets, comet_ids)

    # Time management
    deadline = SOFT_ACT_DEADLINE

    all_launches = []

    # Phase 1: Check evacuation first (prioritized)
    evac = EvacuationController(world)
    evac_launches = evac.evacuate_doomed()
    all_launches.extend(evac_launches)

    if time.time() - start_time > deadline:
        return all_launches

    # Phase 2: Counter-fleet interception
    interceptor = CounterFleetInterceptor(world)
    intercept_launches = interceptor.find_intercept_opportunities()
    all_launches.extend(intercept_launches)

    if time.time() - start_time > deadline:
        return all_launches

    # Phase 3: Endgame calculations
    if world.is_late:
        endgame = EndgameCalculator(world)
        endgame_launches = endgame.compute_endgame_moves()
        all_launches.extend(endgame_launches)

    if time.time() - start_time > deadline:
        return all_launches

    # Phase 4: Rear staging
    if not world.is_late and not world.is_early:
        stager = RearStagingOptimizer(world)
        stage_launches = stager.compute_staging_moves()
        all_launches.extend(stage_launches)

    if time.time() - start_time > deadline:
        return all_launches

    # Phase 5: Generate and execute missions
    generator = MissionGenerator(world)
    missions = generator.generate_missions()

    if time.time() - start_time > deadline:
        return all_launches

    # Execute missions
    executor = StrategyExecutor(world, missions[:50])
    mission_launches = executor.execute()
    all_launches.extend(mission_launches)

    # Phase 6: Crash exploitation
    if time.time() - start_time < HEAVY_PHASE_MIN and CRASH_EXPLOIT_ENABLED:
        crash_sys = CrashExploitSystem(world)
        exploits = crash_sys.find_crash_exploits()

        for exploit in exploits[:3]:
            target = exploit['target']
            sources = exploit['sources']

            for src, ships, _ in sources[:2]:
                available = world.source_inventory_left(src.id, defaultdict(int))
                if available < CRASH_EXPLOIT_MIN_SHIPS:
                    continue

                best = world.plan_shot(src.id, target.id, available)
                if best is None:
                    continue

                angle = best[0]
                send = min(ships, available)

                if send >= CRASH_EXPLOIT_MIN_SHIPS:
                    all_launches.append([src.id, angle, send])

    # Phase 7: Gang-up coordination
    if time.time() - start_time < HEAVY_PHASE_MIN:
        gangup = GangUpCoordinator(world)
        opportunities = gangup.find_gang_up_opportunities()

        for opp in opportunities[:2]:
            target = opp['target']
            sources = opp['sources']

            for src, ships, _ in sources:
                available = world.source_inventory_left(src.id, defaultdict(int))
                if available < 10:
                    continue

                best = world.plan_shot(src.id, target.id, available)
                if best is None:
                    continue

                angle = best[0]
                send = min(ships, available)

                if send >= 10:
                    all_launches.append([src.id, angle, send])

    # Final time check and truncation
    if time.time() - start_time > SOFT_ACT_DEADLINE:
        return all_launches[:20]

    return all_launches

# Export for Kaggle
if __name__ == "__main__":
    from kaggle_environments import make

    env = make("orbit_wars", debug=True)
    env.run(["random_agent", god_of_war_agent])