import pygame
from core.settings import Settings


class Bullet(pygame.sprite.Sprite):
    """
    Простой снаряд — летит по прямой, живёт ограниченное время.
    Sprite достаточно.
    """

    def __init__(
        self,
        pos: tuple[float, float],
        direction: pygame.math.Vector2,
        settings: Settings,
        groups: list = (),
    ) -> None:
        super().__init__(*groups)

        self.settings = settings
        self.damage = settings.bullet_damage
        self.lifetime = settings.bullet_lifetime

        size = settings.bullet_size
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.image.fill(settings.bullet_color)
        self.rect = self.image.get_rect(center=pos)

        self.pos = pygame.math.Vector2(pos)
        self.velocity = direction.normalize() * settings.bullet_speed

    def update(self, dt: float) -> None:
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.kill() # удаляет из всех групп автоматически
            return

        self.pos += self.velocity * dt
        self.rect.center = (round(self.pos.x), round(self.pos.y))
