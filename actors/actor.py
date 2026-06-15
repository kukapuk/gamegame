"""
actor.py — базовый класс для всех сущностей (игрок, враги, NPC).
"""
import pygame
from actors.effects import BloodDrop
from core.managers.faction_manager import Faction


class Actor(pygame.sprite.Sprite):
    """
    Base class: player, enemies, NPCs.

    Два хитбокса:
      body_rect — full sprite collider
      head_rect — sticks out above body_rect

    Кровотечение: bleeding=True → -3 HP/сек, спавн BloodDrop каждые 0.5 сек.
    """

    HEAD_SIZE_RATIO = 0.45

    def __init__(
        self,
        pos:   tuple[float, float],
        size:  int,
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
        self.faction: Faction = Faction.NEUTRAL   # переопределяется в подклассах

        self.body_rect     = self.rect.copy()
        self.head_rect     = self._calc_head_rect()
        self.last_hit_zone = None

        self.bleeding:        bool  = False
        self._bleed_timer:    float = 0.0
        self._bleed_interval: float = 1.0
        self._bleed_damage:   int   = 3
        self._drop_timer:     float = 0.0
        self._drop_interval:  float = 0.5
        self._blood_group:    pygame.sprite.Group = None

    # ── Hitboxes ──────────────────────────────────────────────────────

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

    # ── Bleeding ──────────────────────────────────────────────────────

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

    # ── Damage ────────────────────────────────────────────────────────

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False
            self.kill()

    # ── Update / move ─────────────────────────────────────────────────

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

    # ── Debug ─────────────────────────────────────────────────────────

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
