"""
snow.py — система снежных частиц.

Рендерится поверх мирового буфера (до HUD), чтобы снег
падал «в мире», но всегда перекрывал пол и акторов.

Управление:
    snow = SnowSystem(settings)
    snow.update(dt)
    snow.draw(surface)   # surface — экранный буфер (уже после зума)

Включается автоматически при загрузке уровня с
map property  snow_enabled = true  (bool) в .tmx файле.
Отключается для уровней без этого свойства.
"""
from __future__ import annotations
import random
import pygame


class _Flake:
    """Одна снежинка."""
    __slots__ = ("x", "y", "speed", "drift", "size", "alpha", "phase")

    def __init__(self, sw: int, sh: int) -> None:
        self.x     = random.uniform(0, sw)
        self.y     = random.uniform(-sh, 0)   # стартуем сверху экрана
        self.speed = random.uniform(40, 110)   # px/s вниз
        self.drift = random.uniform(-18, 18)   # px/s горизонтально
        self.size  = random.randint(1, 3)
        self.alpha = random.randint(120, 220)
        self.phase = random.uniform(0, 6.28)   # для покачивания


class SnowSystem:
    """
    Управляет набором снежных частиц.
    Не зависит от камеры — снег рисуется в экранных координатах.
    """

    COUNT     = 200    # кол-во частиц одновременно
    SWAY_AMP  = 12.0   # амплитуда покачивания, px
    SWAY_FREQ = 0.8    # частота, Гц

    def __init__(self, settings) -> None:
        self.sw = settings.screen_width
        self.sh = settings.screen_height
        self._flakes: list[_Flake] = [
            _Flake(self.sw, self.sh) for _ in range(self.COUNT)
        ]
        self._time = 0.0
        self._enabled = False   # управляется снаружи через .enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def update(self, dt: float) -> None:
        if not self._enabled:
            return
        self._time += dt
        for f in self._flakes:
            sway = self.SWAY_AMP * \
                   pygame.math.Vector2(1, 0).rotate(
                       self.SWAY_FREQ * self._time * 360 + f.phase * 57.3
                   ).x
            f.x += (f.drift + sway) * dt
            f.y += f.speed * dt

            # переносим снежинку наверх, когда вышла за нижний край
            if f.y > self.sh + 4:
                f.y = random.uniform(-20, -4)
                f.x = random.uniform(0, self.sw)
                f.speed = random.uniform(40, 110)
                f.drift = random.uniform(-18, 18)
            # заворачиваем по горизонтали
            if f.x > self.sw + 4:
                f.x -= self.sw + 8
            elif f.x < -4:
                f.x += self.sw + 8

    def draw(self, surface: pygame.Surface) -> None:
        if not self._enabled:
            return
        for f in self._flakes:
            x, y = round(f.x), round(f.y)
            if f.size == 1:
                # одиночный пиксель
                surf = pygame.Surface((1, 1), pygame.SRCALPHA)
                surf.fill((220, 235, 255, f.alpha))
                surface.blit(surf, (x, y))
            else:
                surf = pygame.Surface((f.size, f.size), pygame.SRCALPHA)
                surf.fill((220, 235, 255, f.alpha))
                surface.blit(surf, (x - f.size // 2, y - f.size // 2))
