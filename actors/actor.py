import pygame


class Actor(pygame.sprite.Sprite):
    """
    Base class for every entity in the game: player, enemies, NPCs.
    Subclasses extend with input handling (Player) or AI behaviour (Enemy).
    """

    def __init__(
        self,
        pos: tuple[float, float],
        size: int,
        color: tuple[int, int, int],
        groups: list = (),
    ) -> None:
        super().__init__(*groups)

        self.color = color
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect = self.image.get_rect(center=pos)

        self.pos = pygame.math.Vector2(pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.facing = pygame.math.Vector2(0, 1)

        self.speed: float = 0.0
        self.hp: int = 100
        self.max_hp: int = 100
        self.alive: bool = True

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False
            self.kill()

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        if walls:
            self._move_with_collisions(dt, walls)
        else:
            self.pos += self.velocity * dt
            self.rect.center = (round(self.pos.x), round(self.pos.y))

    def _move_with_collisions(self, dt: float, walls: pygame.sprite.Group) -> None:
        self.pos.x += self.velocity.x * dt
        self.rect.centerx = round(self.pos.x)
        for wall in pygame.sprite.spritecollide(self, walls, False):
            if self.velocity.x > 0:
                self.rect.right = wall.rect.left
            elif self.velocity.x < 0:
                self.rect.left = wall.rect.right
            self.pos.x = self.rect.centerx

        self.pos.y += self.velocity.y * dt
        self.rect.centery = round(self.pos.y)
        for wall in pygame.sprite.spritecollide(self, walls, False):
            if self.velocity.y > 0:
                self.rect.bottom = wall.rect.top
            elif self.velocity.y < 0:
                self.rect.top = wall.rect.bottom
            self.pos.y = self.rect.centery

    def set_pos(self, pos: tuple[float, float]) -> None:
        self.pos.update(pos)
        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        draw_rect = self.rect.move(-camera_offset.x, -camera_offset.y)
        pygame.draw.rect(surface, (255, 50, 50), draw_rect, 1)
