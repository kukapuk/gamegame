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
        # постепенно темнеет и исчезает
        alpha = max(0, int(255 * self._lifetime / self.LIFETIME))
        self.image.set_alpha(alpha)


class Casing(pygame.sprite.Sprite):
    """Гильза — маленький золотой прямоугольник, вылетает при выстреле."""

    LIFETIME = 6.0
    W, H     = 4, 2

    def __init__(
        self,
        pos:       pygame.math.Vector2,
        aim_dir:   pygame.math.Vector2,
        groups:    list = (),
    ) -> None:
        super().__init__(*groups)

        # Гильза вылетает перпендикулярно стволу (вправо относительно aim)
        perp = pygame.math.Vector2(-aim_dir.y, aim_dir.x)
        speed = random.uniform(60, 110)
        self._vel = perp * speed + aim_dir * random.uniform(-20, 20)

        ox = random.randint(-2, 2)
        oy = random.randint(-2, 2)
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
        # торможение
        self._vel *= max(0.0, 1.0 - dt * 6)
        self._pos += self._vel * dt
        self.rect.center = (round(self._pos.x), round(self._pos.y))

        alpha = max(0, int(255 * self._lifetime / self.LIFETIME))
        self.image.set_alpha(alpha)


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
        alpha = max(0, int(255 * (self._lifetime / self.LIFETIME)))
        self.image = self._text_surf.copy()
        self.image.set_alpha(alpha)


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
        self._pos = pygame.math.Vector2(pos)
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
        alpha = max(0, int(255 * (self._lifetime / self.LIFETIME)))
        self.image.set_alpha(alpha)


class Actor(pygame.sprite.Sprite):
    """
    Base class for every entity in the game: player, enemies, NPCs.

    Два хитбокса:
      body_rect -- full sprite collider
      head_rect -- sticks out above body_rect (half above, half inside)

    Кровотечение: bleeding=True → -3 HP/сек, спавн BloodDrop каждые 0.5 сек.
    """

    HEAD_SIZE_RATIO = 0.45

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

        self.pos      = pygame.math.Vector2(pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.facing   = pygame.math.Vector2(0, 1)

        self.speed:  float = 0.0
        self.hp:     int   = 100
        self.max_hp: int   = 100
        self.alive:  bool  = True

        self.body_rect     = self.rect.copy()
        self.head_rect     = self._calc_head_rect()
        self.last_hit_zone = None

        # кровотечение
        self.bleeding:         bool  = False
        self._bleed_timer:     float = 0.0
        self._bleed_interval:  float = 1.0
        self._bleed_damage:    int   = 3
        self._drop_timer:      float = 0.0
        self._drop_interval:   float = 0.5
        self._blood_group:     pygame.sprite.Group = None  # задаётся снаружи

    # ------------------------------------------------------------------ #
    # Hitboxes
    # ------------------------------------------------------------------ #

    def _calc_head_rect(self) -> pygame.Rect:
        sz = max(4, int(self.rect.width * self.HEAD_SIZE_RATIO))
        return pygame.Rect(
            self.rect.centerx - sz // 2,
            self.rect.top - sz // 2,
            sz, sz,
        )

    def _update_hitboxes(self) -> None:
        self.body_rect = self.rect.copy()
        self.head_rect = self._calc_head_rect()

    # ------------------------------------------------------------------ #
    # Bleeding
    # ------------------------------------------------------------------ #

    def apply_bleeding(self) -> None:
        self.bleeding     = True
        self._bleed_timer = 0.0
        self._drop_timer  = 0.0

    def stop_bleeding(self) -> None:
        self.bleeding     = False
        self._bleed_timer = 0.0
        self._drop_timer  = 0.0

    def _update_bleeding(self, dt: float) -> None:
        if not self.bleeding:
            return

        self._bleed_timer += dt
        if self._bleed_timer >= self._bleed_interval:
            self._bleed_timer -= self._bleed_interval
            self.take_damage(self._bleed_damage)

        self._drop_timer += dt
        if self._drop_timer >= self._drop_interval:
            self._drop_timer -= self._drop_interval
            if self._blood_group is not None:
                BloodDrop(self.pos, groups=[self._blood_group])

    # ------------------------------------------------------------------ #
    # Damage
    # ------------------------------------------------------------------ #

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False
            self.kill()

    # ------------------------------------------------------------------ #
    # Update / move
    # ------------------------------------------------------------------ #

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        self._update_bleeding(dt)
        if walls:
            self._move_with_collisions(dt, walls)
        else:
            self.pos += self.velocity * dt
            self.rect.center = (round(self.pos.x), round(self.pos.y))
        self._update_hitboxes()

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
        self._update_hitboxes()

    # ------------------------------------------------------------------ #
    # Debug
    # ------------------------------------------------------------------ #

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        body = self.body_rect.move(-camera_offset.x, -camera_offset.y)
        head = self.head_rect.move(-camera_offset.x, -camera_offset.y)
        pygame.draw.rect(surface, (255, 50,  50), body, 1)
        pygame.draw.rect(surface, (255, 220, 50), head, 1)

        if self.last_hit_zone is not None:
            font = pygame.font.SysFont("monospace", 10)
            zone_colors = {
                "HEAD":  (255, 220, 50),
                "TORSO": (255, 120, 50),
                "ARMS":  (50,  200, 255),
                "LEGS":  (50,  255, 120),
            }
            name  = self.last_hit_zone.name
            color = zone_colors.get(name, (255, 255, 255))
            lbl   = font.render(name, True, color)
            surface.blit(lbl, (body.centerx - lbl.get_width() // 2,
                                body.top - lbl.get_height() - 2))
