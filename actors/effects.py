"""
effects.py — визуальные спрайты-эффекты на полу/в воздухе.
BloodDrop, Casing, Magazine, DamagePopup.
"""
import pygame
import random


class BloodDrop(pygame.sprite.Sprite):
    """Красный квадратик на полу — след кровотечения."""

    LIFETIME = 9.0
    SIZE     = 4

    def __init__(self, pos: pygame.math.Vector2, groups: list = ()) -> None:
        super().__init__(*groups)
        ox = random.randint(-6, 6)
        oy = random.randint(-6, 6)
        self.image = pygame.Surface((self.SIZE, self.SIZE))
        self.image.fill((160, 20, 20))
        self.rect  = self.image.get_rect(
            center=(round(pos.x + ox), round(pos.y + oy))
        )
        self._lifetime = self.LIFETIME

    def update(self, dt: float) -> None:
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.kill()
            return
        alpha = max(0, int(255 * self._lifetime / self.LIFETIME))
        self.image.set_alpha(alpha)


class Casing(pygame.sprite.Sprite):
    """Гильза — маленький золотой прямоугольник, вылетает при выстреле."""

    LIFETIME = 6.0
    W, H     = 4, 2

    def __init__(
        self,
        pos:     pygame.math.Vector2,
        aim_dir: pygame.math.Vector2,
        groups:  list = (),
    ) -> None:
        super().__init__(*groups)
        perp      = pygame.math.Vector2(-aim_dir.y, aim_dir.x)
        speed     = random.uniform(60, 110)
        self._vel = perp * speed + aim_dir * random.uniform(-20, 20)
        ox, oy    = random.randint(-2, 2), random.randint(-2, 2)
        self._pos = pygame.math.Vector2(pos.x + ox, pos.y + oy)
        self.image = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.image.fill((210, 170, 60))
        self.rect  = self.image.get_rect(center=(round(self._pos.x), round(self._pos.y)))
        self._lifetime = self.LIFETIME

    def update(self, dt: float) -> None:
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.kill()
            return
        self._vel *= max(0.0, 1.0 - dt * 6)
        self._pos += self._vel * dt
        self.rect.center = (round(self._pos.x), round(self._pos.y))
        self.image.set_alpha(max(0, int(255 * self._lifetime / self.LIFETIME)))


class DamagePopup(pygame.sprite.Sprite):
    """Числовой попап урона над врагом. Белый — обычный, красный — голова."""

    LIFETIME = 1.2

    def __init__(
        self,
        pos:      pygame.math.Vector2,
        damage:   int,
        headshot: bool = False,
        groups:   list = (),
    ) -> None:
        super().__init__(*groups)
        color = (255, 80, 80) if headshot else (230, 230, 230)
        font  = pygame.font.SysFont("monospace", 14 if headshot else 12, bold=headshot)
        self._text_surf = font.render(str(damage), True, color)
        self.image      = self._text_surf.copy()
        self._pos       = pygame.math.Vector2(pos.x + random.randint(-8, 8), pos.y - 20)
        self.rect       = self.image.get_rect(center=(round(self._pos.x), round(self._pos.y)))
        self._lifetime  = self.LIFETIME

    def update(self, dt: float) -> None:
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.kill()
            return
        self._pos.y -= 28 * dt
        self.rect.center = (round(self._pos.x), round(self._pos.y))
        self.image = self._text_surf.copy()
        self.image.set_alpha(max(0, int(255 * self._lifetime / self.LIFETIME)))


class Magazine(pygame.sprite.Sprite):
    """Выброшенный магазин — прямоугольник при перезарядке."""

    LIFETIME = 5.0
    W, H     = 7, 12

    def __init__(self, pos: pygame.math.Vector2, groups: list = ()) -> None:
        super().__init__(*groups)
        self._vel = pygame.math.Vector2(
            random.uniform(-50, 50),
            random.uniform(-80, -30),
        )
        self._pos  = pygame.math.Vector2(pos)
        self.image = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.image.fill((160, 160, 100))
        self.rect  = self.image.get_rect(center=(round(self._pos.x), round(self._pos.y)))
        self._lifetime = self.LIFETIME

    def update(self, dt: float) -> None:
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.kill()
            return
        self._vel *= max(0.0, 1.0 - dt * 4)
        self._pos += self._vel * dt
        self.rect.center = (round(self._pos.x), round(self._pos.y))
        self.image.set_alpha(max(0, int(255 * self._lifetime / self.LIFETIME)))
