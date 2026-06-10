import pygame
from core.settings import Settings


class Camera:
    """
    Simple camera that keeps a target centred on screen.

    Usage:
        offset = camera.get_offset()
        screen_pos = world_pos - offset
    """

    def __init__(self, settings: Settings) -> None:
        self.offset = pygame.math.Vector2(0, 0)
        self.half_w = settings.screen_width // 2
        self.half_h = settings.screen_height // 2

    def follow(self, target: pygame.sprite.Sprite) -> None:
        """Snap camera so target is centred. Call once per frame."""
        self.offset.x = target.rect.centerx - self.half_w
        self.offset.y = target.rect.centery - self.half_h

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        """Return a screen-space rect for a world-space rect."""
        return rect.move(-self.offset.x, -self.offset.y)

    def get_offset(self) -> pygame.math.Vector2:
        return self.offset.copy()
