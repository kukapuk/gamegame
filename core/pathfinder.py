import pygame
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.diagonal_movement import DiagonalMovement

class Pathfinder:
    """
    Строит навигационный grid из тайлов уровня и находит путь A*.
    Grid перестраивается автоматически при смене уровня.
    Используй find_path() — возвращает список world-позиций точек пути.
    """

    def __init__(self, tile_size: int) -> None:
        self.tile_size = tile_size
        self._matrix: list[list[int]] = []
        self._cols: int = 0
        self._rows: int = 0

    def build_from_walls(self, walls: pygame.sprite.Group, cols: int, rows: int) -> None:
        self._cols = cols
        self._rows = rows
        self._matrix = [[1] * cols for _ in range(rows)]

        ts = self.tile_size
        for wall in walls:
            col = wall.rect.left // ts
            row = wall.rect.top  // ts
            if 0 <= row < rows and 0 <= col < cols:
                self._matrix[row][col] = 0

    def find_path(
        self,
        start_world: pygame.math.Vector2,
        end_world: pygame.math.Vector2,
    ) -> list[pygame.math.Vector2]:
        if not self._matrix:
            return []

        ts = self.tile_size
        sc = int(start_world.x // ts)
        sr = int(start_world.y // ts)
        ec = int(end_world.x   // ts)
        er = int(end_world.y   // ts)

        sc = max(0, min(sc, self._cols - 1))
        sr = max(0, min(sr, self._rows - 1))
        ec = max(0, min(ec, self._cols - 1))
        er = max(0, min(er, self._rows - 1))

        if self._matrix[sr][sc] == 0:
            sc, sr = self._nearest_walkable(sc, sr)
        if self._matrix[er][ec] == 0:
            ec, er = self._nearest_walkable(ec, er)

        grid  = Grid(matrix=self._matrix)
        start = grid.node(sc, sr)
        end   = grid.node(ec, er)

        finder = AStarFinder(diagonal_movement=DiagonalMovement.only_when_no_obstacle)
        path, _ = finder.find_path(start, end, grid)

        return [
            pygame.math.Vector2(node.x * ts + ts // 2, node.y * ts + ts // 2)
            for node in path
        ]

    def _nearest_walkable(self, col: int, row: int) -> tuple[int, int]:
        for r in range(1, max(self._cols, self._rows)):
            for dc in range(-r, r + 1):
                for dr in range(-r, r + 1):
                    nc, nr = col + dc, row + dr
                    if (0 <= nr < self._rows and 0 <= nc < self._cols
                            and self._matrix[nr][nc] == 1):
                        return nc, nr
        return col, row

    def draw_debug(
        self,
        surface: pygame.Surface,
        camera_offset: pygame.math.Vector2,
        path: list[pygame.math.Vector2],
    ) -> None:
        if len(path) < 2:
            return
        ts  = self.tile_size
        pts = [
            (round(p.x - camera_offset.x), round(p.y - camera_offset.y))
            for p in path
        ]
        pygame.draw.lines(surface, (80, 200, 255), False, pts, 2)
        for pt in pts:
            pygame.draw.circle(surface, (60, 160, 220), pt, 3)
