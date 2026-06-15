"""
enemy_ai.py — AI логика врагов: state machine, patrol, search, shoot.
Все функции принимают enemy: Enemy как первый аргумент.
"""
import pygame
import math


def update_state(enemy, dt: float) -> None:
    from actors.enemy import EnemyState
    s = enemy.state

    if s == EnemyState.IDLE:
        if enemy.can_see_target():
            enemy._last_known_pos = pygame.math.Vector2(enemy.target.pos)
            enemy.state = EnemyState.CHASE

    elif s == EnemyState.CHASE:
        if enemy.can_see_target():
            enemy._last_known_pos = pygame.math.Vector2(enemy.target.pos)
        else:
            enemy.state                   = EnemyState.SEARCH
            enemy._search_rotate_timer    = enemy.SEARCH_ROTATE_TIME
            enemy._path                   = []

    elif s == EnemyState.SEARCH:
        if enemy.can_see_target():
            enemy._last_known_pos = pygame.math.Vector2(enemy.target.pos)
            enemy.state = EnemyState.CHASE

    elif s == EnemyState.ALERT:
        enemy._alert_timer -= dt
        if enemy.can_see_target():
            enemy._alert_react_timer -= dt
            if enemy._alert_react_timer <= 0:
                enemy._last_known_pos = pygame.math.Vector2(enemy.target.pos)
                enemy.state = EnemyState.CHASE
        else:
            enemy._alert_react_timer = enemy.ALERT_REACT_DELAY
        if enemy._alert_timer <= 0:
            enemy.state = EnemyState.IDLE


def ai_grunt(enemy, dt: float) -> None:
    from actors.enemy import EnemyState
    if enemy.state == EnemyState.IDLE:
        do_patrol(enemy, dt)
    elif enemy.state == EnemyState.CHASE:
        follow_path_to(enemy, enemy.target.pos, dt)
    elif enemy.state == EnemyState.SEARCH:
        do_search(enemy, dt)
    elif enemy.state == EnemyState.ALERT:
        enemy.velocity.update(0, 0)
        do_alert_rotate(enemy, dt)


def ai_shooter(enemy, dt: float) -> None:
    from actors.enemy import EnemyState
    if enemy.state == EnemyState.IDLE:
        do_patrol(enemy, dt)
        return
    elif enemy.state == EnemyState.SEARCH:
        do_search(enemy, dt)
        return
    elif enemy.state == EnemyState.ALERT:
        enemy.velocity.update(0, 0)
        do_alert_rotate(enemy, dt)
        return

    delta = enemy.target.pos - enemy.pos
    dist  = delta.length()

    if dist > enemy._preferred_dist + 40:
        follow_path_to(enemy, enemy.target.pos, dt)
    elif dist < enemy._preferred_dist - 40:
        if dist > 1:
            enemy.velocity = -delta.normalize() * enemy.speed
    else:
        if dist > 1:
            direction = delta.normalize()
            perp      = pygame.math.Vector2(-direction.y, direction.x)
            enemy.velocity = perp * enemy.speed * 0.6

    enemy._shoot_cooldown = max(0.0, enemy._shoot_cooldown - dt)
    if enemy._shoot_cooldown <= 0 and dist < enemy._preferred_dist + 120:
        enemy._fire()
        enemy._shoot_cooldown = enemy._shoot_rate


def do_patrol(enemy, dt: float) -> None:
    if not enemy._patrol_points:
        enemy.velocity.update(0, 0)
        return
    target = enemy._patrol_points[enemy._patrol_index]
    dist   = (enemy.pos - target).length()
    if dist < enemy.tile_size // 2:
        enemy._patrol_index = (enemy._patrol_index + 1) % len(enemy._patrol_points)
        enemy._path         = []
        enemy._path_timer   = 0.0
    else:
        follow_path_to(enemy, target, dt)


def do_search(enemy, dt: float) -> None:
    dist_to_last = (enemy.pos - enemy._last_known_pos).length()
    if dist_to_last > 12:
        follow_path_to(enemy, enemy._last_known_pos, dt)
    else:
        enemy.velocity.update(0, 0)
        enemy._search_rotate_timer -= dt
        enemy._facing_angle        += enemy.ROTATE_SPEED * dt
        angle_rad    = math.radians(enemy._facing_angle)
        enemy.facing = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))
        if enemy._search_rotate_timer <= 0:
            from actors.enemy import EnemyState
            enemy.state              = EnemyState.ALERT
            enemy._alert_timer       = enemy.ALERT_TIMEOUT
            enemy._alert_react_timer = enemy.ALERT_REACT_DELAY


def do_alert_rotate(enemy, dt: float) -> None:
    enemy._facing_angle += enemy.ROTATE_SPEED * 0.3 * dt
    angle_rad    = math.radians(enemy._facing_angle)
    enemy.facing = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))


def follow_path_to(enemy, destination: pygame.math.Vector2, dt: float) -> None:
    enemy._path_timer -= dt
    if enemy._path_timer <= 0:
        enemy._path_timer = enemy._path_interval
        if enemy.pathfinder:
            enemy._path = enemy.pathfinder.find_path(enemy.pos, destination)

    if not enemy._path:
        delta = destination - enemy.pos
        if delta.length() > 1:
            enemy.velocity = delta.normalize() * enemy.speed
        else:
            enemy.velocity.update(0, 0)
        return

    next_point = enemy._path[1] if len(enemy._path) > 1 else enemy._path[0]
    delta      = next_point - enemy.pos
    if delta.length() < enemy.speed * dt + 4 and len(enemy._path) > 1:
        enemy._path.pop(0)
    if delta.length() > 1:
        enemy.velocity = delta.normalize() * enemy.speed
    else:
        enemy.velocity.update(0, 0)
