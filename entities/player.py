import pygame
from entities.actor import Actor
from core.settings import Settings


class Player(Actor):
    def __init__(self, pos: tuple[float, float], settings: Settings, groups) -> None:
        super().__init__(
            pos=pos,
            size=settings.player_size,
            color=settings.player_color,
            groups=groups,
        )
        self.speed = settings.player_speed
        self.settings = settings

        # Direction the player is currently facing (for aiming / shooting later)
        self.facing = pygame.math.Vector2(0, 1)

    def handle_input(self) -> None:
        keys = pygame.key.get_pressed()

        direction = pygame.math.Vector2(0, 0)

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            direction.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction.x += 1

        if direction.length() > 0:
            direction = direction.normalize()
            self.facing = direction.copy()

        self.velocity = direction * self.speed

    def update(self, dt: float) -> None:
        self.handle_input()
        super().update(dt) # applies velocity * dt to position
