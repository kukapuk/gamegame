import pygame
from core.settings import Settings
from core.level import Level
from core.pathfinder import Pathfinder
from core.loot_manager import LootManager
from actors.npc import NPC


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
        self._spawn_from_level()

    def _spawn_from_level(self) -> None:
        from actors.enemy import make_grunt, make_shooter

        for obj in self.level.objects:
            t     = obj["type"]
            pos   = (obj["x"], obj["y"])
            props = obj["props"]

            if t == "enemy_grunt":
                e = make_grunt(
                    pos=pos, target=self.player,
                    armor_class=props.get("armor_class", 0),
                    groups=[self.all_sprites, self.enemies],
                )
                e.pathfinder    = self.pathfinder
                e.enemies_group = self.enemies
                patrol = self._parse_patrol(props)
                if patrol:
                    e.set_patrol(patrol)

            elif t == "enemy_shooter":
                e = make_shooter(
                    pos=pos, target=self.player,
                    armor_class=props.get("armor_class", 0),
                    groups=[self.all_sprites, self.enemies],
                    bullet_group=self.enemy_bullets,
                    all_sprites=self.all_sprites,
                )
                e.pathfinder    = self.pathfinder
                e.enemies_group = self.enemies

            elif t == "npc":
                NPC(
                    pos=pos,
                    name=props.get("npc_name", "NPC"),
                    dialog_file=props.get("dialog_file", ""),
                    groups=[self.all_sprites, self.npcs],
                )

    def _parse_patrol(self, props: dict) -> list:
        points = []
        i = 1
        while f"patrol_x{i}" in props and f"patrol_y{i}" in props:
            points.append((props[f"patrol_x{i}"], props[f"patrol_y{i}"]))
            i += 1
        return points

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
