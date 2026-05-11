#!/usr/bin/env python3
"""
AGGRESSOR V2 - Blitzkrieg tactics to overwhelm agentrl.py

Key changes from V1:
1. Focus swarms on ONE target at a time (stronger than distributed attacks)
2. Capture ALL nearby neutrals in opening (don't skip)
3. Use cooperative attacks on closest enemy planets
4. Commit more ships per attack (80%+ of available)
5. Ignore defensive reserves - go all-in on offense
"""

import math
from kaggle_environments.envs.orbit_wars import orbit_wars as ow

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_R = 10.0
MAX_SPEED = 6.0

_step = 0


def fleet_speed(ships):
    ships = max(1, ships)
    ratio = math.log(ships) / math.log(1000.0)
    ratio = max(0.0, min(1.0, ratio))
    return 1.0 + (MAX_SPEED - 1.0) * (ratio ** 1.5)


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def segment_dist(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-9:
        return dist(px, py, x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return dist(px, py, x1 + t * dx, y1 + t * dy)


def try_angle(sx, sy, sr, tx, ty, tr):
    """Get angle to target or None if sun collision."""
    angle = math.atan2(ty - sy, tx - sx)
    start_x = sx + math.cos(angle) * (sr + 0.05)
    start_y = sy + math.sin(angle) * (sr + 0.05)
    travel = max(0.1, dist(sx, sy, tx, ty) - sr - tr - 0.1)
    end_x = start_x + math.cos(angle) * travel
    end_y = start_y + math.sin(angle) * travel
    
    if segment_dist(CENTER_X, CENTER_Y, start_x, start_y, end_x, end_y) < SUN_R + 1.0:
        return None
    return angle


def agent(obs):
    global _step
    _step += 1
    
    planets = [ow.Planet(*p) for p in obs.get('planets', [])]
    fleets = [ow.Fleet(*f) for f in obs.get('fleets', [])]
    player = obs.get('player', 0)
    
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    
    if not my_planets or not targets:
        return []
    
    moves = []
    allocated = set()
    
    # ========== PHASE 1: CAPTURE ALL NEARBY NEUTRALS (Turns 1-20) ==========
    if _step <= 20:
        neutrals = [t for t in targets if t.owner == -1]
        
        for tgt in sorted(neutrals, key=lambda p: dist(my_planets[0].x, my_planets[0].y, p.x, p.y)):
            # Find cheapest planet to capture from
            best_src = None
            best_cost = float('inf')
            
            for src in my_planets:
                ships_needed = tgt.ships + 1
                cost = dist(src.x, src.y, tgt.x, tgt.y) + ships_needed * 0.1
                
                if src.ships >= ships_needed * 1.5 and cost < best_cost:
                    best_cost = cost
                    best_src = src
            
            if best_src is not None:
                angle = try_angle(best_src.x, best_src.y, best_src.radius, tgt.x, tgt.y, tgt.radius)
                if angle is not None:
                    ships_needed = tgt.ships + 1
                    moves.append([best_src.id, angle, ships_needed])
                    allocated.add(best_src.id)
    
    # ========== PHASE 2: FOCUS SWARM ON CLOSEST ENEMY ==========
    # Find the closest enemy planet from our center of mass
    avg_x = sum(p.x for p in my_planets) / len(my_planets)
    avg_y = sum(p.y for p in my_planets) / len(my_planets)
    
    enemy_targets = sorted(
        [t for t in targets if t.owner != -1],
        key=lambda p: dist(avg_x, avg_y, p.x, p.y)
    )
    
    if enemy_targets:
        primary_target = enemy_targets[0]
        
        # Send swarms from multiple planets to primary target
        contributing = 0
        total_incoming = 0
        
        for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
            if src.id in allocated:
                continue
            
            available = src.ships
            if available < 4:
                continue
            
            # Send 70-90% of available ships
            to_send = int(available * 0.8)
            
            angle = try_angle(src.x, src.y, src.radius, primary_target.x, primary_target.y, primary_target.radius)
            if angle is not None:
                moves.append([src.id, angle, to_send])
                allocated.add(src.id)
                contributing += 1
                total_incoming += to_send
                
                if contributing >= 3:  # Concentrate from max 3 planets
                    break
    
    # ========== PHASE 3: OPPORTUNISTIC ATTACKS FROM REMAINING PLANETS ==========
    for src in my_planets:
        if src.id in allocated:
            continue
        
        available = src.ships
        if available < 3:
            continue
        
        # Find nearest target
        nearest = min(targets, key=lambda p: dist(src.x, src.y, p.x, p.y))
        
        angle = try_angle(src.x, src.y, src.radius, nearest.x, nearest.y, nearest.radius)
        if angle is not None:
            to_send = max(3, int(available * 0.6))
            moves.append([src.id, angle, to_send])
            allocated.add(src.id)
    
    return moves


__all__ = ['agent']
