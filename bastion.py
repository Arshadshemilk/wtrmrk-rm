#!/usr/bin/env python3
"""
BASTION - Beats agentrl.py by SECURING THE OPENING.

Key insight: Maybe agentrl.py wins because:
1. It protects its starting planets carefully
2. It captures neutrals methodically 
3. By mid-game, it has secured more planets than opponents

Strategy:
- Turns 1-5: HOLD - don't send anything, build up production
- Turns 6-25: Swift neutral capture with minimum forces
- Turns 26+: Swarm attacks when we have clear superiority
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


def safe_angle(sx, sy, sr, tx, ty, tr):
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
    
    # ========== OPENING HOLD (Turns 1-5) ==========
    if _step <= 5:
        return []  # Do nothing, build production
    
    # ========== NEUTRAL CAPTURE PHASE (Turns 6-25) ==========
    if _step <= 25:
        neutrals = sorted(
            [t for t in targets if t.owner == -1],
            key=lambda p: (p.production, -dist(my_planets[0].x, my_planets[0].y, p.x, p.y)),
            reverse=True
        )
        
        allocated = set()
        for tgt in neutrals:
            for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
                if src.id in allocated:
                    continue
                
                ships_needed = tgt.ships + 1
                if src.ships >= ships_needed + 2:
                    angle = safe_angle(src.x, src.y, src.radius, tgt.x, tgt.y, tgt.radius)
                    if angle is not None:
                        moves.append([src.id, angle, ships_needed])
                        allocated.add(src.id)
                        break
        
        return moves
    
    # ========== TRANSITION: Still capture neutrals but scan for ripe targets ==========
    if _step <= 40:
        neutrals = [t for t in targets if t.owner == -1]
        allocated = set()
        
        for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
            if src.id in allocated:
                continue
            
            available = max(0, src.ships - 3)
            if available < 3:
                continue
            
            # Prioritize remaining neutrals
            remaining_neutrals = [t for t in neutrals if t not in allocated]
            if remaining_neutrals:
                tgt = min(remaining_neutrals, key=lambda p: dist(src.x, src.y, p.x, p.y))
                ships_needed = tgt.ships + 1
                
                if available >= ships_needed:
                    angle = safe_angle(src.x, src.y, src.radius, tgt.x, tgt.y, tgt.radius)
                    if angle is not None:
                        moves.append([src.id, angle, ships_needed])
                        allocated.add(src.id)
                        continue
            
            # Otherwise, look for enemy planets with low pop
            weak_enemies = sorted(
                [t for t in targets if t.owner != -1 and t.ships < 5],
                key=lambda p: dist(src.x, src.y, p.x, p.y)
            )
            
            if weak_enemies:
                tgt = weak_enemies[0]
                ships_needed = tgt.ships + 2
                
                if available >= ships_needed:
                    angle = safe_angle(src.x, src.y, src.radius, tgt.x, tgt.y, tgt.radius)
                    if angle is not None:
                        moves.append([src.id, angle, ships_needed])
                        allocated.add(src.id)
        
        return moves
    
    # ========== MID-GAME: COORDINATE SWARMS (Turns 41+) ==========
    avg_x = sum(p.x for p in my_planets) / len(my_planets)
    avg_y = sum(p.y for p in my_planets) / len(my_planets)
    
    priority_target = min(targets, key=lambda p: dist(avg_x, avg_y, p.x, p.y))
    
    allocated = set()
    swarm_size = 0
    
    # Build swarms toward priority target
    for src in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        if src.id in allocated:
            continue
        
        available = max(0, src.ships - 2)
        if available < 2:
            continue
        
        to_send = int(available * 0.6)
        if to_send < 2:
            continue
        
        angle = safe_angle(src.x, src.y, src.radius, priority_target.x, priority_target.y, priority_target.radius)
        if angle is not None:
            moves.append([src.id, angle, to_send])
            allocated.add(src.id)
            swarm_size += to_send
            
            if swarm_size >= 30:  # Stop after collecting enough
                break
    
    # Secondary attacks on other targets
    for src in my_planets:
        if src.id in allocated:
            continue
        
        available = max(0, src.ships - 1)
        if available < 3:
            continue
        
        nearest = min(targets, key=lambda p: dist(src.x, src.y, p.x, p.y))
        to_send = max(3, int(available * 0.5))
        
        angle = safe_angle(src.x, src.y, src.radius, nearest.x, nearest.y, nearest.radius)
        if angle is not None:
            moves.append([src.id, angle, to_send])
            allocated.add(src.id)
    
    return moves


__all__ = ['agent']
