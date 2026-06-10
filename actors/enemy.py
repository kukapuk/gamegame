import pygame
from actors.actor import Actor
from items.stats import Stats


class Enemy(Actor):
    """
    Базовый враг. Движется к игроку, получает урон от пуль.
    AI простой: всегда идёт напрямую к цели (chase).
    Позже можно добавить стейт-машину: patrol → chase → attack.
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
        self.hp               = self.stats.max_hp
        self.max_hp           = self.stats.max_hp
        self.speed            = self.stats.speed
        self._contact_cooldown: float = 0.0
        self._stun_timer: float       = 0.0
        self._knockback_vel           = pygame.math.Vector2(0, 0)

    def apply_stopping_effect(self, bullet_direction: pygame.math.Vector2, stopping_effect: float) -> None:
        knockback_force = stopping_effect * 420.0
        self._knockback_vel = bullet_direction.normalize() * knockback_force
        self._stun_timer    = stopping_effect * 0.45

    def try_deal_contact_damage(self, target: Actor, damage: int, cooldown: float) -> None:
        if self._contact_cooldown > 0:
            return
        if self.rect.colliderect(target.rect):
            target.take_damage(damage)
            self._contact_cooldown = cooldown

    def _chase(self) -> None:
        delta = self.target.pos - self.pos
        if delta.length() > 1:
            self.velocity = delta.normalize() * self.speed
        else:
            self.velocity.update(0, 0)

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        self._contact_cooldown = max(0.0, self._contact_cooldown - dt)

        if self._stun_timer > 0:
            self._stun_timer -= dt
            self._knockback_vel *= max(0.0, 1.0 - self.KNOCKBACK_FRICTION * dt)
            self.velocity = self._knockback_vel.copy()
        else:
            self._knockback_vel.update(0, 0)
            self._chase()

        super().update(dt, walls)
