import pygame
from core.settings import Settings


class Camera:
    """
    Плавная камера с lerp. Следует за целью с небольшим отставанием.
    smoothing — скорость следования (1.0 = мгновенно, 0.05 = очень плавно).
    """

    def __init__(self, settings: Settings) -> None:
        self.offset   = pygame.math.Vector2(0, 0)
        self.half_w   = settings.screen_width  // 2
        self.half_h   = settings.screen_height // 2
        self.smoothing = 0.12

    def follow(self, target: pygame.sprite.Sprite) -> None:
        target_x = target.rect.centerx - self.half_w
        target_y = target.rect.centery - self.half_h
        self.offset.x += (target_x - self.offset.x) * self.smoothing
        self.offset.y += (target_y - self.offset.y) * self.smoothing

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(-self.offset.x, -self.offset.y)

    def get_offset(self) -> pygame.math.Vector2:
        return self.offset.copy()
