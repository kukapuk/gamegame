import pygame
from core.settings import Settings
from core.level import Level
from core.pathfinder import Pathfinder
from core.managers.loot_manager import LootManager


class WorldManager:
    """
    Управляет игровым миром: спавн акторов из уровня, переходы между уровнями,
    отслеживание ближайшего NPC.

    Переход между уровнями — через объект типа level_exit в tmx:
        props: target_level (str)
    """

    def __init__(
        self,
        settings: Settings,
        all_sprites: pygame.sprite.Group,
        enemies: pygame.sprite.Group,
        enemy_bullets: pygame.sprite.Group,
        npcs: pygame.sprite.Group,
        loot: LootManager,
    ) -> None:
        self.s             = settings
        self.all_sprites   = all_sprites
        self.enemies       = enemies
        self.enemy_bullets = enemy_bullets
        self.npcs          = npcs
        self.loot          = loot

        self.level:      Level      = None
        self.pathfinder: Pathfinder = None
        self.player                 = None

        self._nearby_npc            = None
        self._nearby_exit           = None
        self._pending_level: str    = None

        self._font = pygame.font.SysFont("monospace", 14)

    # Level loading

    def load_level(self, path: str, player, bullets: pygame.sprite.Group) -> None:
        self.player  = player
        self._bullets = bullets

        self.level = Level(path, self.s.grid_size)

        self.pathfinder = Pathfinder(self.s.grid_size)
        self.pathfinder.build_from_walls(
            self.level.walls, self.level.cols, self.level.rows
        )

    # Update

    def update(self, player) -> None:
        self._update_nearby_npc(player)
        self._update_nearby_exit(player)

    def _update_nearby_npc(self, player) -> None:
        self._nearby_npc = None
        for npc in self.npcs:
            if npc.is_in_interact_range(player.pos):
                self._nearby_npc = npc
                break

    def _update_nearby_exit(self, player) -> None:
        self._nearby_exit  = None
        self._pending_level = None
        if not self.level:
            return
        for obj in self.level.objects:
            if obj["type"] != "level_exit":
                continue
            ox, oy = obj["x"], obj["y"]
            hw = obj["props"].get("half_w", 48)
            hh = obj["props"].get("half_h", 48)
            zone = pygame.Rect(ox - hw, oy - hh, hw * 2, hh * 2)
            if zone.collidepoint(player.pos.x, player.pos.y):
                self._nearby_exit   = obj
                self._pending_level = obj["props"].get("target_level")
                break

    # Public getters

    def get_nearby_npc(self):
        return self._nearby_npc

    def get_pending_level(self) -> str | None:
        return self._pending_level

    def consume_pending_level(self) -> str | None:
        lvl = self._pending_level
        self._pending_level = None
        self._nearby_exit   = None
        return lvl

    # Draw

    def draw(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        self._draw_exit_hint(surface, camera_offset)

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        if not self.level:
            return
        for obj in self.level.objects:
            if obj["type"] != "level_exit":
                continue
            ox, oy = obj["x"], obj["y"]
            hw = obj["props"].get("half_w", 48)
            hh = obj["props"].get("half_h", 48)
            rect = pygame.Rect(
                ox - hw - camera_offset.x,
                oy - hh - camera_offset.y,
                hw * 2, hh * 2,
            )
            pygame.draw.rect(surface, (80, 220, 180), rect, 2)

    def _draw_exit_hint(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        if not self._nearby_exit:
            return
        ox  = self._nearby_exit["x"]
        oy  = self._nearby_exit["y"]
        sx  = round(ox - camera_offset.x)
        sy  = round(oy - camera_offset.y)
        tgt = self._nearby_exit["props"].get("target_level", "?")
        text = f"[E]  Enter  →  {tgt}"
        surf = self._font.render(text, True, (180, 240, 200))
        pad  = 5
        bg   = pygame.Surface(
            (surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA
        )
        bg.fill((10, 20, 14, 180))
        bx = sx - bg.get_width() // 2
        by = sy - bg.get_height() - 10
        surface.blit(bg,   (bx, by))
        surface.blit(surf, (bx + pad, by + pad))
