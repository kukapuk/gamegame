import pygame
from entities.actor import Actor
from entities.stats import Stats


class Enemy(Actor):
    """
    Базовый враг. Движется к игроку, получает урон от пуль.
    AI простой: всегда идёт напрямую к цели (chase).
    Позже можно добавить стейт-машину: patrol → chase → attack.
    """

    def __init__(
        self,
        pos: tuple[float, float],
        target: Actor,
        groups: list = (),
    ) -> None:
        super().__init__(
            pos=pos,
            size=28,
            color=(220, 60, 60),
            groups=groups,
        )
        self.target = target
        self.stats = Stats(
            max_hp=60,
            speed=120.0,
            dash_cooldown=999,
            dash_stamina_cost=999,
        )
        self.hp = self.stats.max_hp
        self.max_hp = self.stats.max_hp
        self.speed = self.stats.speed
        self._contact_cooldown: float = 0.0

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

    def update(self, dt: float) -> None:
        self._contact_cooldown = max(0.0, self._contact_cooldown - dt)
        self._chase()
        super().update(dt)
