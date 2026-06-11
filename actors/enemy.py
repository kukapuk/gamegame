import pygame
from actors.actor import Actor
from items.stats import Stats


class Enemy(Actor):
    """
    Базовый враг. Поведение определяется стейт-машиной через _ai_update.
    Grunt: всегда chase. Shooter: держит дистанцию, стреляет.
    """

    KNOCKBACK_FRICTION = 8.0

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

        self._ai_update = self._ai_chase

        self.can_shoot: bool        = False
        self._shoot_cooldown: float = 0.0
        self._shoot_rate: float     = 0.0
        self._preferred_dist: float = 0.0
        self._bullet_group          = None
        self._all_sprites           = None
        self._bullet_speed: float   = 0.0
        self._bullet_damage: int    = 0
        self._bullet_color: tuple   = (255, 200, 50)

    def apply_stopping_effect(self, bullet_direction: pygame.math.Vector2, stopping_effect: float) -> None:
        self._knockback_vel = bullet_direction.normalize() * stopping_effect * 420.0
        self._stun_timer    = stopping_effect * 0.45

    def try_deal_contact_damage(self, target: Actor, damage: int, cooldown: float) -> None:
        if self._contact_cooldown > 0:
            return
        if self.rect.colliderect(target.rect):
            target.take_damage(damage)
            self._contact_cooldown = cooldown

    def _ai_chase(self, dt: float) -> None:
        delta = self.target.pos - self.pos
        if delta.length() > 1:
            self.velocity = delta.normalize() * self.speed
        else:
            self.velocity.update(0, 0)

    def _ai_shooter(self, dt: float) -> None:
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
        direction = delta.normalize()
        self._spawn_bullet(direction)

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

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        self._contact_cooldown = max(0.0, self._contact_cooldown - dt)
        if self._stun_timer > 0:
            self._stun_timer -= dt
            self._knockback_vel *= max(0.0, 1.0 - self.KNOCKBACK_FRICTION * dt)
            self.velocity = self._knockback_vel.copy()
        else:
            self._knockback_vel.update(0, 0)
            self._ai_update(dt)
        super().update(dt, walls)


def _bullet_update(b, dt: float) -> None:
    b.lifetime -= dt
    if b.lifetime <= 0:
        b.kill()
        return
    b.pos += b.velocity * dt
    b.rect.center = (round(b.pos.x), round(b.pos.y))


def make_grunt(pos, target, armor_class: int = 0, groups: list = ()) -> Enemy:
    return Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)


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
