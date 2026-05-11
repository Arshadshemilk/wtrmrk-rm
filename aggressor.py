#!/usr/bin/env python3
"""
AGGRESSOR - Beats agentrl.py through early rushing and relentless pressure.

Key insights:
1. Agentrl.py does complex calculations - this is SLOW
2. Early territory control wins the game
3. Simple greedy heuristics are faster and more decisive
4. Swarm attacks overwhelm defensive calculations
5. Don't plan - just attack from everything, everywhere, immediately

Strategy:
- Turn 1-15: RUSH all neutral planets with minimal viable forces
- Turn 16+: Swarm attack closest/highest-production enemy planets
- Reinforce only doomed planets at the last second
- Ignore complex trajectory tracking - just send 60-turn fleets blindly
"""

import math
from kaggle_environments.envs.orbit_wars import orbit_wars as ow

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_R = 10.0
MAX_SPEED = 6.0

_step = 0


def fleet_speed(ships):
    """Log-scaled speed from 1 to 6 ships/turn."""
    ships = max(1, ships)
    ratio = math.log(ships) / math.log(1000.0)
    ratio = max(0.0, min(1.0, ratio))
    return 1.0 + (MAX_SPEED - 1.0) * (ratio ** 1.5)


def dist(ax, ay, bx, by):
    """Euclidean distance."""
    return math.hypot(ax - bx, ay - by)


def segment_dist_to_point(px, py, x1, y1, x2, y2):
    """Closest distance from point to line segment."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-9:
        return dist(px, py, x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return dist(px, py, closest_x, closest_y)


def safe_launch_angle(sx, sy, sr, tx, ty, tr):
    """
    Get angle to target, checking for sun collision.
    Returns (angle, travel_distance) or None if hits sun.
    """
    angle = math.atan2(ty - sy, tx - sx)
    
    # Approximate travel distance
    travel_dist = max(0.1, dist(sx, sy, tx, ty) - sr - tr - 0.1)
    
    # Launch from planet surface
    start_x = sx + math.cos(angle) * (sr + 0.05)
    start_y = sy + math.sin(angle) * (sr + 0.05)
    
    # End point of trajectory
    end_x = start_x + math.cos(angle) * travel_dist
    end_y = start_y + math.sin(angle) * travel_dist
    
    # Check sun collision
    if segment_dist_to_point(CENTER_X, CENTER_Y, start_x, start_y, end_x, end_y) < SUN_R + 1.0:
        return None
    
    return angle, travel_dist


def estimate_eta(sx, sy, sr, tx, ty, tr, ships):
    """Estimate turns to arrival."""
    result = safe_launch_angle(sx, sy, sr, tx, ty, tr)
    if result is None:
        return None
    angle, travel_dist = result
    speed = fleet_speed(ships)
    eta = max(1, int(math.ceil(travel_dist / speed)))
    return eta


def greedy_score_target(src, tgt, ships, step):
    """
    Simple greedy scoring: prioritize high production and nearby planets.
    Enemy planets are worth 3x neutral planets.
    Early game: extra bonus for neutral planets (rush phase).
    """
    base_value = tgt.production * 10
    
    if tgt.owner == -1:
        # Neutral: base value
        base_value += 20
        if step <= 15:
            base_value += 50  # Early rush bonus for neutrals
    else:
        # Enemy: 3x value boost
        base_value *= 3
        base_value += 30
    
    # Cost: distance and ship count
    distance_cost = dist(src.x, src.y, tgt.x, tgt.y) * 0.5
    garrison_cost = tgt.ships * 0.3
    
    # ETA factor (prefer fast arrivals)
    eta = estimate_eta(src.x, src.y, src.radius, tgt.x, tgt.y, tgt.radius, ships)
    if eta is None:
        return None  # Sun collision
    
    eta_cost = eta * 0.2  # Penalize slow arrivals
    
    score = base_value - distance_cost - garrison_cost - eta_cost
    return score


def agent(obs):
    """Main agent function."""
    global _step
    _step += 1
    
    # Parse observation
    planets = [ow.Planet(*p) for p in obs.get('planets', [])]
    fleets = [ow.Fleet(*f) for f in obs.get('fleets', [])]
    player = obs.get('player', 0)
    
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    
    if not my_planets or not targets:
        return []
    
    moves = []
    used_planet_ids = set()
    
    # ========== EARLY RUSH PHASE (Turns 1-15) ==========
    if _step <= 15:
        # Prioritize neutral planets
        neutral_targets = sorted(
            [t for t in targets if t.owner == -1],
            key=lambda p: (p.production, -p.ships),
            reverse=True
        )
        
        for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
            if src.id in used_planet_ids:
                continue
            
            for tgt in neutral_targets:
                ships_needed = tgt.ships + 1
                if src.ships < ships_needed + 1:
                    continue
                
                result = safe_launch_angle(src.x, src.y, src.radius, tgt.x, tgt.y, tgt.radius)
                if result is None:
                    continue
                
                angle, _ = result
                moves.append([src.id, angle, ships_needed])
                used_planet_ids.add(src.id)
                break
    
    # ========== SWARM PHASE (All turns, especially after rush) ==========
    # Sort targets by priority: closest, highest production
    priority_targets = sorted(
        targets,
        key=lambda p: (
            -p.production if p.owner != -1 else -p.production * 0.5,
            dist(my_planets[0].x, my_planets[0].y, p.x, p.y)
        )
    )
    
    for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        if src.id in used_planet_ids:
            continue
        
        available = max(0, src.ships - 1)  # Keep 1 ship buffer
        if available < 3:
            continue
        
        best_target = None
        best_score = -1e9
        best_ships = 0
        best_angle = 0
        
        for tgt in priority_targets:
            # Try different ship counts
            for ships_to_send in [available // 2, available, min(20, available)]:
                if ships_to_send < 3:
                    continue
                
                score = greedy_score_target(src, tgt, ships_to_send, _step)
                if score is None:
                    continue
                
                if score > best_score:
                    best_score = score
                    best_target = tgt
                    best_ships = ships_to_send
                    result = safe_launch_angle(src.x, src.y, src.radius, tgt.x, tgt.y, tgt.radius)
                    if result:
                        best_angle, _ = result
        
        if best_target is not None and best_ships > 0:
            moves.append([src.id, best_angle, best_ships])
            used_planet_ids.add(src.id)
    
    return moves


__all__ = ['agent']
