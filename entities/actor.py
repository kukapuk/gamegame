import pygame
from typing import Optional


class Actor(pygame.sprite.Sprite):
    """
    Base class for every entity in the game: player, enemies, NPCs.

    Holds the common data every actor needs:
      - position (float precision, converted to int for rendering)
      - velocity
      - size / rect
      - a reference to the sprite groups it belongs to

    Subclasses extend this with input handling (Player),
    AI behaviour (Enemy), etc.
    """

    def __init__(
        self,
        pos: tuple[float, float],
        size: int,
        color: tuple[int, int, int],
        groups: list | tuple = (),
    ) -> None:
        super().__init__(*groups)

        self.color = color
        
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect = self.image.get_rect(center=pos)
        
        self.pos = pygame.math.Vector2(pos)
        
        self.velocity = pygame.math.Vector2(0, 0)
        
        self.speed: float = 0.0
        self.alive: bool = True

    def update(self, dt: float) -> None:
        """Move actor by velocity * dt. dt is seconds since last frame."""
        self.pos += self.velocity * dt
        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def set_pos(self, pos: tuple[float, float]) -> None:
        self.pos.update(pos)
        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        """Draw bounding rect — useful while building the game."""
        draw_rect = self.rect.move(-camera_offset.x, -camera_offset.y)
        pygame.draw.rect(surface, (255, 50, 50), draw_rect, 1)
