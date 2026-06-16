import math
import random
import pygame
from core.settings import Settings


class Camera:
    """
    Плавная камера с lerp + screen shake.
    smoothing — скорость следования (1.0 = мгновенно, 0.05 = очень плавно).

    shake(intensity, duration):
        intensity — амплитуда в пикселях
        duration  — длительность в секундах
    """

    def __init__(self, settings: Settings) -> None:
        self.offset    = pygame.math.Vector2(0, 0)
        self.half_w    = settings.screen_width  // 2
        self.half_h    = settings.screen_height // 2
        self.smoothing = 0.12

        # zoom
        self.zoom:      float = settings.zoom_default
        self._zoom_min: float = settings.zoom_min
        self._zoom_max: float = settings.zoom_max
        self._zoom_step: float = settings.zoom_step

        # shake
        self._shake_intensity: float = 0.0
        self._shake_timer:     float = 0.0
        self._shake_decay:     float = 0.0   # интенсивность/сек убывания
        self._shake_offset     = pygame.math.Vector2(0, 0)

    def shake(self, intensity: float, duration: float = 0.08) -> None:
        """Добавить тряску. Вызывается при выстреле, попадании и т.д."""
        # аккумулируем — несколько выстрелов подряд усиливают тряску
        self._shake_intensity = min(self._shake_intensity + intensity, intensity * 2.5)
        self._shake_timer     = max(self._shake_timer, duration)
        self._shake_decay     = self._shake_intensity / max(duration, 0.01)

    def update(self, dt: float) -> None:
        """Обновлять каждый кадр до follow()."""
        if self._shake_timer > 0:
            self._shake_timer    -= dt
            self._shake_intensity = max(0.0, self._shake_intensity - self._shake_decay * dt)
            # случайный offset в любом направлении
            angle = random.uniform(0, math.pi * 2)
            r     = self._shake_intensity
            self._shake_offset.x = math.cos(angle) * r
            self._shake_offset.y = math.sin(angle) * r
        else:
            self._shake_intensity = 0.0
            self._shake_offset.update(0, 0)

    def follow(self, target: pygame.sprite.Sprite) -> None:
        target_x = target.rect.centerx - self.half_w
        target_y = target.rect.centery - self.half_h
        self.offset.x += (target_x - self.offset.x) * self.smoothing
        self.offset.y += (target_y - self.offset.y) * self.smoothing

    def change_zoom(self, direction: int) -> None:
        """direction: +1 приблизить, -1 отдалить."""
        self.zoom = round(
            max(self._zoom_min, min(self._zoom_max, self.zoom + direction * self._zoom_step)),
            2,
        )

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        sx = self.offset.x + self._shake_offset.x
        sy = self.offset.y + self._shake_offset.y
        return rect.move(-sx, -sy)

    def get_offset(self) -> pygame.math.Vector2:
        return pygame.math.Vector2(
            self.offset.x + self._shake_offset.x,
            self.offset.y + self._shake_offset.y,
        )
