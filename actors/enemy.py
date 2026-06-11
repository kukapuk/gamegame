import pygame
import math
from actors.actor import Actor
from items.stats import Stats


class EnemyState:
    IDLE  = "idle"
    CHASE = "chase"


class Enemy(Actor):
    """
    Базовый враг. Поведение определяется стейт-машиной.
    Состояния: IDLE (стоит) → CHASE (преследует).
    Зона видения: треугольник 125° на дистанцию vision_range.
    Raycast проверяет стены — если стена перекрывает, игрок не виден.
    Один раз увидел — преследует до конца (агр не сбрасывается).
    """

    KNOCKBACK_FRICTION = 8.0
    VISION_ANGLE       = 125.0
    VISION_RANGE       = 280.0
    DEBUG_COLOR_IDLE   = (80, 200, 80, 40)
    DEBUG_COLOR_CHASE  = (220, 80, 80, 40)
    DEBUG_RAY_COLOR    = (255, 255, 100, 120)

    def __init__(
        self,
        pos: tuple[float, float],
        target: Actor,
        armor_class: int = 0,
        groups: list = (),
    ) -> None:
        super().__init__(
            pos=pos,
            size=28,
            color=(220, 60, 60),
            groups=groups,
        )
        self.target      = target
        self.armor_class = armor_class
        self.walls       = None

        self.stats = Stats(
            max_hp=60,
            speed=120.0,
            dash_cooldown=999,
            dash_stamina_cost=999,
        )
        self.hp     = self.stats.max_hp
        self.max_hp = self.stats.max_hp
        self.speed  = self.stats.speed

        self._contact_cooldown: float = 0.0
        self._stun_timer: float       = 0.0
        self._knockback_vel           = pygame.math.Vector2(0, 0)

        self.state      = EnemyState.IDLE
        self._ai_update = self._ai_grunt

        self.can_shoot: bool        = False
        self._shoot_cooldown: float = 0.0
        self._shoot_rate: float     = 0.0
        self._preferred_dist: float = 0.0
        self._bullet_group          = None
        self._all_sprites           = None
        self._bullet_speed: float   = 0.0
        self._bullet_damage: int    = 0
        self._bullet_color: tuple   = (255, 200, 50)

        self.vision_range: float = self.VISION_RANGE
        self.vision_angle: float = self.VISION_ANGLE

    def apply_stopping_effect(self, bullet_direction: pygame.math.Vector2, stopping_effect: float) -> None:
        self._knockback_vel = bullet_direction.normalize() * stopping_effect * 420.0
        self._stun_timer    = stopping_effect * 0.45

    def try_deal_contact_damage(self, target: Actor, damage: int, cooldown: float) -> None:
        if self._contact_cooldown > 0:
            return
        if self.rect.colliderect(target.rect):
            target.take_damage(damage)
            self._contact_cooldown = cooldown

    def hear_sound(self, world_pos: pygame.math.Vector2, radius: float) -> None:
        if self.state == EnemyState.CHASE:
            return
        if (self.pos - world_pos).length() <= radius:
            self.state = EnemyState.CHASE

    def can_see_target(self) -> bool:
        delta = self.target.pos - self.pos
        dist  = delta.length()
        if dist > self.vision_range:
            return False

        angle_to_target = math.degrees(math.atan2(delta.y, delta.x))
        facing_angle    = math.degrees(math.atan2(self.facing.y, self.facing.x))
        diff = (angle_to_target - facing_angle + 180) % 360 - 180
        if abs(diff) > self.vision_angle / 2:
            return False

        return not self._ray_hits_wall(self.pos, self.target.pos)

    def _ray_hits_wall(
        self,
        start: pygame.math.Vector2,
        end: pygame.math.Vector2,
    ) -> bool:
        if not self.walls:
            return False
        for wall in self.walls:
            if _segment_intersects_rect(start, end, wall.rect):
                return True
        return False

    def _update_facing(self) -> None:
        if self.velocity.length() > 0.5:
            self.facing = self.velocity.normalize()

    def _update_state(self) -> None:
        if self.state == EnemyState.IDLE:
            if self.can_see_target():
                self.state = EnemyState.CHASE

    def _ai_grunt(self, dt: float) -> None:
        if self.state == EnemyState.IDLE:
            self.velocity.update(0, 0)
            return
        delta = self.target.pos - self.pos
        if delta.length() > 1:
            self.velocity = delta.normalize() * self.speed
        else:
            self.velocity.update(0, 0)

    def _ai_shooter(self, dt: float) -> None:
        if self.state == EnemyState.IDLE:
            self.velocity.update(0, 0)
            return

        delta = self.target.pos - self.pos
        dist  = delta.length()

        if dist > 1:
            direction = delta.normalize()
            if dist > self._preferred_dist + 40:
                self.velocity = direction * self.speed
            elif dist < self._preferred_dist - 40:
                self.velocity = -direction * self.speed
            else:
                perp = pygame.math.Vector2(-direction.y, direction.x)
                self.velocity = perp * self.speed

        self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
        if self._shoot_cooldown <= 0 and dist < self._preferred_dist + 120:
            self._fire()
            self._shoot_cooldown = self._shoot_rate

    def _fire(self) -> None:
        if self._bullet_group is None:
            return
        delta = self.target.pos - self.pos
        if delta.length() == 0:
            return
        self._spawn_bullet(delta.normalize())

    def _spawn_bullet(self, direction: pygame.math.Vector2) -> None:
        from combat.bullet import Bullet
        groups = [self._bullet_group]
        if self._all_sprites:
            groups.append(self._all_sprites)
        Bullet(
            pos=(self.pos.x, self.pos.y),
            direction=direction,
            speed=self._bullet_speed,
            lifetime=3.0,
            damage=self._bullet_damage,
            size=6,
            color=self._bullet_color,
            stopping_effect=0.0,
            groups=groups,
        )

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        super().draw_debug(surface, camera_offset)
        self._draw_vision_cone(surface, camera_offset)

    def _draw_vision_cone(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        cx = round(self.pos.x - camera_offset.x)
        cy = round(self.pos.y - camera_offset.y)

        facing_angle = math.degrees(math.atan2(self.facing.y, self.facing.x))
        half         = self.vision_angle / 2
        r            = self.vision_range
        steps        = 16

        color = self.DEBUG_COLOR_CHASE if self.state == EnemyState.CHASE else self.DEBUG_COLOR_IDLE

        points = [(cx, cy)]
        for i in range(steps + 1):
            a   = math.radians(facing_angle - half + (self.vision_angle / steps) * i)
            end = pygame.math.Vector2(self.pos.x + math.cos(a) * r,
                                      self.pos.y + math.sin(a) * r)
            if self.walls and self._ray_hits_wall(self.pos, end):
                for wall in self.walls:
                    hit = _ray_rect_hit_point(self.pos, end, wall.rect)
                    if hit:
                        end = hit
                        break
            points.append((round(end.x - camera_offset.x), round(end.y - camera_offset.y)))

        if len(points) >= 3:
            cone_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(cone_surf, color, points)
            surface.blit(cone_surf, (0, 0))

        ray_end = self.target.pos
        blocked = self._ray_hits_wall(self.pos, self.target.pos)
        ray_color = (255, 80, 80, 180) if blocked else (80, 255, 80, 180)
        pygame.draw.line(surface, ray_color[:3],
                         (cx, cy),
                         (round(ray_end.x - camera_offset.x),
                          round(ray_end.y - camera_offset.y)), 1)

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        if walls is not None:
            self.walls = walls
        self._contact_cooldown = max(0.0, self._contact_cooldown - dt)
        if self._stun_timer > 0:
            self._stun_timer -= dt
            self._knockback_vel *= max(0.0, 1.0 - self.KNOCKBACK_FRICTION * dt)
            self.velocity = self._knockback_vel.copy()
        else:
            self._knockback_vel.update(0, 0)
            self._update_state()
            self._update_facing()
            self._ai_update(dt)
        super().update(dt, walls)


def _segment_intersects_rect(
    p1: pygame.math.Vector2,
    p2: pygame.math.Vector2,
    rect: pygame.Rect,
) -> bool:
    left   = rect.left
    right  = rect.right
    top    = rect.top
    bottom = rect.bottom

    edges = [
        ((left,  top),    (right, top)),
        ((right, top),    (right, bottom)),
        ((right, bottom), (left,  bottom)),
        ((left,  bottom), (left,  top)),
    ]
    for a, b in edges:
        if _segments_intersect(p1, p2,
                               pygame.math.Vector2(a),
                               pygame.math.Vector2(b)):
            return True
    return False


def _segments_intersect(
    p1: pygame.math.Vector2, p2: pygame.math.Vector2,
    p3: pygame.math.Vector2, p4: pygame.math.Vector2,
) -> bool:
    d1 = p2 - p1
    d2 = p4 - p3
    cross = d1.x * d2.y - d1.y * d2.x
    if abs(cross) < 1e-10:
        return False
    d3  = p3 - p1
    t   = (d3.x * d2.y - d3.y * d2.x) / cross
    u   = (d3.x * d1.y - d3.y * d1.x) / cross
    return 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0


def _ray_rect_hit_point(
    origin: pygame.math.Vector2,
    end: pygame.math.Vector2,
    rect: pygame.Rect,
) -> pygame.math.Vector2 | None:
    left, right, top, bottom = rect.left, rect.right, rect.top, rect.bottom
    edges = [
        ((left,  top),    (right, top)),
        ((right, top),    (right, bottom)),
        ((right, bottom), (left,  bottom)),
        ((left,  bottom), (left,  top)),
    ]
    closest     = None
    closest_t   = float("inf")
    d1 = end - origin
    for a, b in edges:
        p3 = pygame.math.Vector2(a)
        p4 = pygame.math.Vector2(b)
        d2 = p4 - p3
        cross = d1.x * d2.y - d1.y * d2.x
        if abs(cross) < 1e-10:
            continue
        d3 = p3 - origin
        t  = (d3.x * d2.y - d3.y * d2.x) / cross
        u  = (d3.x * d1.y - d3.y * d1.x) / cross
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0 and t < closest_t:
            closest_t = t
            closest   = origin + d1 * t
    return closest


def make_grunt(pos, target, armor_class: int = 0, groups: list = ()) -> Enemy:
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    return e


def make_shooter(
    pos,
    target,
    armor_class: int = 0,
    groups: list = (),
    bullet_group=None,
    all_sprites=None,
) -> Enemy:
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((180, 80, 220))
    e.stats.max_hp = 40
    e.hp           = 40
    e.max_hp       = 40
    e.speed        = 90.0

    e.can_shoot         = True
    e._shoot_rate       = 1.2
    e._shoot_cooldown   = 1.2
    e._preferred_dist   = 220.0
    e._bullet_speed     = 380.0
    e._bullet_damage    = 8
    e._bullet_color     = (220, 100, 255)
    e._bullet_group     = bullet_group
    e._all_sprites      = all_sprites
    e._ai_update        = e._ai_shooter

    return e
