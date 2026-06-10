import pygame


class Bullet(pygame.sprite.Sprite):
    """
    Простой снаряд — летит по прямой, живёт ограниченное время.
    Параметры берёт напрямую, не из Settings — каждое оружие задаёт свои.
    """

    def __init__(
        self,
        pos: tuple[float, float],
        direction: pygame.math.Vector2,
        speed: float,
        lifetime: float,
        damage: int,
        size: int,
        color: tuple[int, int, int],
        stopping_effect: float,
        groups: list = (),
    ) -> None:
        super().__init__(*groups)

        self.damage          = damage
        self.stopping_effect = stopping_effect
        self.lifetime        = lifetime

        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect  = self.image.get_rect(center=pos)

        self.pos      = pygame.math.Vector2(pos)
        self.velocity = direction.normalize() * speed

    def update(self, dt: float) -> None:
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.kill()
            return
        self.pos += self.velocity * dt
        self.rect.center = (round(self.pos.x), round(self.pos.y))
