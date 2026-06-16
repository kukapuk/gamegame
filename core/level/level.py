import pygame
import pytmx
from core.wall import Wall


class Level:
    """
    Загружает уровень из .tmx файла (Tiled).
    Слои: floor (рендер), walls (коллизии), objects (спавны).
    Объекты читаются через level.objects — список dict с полями type и props.
    """

    def __init__(self, path: str, tile_size: int) -> None:
        self.path         = path
        self.tile_size    = tile_size
        self.walls        = pygame.sprite.Group()
        self.all_sprites  = pygame.sprite.Group()
        self.player_spawn: tuple[int, int] = (0, 0)
        self.cols: int = 0
        self.rows: int = 0

        self._floor_surfaces: list[tuple[pygame.Surface, pygame.Rect]] = []
        self.objects: list[dict] = []
        self.lights:  list[dict] = []
        # (tile_x, tile_y) → surface_type str
        self.surface_map: dict[tuple[int,int], str] = {}

        self._load(path)

    def _load(self, path: str) -> None:
        tiled = pytmx.util_pygame.load_pygame(path)
        self.cols      = tiled.width
        self.rows      = tiled.height
        self.tile_size = tiled.tilewidth

        for layer in tiled.layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                if layer.name == "floor":
                    self._load_floor(tiled, layer)
                elif layer.name == "walls":
                    self._load_walls(tiled, layer)
            elif isinstance(layer, pytmx.TiledObjectGroup):
                if layer.name == "objects":
                    self._load_objects(layer)
                elif layer.name == "lights":
                    self._load_lights(layer)

    def _load_floor(self, tiled, layer: pytmx.TiledTileLayer) -> None:
        ts = self.tile_size
        for x, y, gid in layer:
            if gid == 0:
                continue
            surf = tiled.get_tile_image_by_gid(gid)
            if surf:
                scaled = pygame.transform.scale(surf, (ts, ts))
                rect   = pygame.Rect(x * ts, y * ts, ts, ts)
                self._floor_surfaces.append((scaled, rect))
            # читаем surface_type из свойств тайла
            props = tiled.get_tile_properties_by_gid(gid)
            if props and "surface_type" in props:
                self.surface_map[(x, y)] = props["surface_type"]

    def _load_walls(self, tiled, layer: pytmx.TiledTileLayer) -> None:
        ts = self.tile_size
        for x, y, gid in layer:
            if gid == 0:
                continue
            surf = tiled.get_tile_image_by_gid(gid)
            wall = Wall(x * ts, y * ts, ts, groups=[self.walls, self.all_sprites])
            if surf:
                scaled = pygame.transform.scale(surf, (ts, ts))
                wall.image = scaled
            # ШАГ 4: строим sprite stack сразу после загрузки тайла
            wall.build_sprite_stack()

    def _load_objects(self, layer: pytmx.TiledObjectGroup) -> None:
        for obj in layer:
            props = dict(obj.properties) if obj.properties else {}
            cx    = int(obj.x + obj.width  / 2)
            cy    = int(obj.y + obj.height / 2)

            entry = {
                "type":  obj.type or "",
                "name":  obj.name or "",
                "x":     cx,
                "y":     cy,
                "props": props,
            }
            self.objects.append(entry)

            if obj.type == "player_spawn":
                self.player_spawn = (cx, cy)

    def _load_lights(self, layer: pytmx.TiledObjectGroup) -> None:
        for obj in layer:
            props = dict(obj.properties) if obj.properties else {}
            self.lights.append({
                "x":         obj.x,
                "y":         obj.y,
                "radius":    props.get("radius",    180),
                "color":     props.get("color",     "#ffcc88"),
                "intensity": props.get("intensity", 0.85),
                "flicker":   props.get("flicker",   False),
            })

    def draw_floor(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        for tile_surf, rect in self._floor_surfaces:
            screen_rect = rect.move(-camera_offset.x, -camera_offset.y)
            if surface.get_rect().colliderect(screen_rect):
                surface.blit(tile_surf, screen_rect)
