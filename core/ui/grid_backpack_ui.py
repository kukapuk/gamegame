"""
GridBackpackUI — UI рюкзака в стиле RE4/Tarkov.

Отвечает за:
  - Отрисовку сетки с предметами
  - Drag & drop с подсветкой целевых ячеек (зелёная/красная)
  - Поворот предмета во время drag (Ctrl)
  - Дроп предмета на пол если не влезает

Общается с HUD через return-значения handle_mouse_up():
  {"drop_item": Item | None, "kill_world_item": WorldItem | None}
"""

from __future__ import annotations
import pygame
from typing import Optional
from dataclasses import dataclass, field

from items.inventory import GridInventory
from items.item import Item


# ── Цвета ────────────────────────────────────────────────────────────────────

_CELL_BG        = (28, 30, 42)
_CELL_BORDER    = (55, 58, 78)
_CELL_HOVER     = (48, 52, 70)
_PLACE_OK       = (50, 160, 70,  90)   # зелёная тень — можно положить
_PLACE_FAIL     = (180, 50, 50,  90)   # красная тень — не влезает
_PLACE_OK_BRD   = (80, 220, 100, 200)
_PLACE_FAIL_BRD = (220, 70,  70, 200)
_PANEL_BG       = (18, 20, 30, 235)
_PANEL_BORDER   = (58, 62, 88)
_TITLE_BG       = (26, 28, 44)
_TITLE_DRAG_BG  = (36, 40, 62)
_TEXT_COLOR     = (180, 185, 205)
_ITEM_TINT_NORM = (255, 255, 255, 0)   # без тинта
TITLE_H         = 28
CELL            = 48    # пикселей на ячейку
CELL_PAD        = 3     # зазор между ячейками


@dataclass
class GridDragState:
    item:              Item
    source_grid:       Optional[GridInventory] = None   # из сетки
    source_slot:       object                  = None   # из pouch-слота
    source_world_item: object                  = None   # из мира
    grab_col: int = 0
    grab_row: int = 0


class GridBackpackUI:
    """
    Отрисовывает рюкзак-сетку и обрабатывает его события мыши.
    Создаётся и хранится внутри HUD.
    """

    def __init__(
        self,
        settings,
        player,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
    ) -> None:
        self.s      = settings
        self.player = player
        self.font_sm = font_sm
        self.font_md = font_md

        # позиция панели (перетаскивается за заголовок)
        grid    = player.backpack
        pw      = grid.cols * (CELL + CELL_PAD) + CELL_PAD + 24
        ph      = grid.rows * (CELL + CELL_PAD) + CELL_PAD + TITLE_H + 16
        self._panel_pos  = pygame.Vector2(
            settings.screen_width  - pw - 20,
            settings.screen_height // 2 - ph // 2,
        )
        self._panel_size = (pw, ph)
        self._panel_dragging    = False
        self._panel_drag_offset = pygame.Vector2(0, 0)

        self._drag: Optional[GridDragState] = None
        self._hover_cell: Optional[tuple[int, int]] = None  # (col, row) под курсором

    # ── Public API ────────────────────────────────────────────────────────────

    def open(self) -> None:
        """Вызывается когда рюкзак открывается — сбрасываем hover."""
        self._hover_cell = None

    def close(self) -> None:
        """Вызывается при закрытии — отменяем drag, возвращаем предмет."""
        if self._drag:
            d = self._drag
            if d.source_grid:
                d.source_grid.add(d.item)
            elif d.source_slot and d.source_slot.item is None:
                d.source_slot.item = d.item
        self._drag           = None
        self._hover_cell     = None
        self._panel_dragging = False

    @property
    def is_dragging(self) -> bool:
        return self._drag is not None

    def get_drag_item(self) -> Optional[Item]:
        return self._drag.item if self._drag else None

    # ── Mouse events ─────────────────────────────────────────────────────────

    def handle_mouse_down(self, pos: tuple) -> bool:
        """
        ЛКМ. Возвращает True если клик поглощён панелью.
        Начинает drag если нажали на предмет в сетке.
        """
        px, py = int(self._panel_pos.x), int(self._panel_pos.y)
        pw, ph = self._panel_size

        # клик на заголовок — перетаскиваем панель
        title_rect = pygame.Rect(px, py, pw, TITLE_H)
        if title_rect.collidepoint(pos):
            self._panel_dragging = True
            self._panel_drag_offset.update(pos[0] - px, pos[1] - py)
            return True

        # клик вне панели — не наше
        if not pygame.Rect(px, py, pw, ph).collidepoint(pos):
            return False

        # определяем ячейку
        cell = self._pos_to_cell(pos)
        if cell is None:
            return True  # внутри панели, но вне сетки

        col, row = cell
        grid = self.player.backpack
        item = grid.item_at(col, row)
        if item is None:
            return True

        # вычисляем смещение захвата — на какую sub-ячейку нажали
        placement = grid.placement_of(item)
        grab_col  = col - placement.col
        grab_row  = row - placement.row

        grid.remove(item)
        self._drag = GridDragState(
            item=item,
            source_grid=grid,
            grab_col=grab_col,
            grab_row=grab_row,
        )
        return True

    def handle_world_mouse_down(self, pos: tuple, world_items, camera_offset) -> bool:
        """
        Если рюкзак открыт и кликнули на WorldItem в радиусе — начинаем drag из мира.
        Зона клика расширена на 16px вокруг спрайта.
        """
        best_wi   = None
        best_dist = float("inf")
        for wi in world_items:
            if not wi.is_in_pickup_range(self.player.pos):
                continue
            screen_rect = wi.rect.move(-camera_offset.x, -camera_offset.y)
            expanded    = screen_rect.inflate(32, 32)
            if expanded.collidepoint(pos):
                dx   = screen_rect.centerx - pos[0]
                dy   = screen_rect.centery - pos[1]
                dist = dx * dx + dy * dy
                if dist < best_dist:
                    best_dist = dist
                    best_wi   = wi
        if best_wi:
            self._drag = GridDragState(
                item=best_wi.item,
                source_grid=None,
                source_world_item=best_wi,
            )
            return True
        return False

    def handle_mouse_up(self, pos: tuple) -> dict:
        """
        Отпустили ЛКМ.
        Возвращает {"drop_item": Item|None, "kill_world_item": WorldItem|None}.
        """
        result = {"drop_item": None, "kill_world_item": None}

        if self._panel_dragging:
            self._panel_dragging = False
            return result

        if self._drag is None:
            return result

        drag       = self._drag
        self._drag = None

        cell = self._pos_to_cell(pos)

        if cell is not None:
            col, row = cell
            # смещаем на grab-offset чтобы предмет «лёг» туда откуда тащили
            target_col = col - drag.grab_col
            target_row = row - drag.grab_row

            grid = self.player.backpack
            placed = grid.place(drag.item, target_col, target_row)

            if placed:
                if drag.source_world_item:
                    result["kill_world_item"] = drag.source_world_item
                return result

        # не попали в сетку или не влезло
        if drag.source_grid is not None:
            result["drop_item"] = drag.item
        elif drag.source_slot is not None:
            # Если курсор вне панели рюкзака — дропаем на пол
            # Если рюкзак открыт и курсор над сеткой но не влезло — тоже на пол
            px, py = int(self._panel_pos.x), int(self._panel_pos.y)
            pw, ph = self._panel_size
            inside_panel = pygame.Rect(px, py, pw, ph).collidepoint(pos)
            if inside_panel and drag.source_slot.item is None:
                # промахнулся внутри открытой панели — возврат в слот
                drag.source_slot.item = drag.item
            else:
                # дропнул вне панели — на пол
                result["drop_item"] = drag.item
        # из мира — WorldItem остаётся на полу, ничего не делаем

        return result

    def handle_mouse_motion(self, pos: tuple) -> None:
        if self._panel_dragging:
            pw, ph = self._panel_size
            nx = max(0, min(pos[0] - self._panel_drag_offset.x, self.s.screen_width  - pw))
            ny = max(0, min(pos[1] - self._panel_drag_offset.y, self.s.screen_height - ph))
            self._panel_pos.update(nx, ny)
            return
        self._hover_cell = self._pos_to_cell(pos)

    def handle_key_down(self, key: int) -> None:
        """Ctrl во время drag — поворачиваем предмет."""
        if self._drag and key in (pygame.K_LCTRL, pygame.K_RCTRL):
            self.player.backpack.rotate_free(self._drag.item)

    def start_drag_from_slot(self, item, source_slot) -> None:
        """
        Начать drag из внешнего Slot (pouch-панель).
        Предмет будет вести себя как обычный grid-drag — тень, точная вставка по ячейке.
        """
        self._drag = GridDragState(
            item=item,
            source_grid=None,
            source_slot=source_slot,
            source_world_item=None,
            grab_col=0,
            grab_row=0,
        )

    def get_tooltip(self, pos: tuple) -> str:
        """Возвращает текст тултипа для предмета под курсором."""
        cell = self._pos_to_cell(pos)
        if cell is None:
            return ""
        item = self.player.backpack.item_at(*cell)
        return item.get_tooltip() if item else ""

    def item_at_pos(self, pos: tuple) -> Optional[Item]:
        cell = self._pos_to_cell(pos)
        if cell is None:
            return None
        return self.player.backpack.item_at(*cell)

    def title_rect(self) -> pygame.Rect:
        px, py = int(self._panel_pos.x), int(self._panel_pos.y)
        return pygame.Rect(px, py, self._panel_size[0], TITLE_H)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface) -> None:
        px, py = int(self._panel_pos.x), int(self._panel_pos.y)
        pw, ph = self._panel_size
        grid   = self.player.backpack

        # фон панели
        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        surf.fill(_PANEL_BG)
        screen.blit(surf, (px, py))
        pygame.draw.rect(screen, _PANEL_BORDER, (px, py, pw, ph), 1)

        # заголовок
        title_bg = _TITLE_DRAG_BG if self._panel_dragging else _TITLE_BG
        pygame.draw.rect(screen, title_bg, (px, py, pw, TITLE_H))
        pygame.draw.rect(screen, _PANEL_BORDER, (px, py, pw, TITLE_H), 1)
        cap = self.font_md.render("Backpack", True, _TEXT_COLOR)
        screen.blit(cap, (px + 10, py + (TITLE_H - cap.get_height()) // 2))

        ox = px + 12
        oy = py + TITLE_H + 8

        # пустые ячейки
        for row in range(grid.rows):
            for col in range(grid.cols):
                r = self._cell_rect(col, row, ox, oy)
                bg = _CELL_HOVER if self._hover_cell == (col, row) else _CELL_BG
                pygame.draw.rect(screen, bg,          r)
                pygame.draw.rect(screen, _CELL_BORDER, r, 1)

        # предметы
        for item in grid.all_items():
            placement = grid.placement_of(item)
            self._draw_item(screen, item, placement.col, placement.row, ox, oy)

        # тень drag'а
        if self._drag:
            self._draw_drag_shadow(screen, ox, oy)

    def draw_dragged_item(self, screen: pygame.Surface) -> None:
        """Рисует иконку предмета под курсором (вызывается из HUD поверх всего)."""
        if not self._drag:
            return
        item       = self._drag.item
        mx, my     = pygame.mouse.get_pos()
        w, h       = item.effective_size
        icon_w     = w * (CELL + CELL_PAD) - CELL_PAD
        icon_h     = h * (CELL + CELL_PAD) - CELL_PAD
        icon       = self._make_item_icon(item, icon_w, icon_h)
        # центрируем на ячейке захвата
        draw_x = mx - self._drag.grab_col * (CELL + CELL_PAD) - CELL // 2
        draw_y = my - self._drag.grab_row * (CELL + CELL_PAD) - CELL // 2
        screen.blit(icon, (draw_x, draw_y))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _origin(self):
        """(ox, oy) — верхний левый угол сетки."""
        px, py = int(self._panel_pos.x), int(self._panel_pos.y)
        return px + 12, py + TITLE_H + 8

    def _cell_rect(self, col: int, row: int, ox: int, oy: int) -> pygame.Rect:
        return pygame.Rect(
            ox + col * (CELL + CELL_PAD),
            oy + row * (CELL + CELL_PAD),
            CELL, CELL,
        )

    def _pos_to_cell(self, pos: tuple) -> Optional[tuple[int, int]]:
        """Экранные координаты → (col, row) или None если вне сетки."""
        ox, oy = self._origin()
        grid   = self.player.backpack
        mx, my = pos
        col = (mx - ox) // (CELL + CELL_PAD)
        row = (my - oy) // (CELL + CELL_PAD)
        if 0 <= col < grid.cols and 0 <= row < grid.rows:
            # проверяем что попали именно в ячейку, а не в padding
            cr = self._cell_rect(col, row, ox, oy)
            if cr.collidepoint(pos):
                return (col, row)
        return None

    def _draw_item(
        self, screen: pygame.Surface,
        item: Item, col: int, row: int,
        ox: int, oy: int,
    ) -> None:
        w, h   = item.effective_size
        icon_w = w * (CELL + CELL_PAD) - CELL_PAD
        icon_h = h * (CELL + CELL_PAD) - CELL_PAD
        x      = ox + col * (CELL + CELL_PAD)
        y      = oy + row * (CELL + CELL_PAD)
        icon   = self._make_item_icon(item, icon_w, icon_h)
        screen.blit(icon, (x, y))
        self._draw_item_overlays(screen, item, pygame.Rect(x, y, icon_w, icon_h))

    def _make_item_icon(self, item: Item, w: int, h: int) -> pygame.Surface:
        """
        Масштабирует иконку предмета до нужного размера.
        Если предмет повёрнут (grid_rotated), поворачивает на 90°.
        """
        base = item.icon
        if item.grid_rotated:
            # rotate возвращает повёрнутую поверхность
            base = pygame.transform.rotate(base, -90)
        return pygame.transform.scale(base, (w, h))

    def _draw_item_overlays(
        self, screen: pygame.Surface, item: Item, rect: pygame.Rect
    ) -> None:
        """Полоска чистоты оружия, стак-каунт патронов, иконка клина."""
        from items.weapon_item import WeaponItem
        if isinstance(item, WeaponItem):
            clean = item.cleanliness
            bw = rect.width - 4
            bh = 3
            bx = rect.x + 2
            by = rect.bottom - bh - 2
            if   clean >= 0.75: bar_c = (80, 180, 80)
            elif clean >= 0.50: bar_c = (200, 180, 40)
            elif clean >= 0.25: bar_c = (220, 120, 40)
            else:               bar_c = (200, 50,  50)
            pygame.draw.rect(screen, (20, 20, 30), (bx, by, bw, bh))
            pygame.draw.rect(screen, bar_c,        (bx, by, int(bw * clean), bh))
            if item.jammed:
                j = self.font_sm.render("J", True, (220, 60, 60))
                screen.blit(j, (rect.x + 3, rect.y + 3))
            return

        if item.stackable and item.stack_count > 1:
            cnt = self.font_sm.render(str(item.stack_count), True, (200, 200, 160))
            screen.blit(cnt, (rect.right - cnt.get_width() - 3,
                               rect.bottom - cnt.get_height() - 2))

    def _draw_drag_shadow(self, screen: pygame.Surface, ox: int, oy: int) -> None:
        """
        Рисует полупрозрачную тень предмета на сетке там, где он упадёт.
        Зелёная — можно положить, красная — занято / выходит за границы.
        """
        if self._hover_cell is None:
            return
        drag  = self._drag
        item  = drag.item
        w, h  = item.effective_size
        col   = self._hover_cell[0] - drag.grab_col
        row   = self._hover_cell[1] - drag.grab_row
        grid  = self.player.backpack
        can   = grid.can_place(item, col, row)

        fill_c   = _PLACE_OK   if can else _PLACE_FAIL
        border_c = _PLACE_OK_BRD if can else _PLACE_FAIL_BRD

        shadow_w = w * (CELL + CELL_PAD) - CELL_PAD
        shadow_h = h * (CELL + CELL_PAD) - CELL_PAD
        x = ox + col * (CELL + CELL_PAD)
        y = oy + row * (CELL + CELL_PAD)

        surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        surf.fill(fill_c)
        screen.blit(surf, (x, y))
        pygame.draw.rect(screen, border_c, (x, y, shadow_w, shadow_h), 2)
