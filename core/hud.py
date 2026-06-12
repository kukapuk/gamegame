import pygame
from dataclasses import dataclass
from typing import Optional
from core.settings import Settings
from actors.player import Player
from items.item import ItemType
from items.inventory import Slot, Inventory


@dataclass
class DragState:
    item: object
    source_inv: object
    source_slot: object
    source_world_item: object = None
    icon_size: int = 40


class HUD:
    """
    Рисует весь UI поверх игрового мира.
    Владеет состоянием drag & drop, перемещением панели рюкзака.
    """

    POUCH_KEY_LABELS  = ["Z", "X", "C", "V"]
    SLOT_SIZE         = 48
    SMALL_SLOT        = 24
    SLOT_PAD          = 4
    COLS_BACKPACK     = 4
    TITLE_H           = 28
    SLOT_BG           = (35, 35, 45)
    SLOT_BORDER       = (70, 70, 90)
    SLOT_TYPED_BG     = (25, 30, 50)
    SLOT_TYPED_BORDER = (60, 80, 140)
    SLOT_HOVER        = (55, 55, 70)
    TITLE_BG          = (28, 30, 45)
    TITLE_DRAG_BG     = (38, 42, 65)
    TEXT_COLOR        = (200, 200, 210)
    TOOLTIP_BG        = (20, 20, 30, 210)
    PANEL_BG          = (20, 22, 32, 230)
    PANEL_BORDER      = (60, 65, 90)
    MARGIN            = 20

    def __init__(self, settings: Settings, player: Player) -> None:
        self.s      = settings
        self.player = player
        self.font_sm = pygame.font.SysFont("monospace", 11)
        self.font_md = pygame.font.SysFont("monospace", 13)

        self.pouch_open: bool    = False
        self.backpack_open: bool = False

        self._drag: Optional[DragState]           = None
        self._tooltip_text: str                   = ""
        self._hovered_rect: Optional[pygame.Rect] = None
        self._hovered_world_item                  = None

        self._backpack_slot_rects: list      = []
        self._pouch_panel_slot_rects: list   = []
        self._info_panels: list              = []   # список открытых инфо-панелей
        self._hovered_item                   = None  # предмет под курсором

        ss      = self.SLOT_SIZE
        pad     = self.SLOT_PAD
        cols    = self.COLS_BACKPACK
        rows    = (16 + cols - 1) // cols
        panel_w = cols * ss + (cols - 1) * pad + 24
        panel_h = rows * ss + (rows - 1) * pad + self.TITLE_H + 22

        self._backpack_pos        = pygame.Vector2(
            settings.screen_width - panel_w - self.MARGIN,
            settings.screen_height // 2 - panel_h // 2,
        )
        self._backpack_panel_size = (panel_w, panel_h)
        self._panel_dragging      = False
        self._panel_drag_offset   = pygame.Vector2(0, 0)

    def toggle_pouch(self) -> None:
        self.pouch_open = not self.pouch_open

    def open_backpack(self) -> None:
        self.backpack_open = True

    def close_backpack(self) -> None:
        self.backpack_open = False
        if self._drag:
            if self._drag.source_slot:
                self._drag.source_slot.item = self._drag.item
            self._drag = None
        self._panel_dragging        = False
        self._hovered_world_item    = None
        self._hovered_rect          = None
        self._tooltip_text          = ""
        self._backpack_slot_rects   = []
        self._pouch_panel_slot_rects = []
        self._info_panels           = []

    def is_open(self) -> bool:
        return self.backpack_open

    def handle_mouse_down(self, pos: tuple) -> None:
        if not self.backpack_open:
            return
        # сначала проверяем инфо-панели
        if self.handle_info_panels_mouse_down(pos):
            return
        if self._backpack_title_rect().collidepoint(pos):
            self._panel_dragging = True
            self._panel_drag_offset.update(
                pos[0] - self._backpack_pos.x,
                pos[1] - self._backpack_pos.y,
            )
            return
        for slot, rect in self._all_interactive_rects():
            if rect.collidepoint(pos) and not slot.empty:
                self._drag = DragState(
                    item=slot.item,
                    source_inv=self._inv_for_slot(slot),
                    source_slot=slot,
                    icon_size=rect.width - 4,
                )
                slot.take()
                return

    def handle_world_mouse_down(self, pos: tuple, world_items, camera_offset) -> bool:
        if not self.backpack_open:
            return False
        for wi in world_items:
            if not wi.is_in_pickup_range(self.player.pos):
                continue
            screen_rect = wi.rect.move(-camera_offset.x, -camera_offset.y)
            if screen_rect.collidepoint(pos):
                self._drag = DragState(
                    item=wi.item,
                    source_inv=None,
                    source_slot=None,
                    source_world_item=wi,
                    icon_size=max(wi.rect.width, 20),
                )
                return True
        return False

    def update_world_hover(self, pos: tuple, world_items, camera_offset) -> None:
        if not self.backpack_open:
            self._hovered_world_item = None
            return
        self._hovered_world_item = None
        for wi in world_items:
            if not wi.is_in_pickup_range(self.player.pos):
                continue
            screen_rect = wi.rect.move(-camera_offset.x, -camera_offset.y)
            if screen_rect.collidepoint(pos):
                self._hovered_world_item = wi
                break

    def handle_mouse_up(self, pos: tuple) -> dict:
        result = {"kill_world_item": None, "drop_item": None}
        self.handle_info_panels_mouse_up()

        if self._panel_dragging:
            self._panel_dragging = False
            return result
        if not self._drag:
            return result

        for slot, rect in self._all_interactive_rects():
            if rect.collidepoint(pos) and slot is not self._drag.source_slot:
                drag_item   = self._drag.item
                target_item = slot.item

                # --- CleaningKit на оружие ---
                from items.cleaning_kit import CleaningKit
                from items.weapon_item import WeaponItem
                if (isinstance(drag_item, CleaningKit)
                        and isinstance(target_item, WeaponItem)):
                    drag_item.apply_to_weapon(target_item)
                    if self._drag.source_world_item:
                        result["kill_world_item"] = self._drag.source_world_item
                    self._drag = None
                    return result

                if (target_item and drag_item.stackable
                        and type(target_item) == type(drag_item)
                        and hasattr(target_item, 'ammo_type')
                        and target_item.ammo_type == drag_item.ammo_type
                        and target_item.stack_count < target_item.max_stack):
                    space = target_item.max_stack - target_item.stack_count
                    take  = min(space, drag_item.stack_count)
                    target_item.stack_count += take
                    drag_item.stack_count   -= take
                    if drag_item.stack_count <= 0:
                        if self._drag.source_slot:
                            self._drag.source_slot.item = None
                        self._drag = None
                    else:
                        if self._drag.source_slot:
                            self._drag.source_slot.item = drag_item
                        self._drag = None
                    return result

                if not slot.accepts(drag_item):
                    continue
                source_slot  = self._drag.source_slot
                source_world = self._drag.source_world_item
                old_item     = slot.item

                if source_slot and old_item and not source_slot.accepts(old_item):
                    continue

                old_item = slot.take()
                slot.put(self._drag.item)
                self._drag = None

                if source_slot:
                    source_slot.take()
                    if old_item:
                        source_slot.put(old_item)
                elif source_world:
                    result["kill_world_item"] = source_world

                return result

        source_slot  = self._drag.source_slot
        source_world = self._drag.source_world_item

        if source_slot:
            result["drop_item"] = self._drag.item
        self._drag = None
        return result

    def handle_mouse_motion(self, pos: tuple) -> None:
        self.handle_info_panels_mouse_motion(pos)
        if self._panel_dragging:
            pw, ph  = self._backpack_panel_size
            new_x   = max(0, min(pos[0] - self._panel_drag_offset.x, self.s.screen_width  - pw))
            new_y   = max(0, min(pos[1] - self._panel_drag_offset.y, self.s.screen_height - ph))
            self._backpack_pos.update(new_x, new_y)
            return
        self._tooltip_text  = ""
        self._hovered_rect  = None
        for slot, rect in self._all_interactive_rects():
            if rect.collidepoint(pos):
                self._hovered_rect = rect
                if not slot.empty:
                    self._tooltip_text = slot.item.get_tooltip()

    def draw(self, screen: pygame.Surface, i_hold_progress: float = 0.0, weapon=None) -> None:
        self._draw_hp_bar(screen)
        self._draw_stamina_bar(screen)
        self._draw_quick_slots(screen)
        if weapon and weapon.has_weapon:
            self._draw_ammo_counter(screen, weapon)
        if self.pouch_open:
            self._draw_pouch_panel(screen)
        if self.backpack_open:
            self._draw_backpack(screen)
        if self._drag:
            self._draw_dragged_item(screen)
        if i_hold_progress > 0:
            self._draw_i_progress(screen, i_hold_progress)
        self._draw_tooltip(screen, pygame.mouse.get_pos())
        self.draw_info_panels(screen)

    def draw_world_hover(self, screen: pygame.Surface, camera_offset) -> None:
        if not self._hovered_world_item or not self.backpack_open:
            return
        wi  = self._hovered_world_item
        r   = wi.rect.move(-camera_offset.x, -camera_offset.y)
        pad = 6
        hover = pygame.Surface((r.width + pad * 2, r.height + pad * 2), pygame.SRCALPHA)
        hover.fill((180, 200, 255, 60))
        pygame.draw.rect(hover, (140, 170, 255, 160), hover.get_rect(), 1)
        screen.blit(hover, (r.x - pad, r.y - pad))

    def _backpack_title_rect(self) -> pygame.Rect:
        pw, _ = self._backpack_panel_size
        return pygame.Rect(int(self._backpack_pos.x), int(self._backpack_pos.y), pw, self.TITLE_H)

    def _bar_baseline(self) -> int:
        return self.s.screen_height - self.MARGIN

    def _all_interactive_rects(self):
        yield from self._quick_slot_rects()
        yield from self._pouch_panel_slot_rects
        yield from self._backpack_slot_rects

    def _inv_for_slot(self, slot: Slot) -> Inventory:
        for s in self.player.pouch.all_slots():
            if s is slot:
                return self.player.pouch
        return self.player.backpack

    def _quick_slot_rects(self):
        ox  = self.MARGIN + self.s.player_hp_bar_width + 12
        oy  = self._bar_baseline() - self.SMALL_SLOT
        ss  = self.SMALL_SLOT
        pad = self.SLOT_PAD
        for i, slot in enumerate(self.player.pouch.slots):
            yield slot, pygame.Rect(ox + i * (ss + pad), oy, ss, ss)

    def _draw_ammo_counter(self, screen: pygame.Surface, weapon) -> None:
        ox      = self.MARGIN + self.s.player_hp_bar_width + 12
        ss      = self.SMALL_SLOT
        pad     = self.SLOT_PAD
        slots_w = len(list(self.player.pouch.slots)) * (ss + pad)
        x       = ox + slots_w + 12
        y       = self._bar_baseline() - ss

        if weapon.jammed:
            # JAMMED — мигающий красный, подсказка
            lbl = self.font_md.render("JAMMED", True, (220, 60, 60))
            screen.blit(lbl, (x, y + (ss - lbl.get_height()) // 2))
            hint = self.font_sm.render("[R] reload  [Q] unjam", True, (160, 80, 80))
            screen.blit(hint, (x, y + (ss - hint.get_height()) // 2 + 14))
            return

        if weapon.unjamming:
            progress = 1.0 - weapon._unjam_timer / 0.5
            bw, bh   = 90, 5
            pygame.draw.rect(screen, (40, 40, 60),   (x, y + ss - bh - 2, bw, bh))
            pygame.draw.rect(screen, (200, 100, 40), (x, y + ss - bh - 2, int(bw * progress), bh))
            lbl = self.font_md.render("CYCLING...", True, (200, 120, 60))
            screen.blit(lbl, (x, y + (ss - lbl.get_height()) // 2))
            return

        if weapon.reloading:
            progress = 1.0 - weapon._reload_timer / weapon._weapon_item.stats.reload_time
            bw, bh   = 90, 5
            pygame.draw.rect(screen, (40, 40, 60),   (x, y + ss - bh - 2, bw, bh))
            pygame.draw.rect(screen, (180, 140, 40), (x, y + ss - bh - 2, int(bw * progress), bh))
            lbl = self.font_md.render("RELOADING", True, (220, 180, 60))
        else:
            text  = f"{weapon.mag_current} / {weapon.mag_size}"
            color = (220, 220, 220) if weapon.mag_current > 0 else (220, 60, 60)
            lbl   = self.font_md.render(text, True, color)

        screen.blit(lbl, (x, y + (ss - lbl.get_height()) // 2))

        # полоска чистоты оружия
        wi = weapon._weapon_item
        if wi:
            bw, bh = 90, 3
            by2    = y + ss - bh - 2
            clean  = wi.cleanliness
            if clean >= 0.75:
                bar_color = (80, 180, 80)
            elif clean >= 0.5:
                bar_color = (200, 180, 40)
            elif clean >= 0.25:
                bar_color = (220, 120, 40)
            else:
                bar_color = (200, 50, 50)
            pygame.draw.rect(screen, (30, 30, 50),  (x, by2, bw, bh))
            pygame.draw.rect(screen, bar_color,     (x, by2, int(bw * clean), bh))

    def _draw_i_progress(self, screen: pygame.Surface, progress: float) -> None:
        bw, bh = 120, 6
        cx     = self.s.screen_width // 2
        by     = self.s.screen_height - self.MARGIN - bh - 60
        bx     = cx - bw // 2
        pygame.draw.rect(screen, (30, 30, 50),    (bx, by, bw, bh))
        fill = int(bw * min(progress, 1.0))
        if fill > 0:
            pygame.draw.rect(screen, (120, 160, 220), (bx, by, fill, bh))
        pygame.draw.rect(screen, (60, 65, 90),    (bx, by, bw, bh), 1)
        label = "Opening..." if not self.backpack_open else "Closing..."
        lbl   = self.font_sm.render(label, True, (140, 150, 180))
        screen.blit(lbl, (cx - lbl.get_width() // 2, by - 16))

    def _draw_hp_bar(self, screen: pygame.Surface) -> None:
        s       = self.s
        bw, bh  = s.player_hp_bar_width, s.player_hp_bar_height
        bx, by  = self.MARGIN, self._bar_baseline() - bh
        pygame.draw.rect(screen, s.player_hp_bar_bg,    (bx, by, bw, bh))
        fill = int(bw * self.player.hp / self.player.max_hp)
        if fill > 0:
            pygame.draw.rect(screen, s.player_hp_bar_color, (bx, by, fill, bh))
        pygame.draw.rect(screen, (80, 80, 80), (bx, by, bw, bh), 1)

    def _draw_stamina_bar(self, screen: pygame.Surface) -> None:
        s   = self.s
        bw  = s.player_hp_bar_width
        bh  = 5
        bx  = self.MARGIN
        by  = self._bar_baseline() - s.player_hp_bar_height - 3 - bh
        pygame.draw.rect(screen, (30, 30, 50),  (bx, by, bw, bh))
        fill = int(bw * self.player.stamina / self.player.stats.max_stamina)
        if fill > 0:
            pygame.draw.rect(screen, (80, 140, 220), (bx, by, fill, bh))
        pygame.draw.rect(screen, (60, 60, 90),  (bx, by, bw, bh), 1)

    def _draw_quick_slots(self, screen: pygame.Surface) -> None:
        ss = self.SMALL_SLOT
        for i, (slot, rect) in enumerate(self._quick_slot_rects()):
            bg = self.SLOT_HOVER if rect == self._hovered_rect else self.SLOT_BG
            pygame.draw.rect(screen, bg,              rect)
            pygame.draw.rect(screen, self.SLOT_BORDER, rect, 1)
            if not slot.empty:
                icon = pygame.transform.scale(slot.item.icon, (ss - 4, ss - 4))
                screen.blit(icon, icon.get_rect(center=rect.center))
            if i < len(self.POUCH_KEY_LABELS):
                lbl = self.font_sm.render(self.POUCH_KEY_LABELS[i], True, (100, 100, 120))
                screen.blit(lbl, (rect.right - lbl.get_width() - 2, rect.bottom - lbl.get_height() - 1))

    def _draw_pouch_panel(self, screen: pygame.Surface) -> None:
        weapon_w  = 56
        weapon_h  = 28
        armor_sz  = 64
        inner_pad = 10
        pad       = self.SLOT_PAD
        panel_w   = weapon_w + inner_pad + armor_sz + inner_pad + weapon_w + inner_pad * 2
        panel_h   = armor_sz + inner_pad * 2
        ox        = self.MARGIN
        oy        = self._bar_baseline() - self.s.player_hp_bar_height - panel_h - 16

        surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        surf.fill(self.PANEL_BG)
        screen.blit(surf, (ox, oy))
        pygame.draw.rect(screen, self.PANEL_BORDER, (ox, oy, panel_w, panel_h), 1)

        typed_slots  = self.player.pouch.typed_slots
        weapon_slots = [s for s in typed_slots if s.allowed_type == ItemType.WEAPON]
        armor_slots  = [s for s in typed_slots if s.allowed_type == ItemType.ARMOR]

        self._pouch_panel_slot_rects = []
        cx = ox + inner_pad

        for i, slot in enumerate(weapon_slots):
            r = pygame.Rect(cx, oy + inner_pad + i * (weapon_h + pad), weapon_w, weapon_h)
            self._pouch_panel_slot_rects.append((slot, r))
            self._draw_slot(screen, slot, r, typed=True)
            lbl = self.font_sm.render("WEAPON", True, (70, 90, 150))
            screen.blit(lbl, (r.x + 3, r.y + 3))

        cx += weapon_w + inner_pad
        for slot in armor_slots:
            r = pygame.Rect(cx, oy + inner_pad, armor_sz, armor_sz)
            self._pouch_panel_slot_rects.append((slot, r))
            self._draw_slot(screen, slot, r, typed=True)
            lbl = self.font_sm.render("ARMOR", True, (70, 90, 150))
            screen.blit(lbl, (r.x + 3, r.y + 3))

    def _draw_backpack(self, screen: pygame.Surface) -> None:
        ss     = self.SLOT_SIZE
        pad    = self.SLOT_PAD
        cols   = self.COLS_BACKPACK
        slots  = self.player.backpack.all_slots()
        pw, ph = self._backpack_panel_size
        px     = int(self._backpack_pos.x)
        py     = int(self._backpack_pos.y)

        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        surf.fill(self.PANEL_BG)
        screen.blit(surf, (px, py))
        pygame.draw.rect(screen, self.PANEL_BORDER, (px, py, pw, ph), 1)

        title_bg = self.TITLE_DRAG_BG if self._panel_dragging else self.TITLE_BG
        pygame.draw.rect(screen, title_bg, (px, py, pw, self.TITLE_H))
        pygame.draw.rect(screen, self.PANEL_BORDER, (px, py, pw, self.TITLE_H), 1)

        title = self.font_md.render(f"Backpack", True, (160, 160, 180))
        screen.blit(title, (px + 10, py + (self.TITLE_H - title.get_height()) // 2))

        ox = px + 12
        oy = py + self.TITLE_H + 10
        self._backpack_slot_rects = []

        for i, slot in enumerate(slots):
            col, row = i % cols, i // cols
            r        = pygame.Rect(ox + col * (ss + pad), oy + row * (ss + pad), ss, ss)
            self._backpack_slot_rects.append((slot, r))
            bg = self.SLOT_HOVER if r == self._hovered_rect else self.SLOT_BG
            pygame.draw.rect(screen, bg,               r)
            pygame.draw.rect(screen, self.SLOT_BORDER, r, 1)
            if not slot.empty:
                icon = pygame.transform.scale(slot.item.icon, (ss - 4, ss - 4))
                screen.blit(icon, icon.get_rect(center=r.center))
                if slot.item.stackable and slot.item.stack_count > 1:
                    cnt = self.font_sm.render(str(slot.item.stack_count), True, (200, 200, 160))
                    screen.blit(cnt, (r.right - cnt.get_width() - 3, r.bottom - cnt.get_height() - 2))
                self._draw_weapon_condition(screen, slot.item, r)

    def _draw_dragged_item(self, screen: pygame.Surface) -> None:
        mx, my = pygame.mouse.get_pos()
        sz     = self._drag.icon_size
        icon   = pygame.transform.scale(self._drag.item.icon, (sz, sz))
        screen.blit(icon, (mx - sz // 2, my - sz // 2))

    def _draw_tooltip(self, screen: pygame.Surface, pos: tuple) -> None:
        if not self._tooltip_text or self._drag:
            return
        surf = self.font_sm.render(self._tooltip_text, True, (255, 255, 200))
        pad  = 6
        bg   = pygame.Surface((surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA)
        bg.fill(self.TOOLTIP_BG)
        screen.blit(bg,   (pos[0] + 12, pos[1] - bg.get_height()))
        screen.blit(surf, (pos[0] + 12 + pad, pos[1] - bg.get_height() + pad))

    def _draw_slot(self, screen: pygame.Surface, slot: Slot, rect: pygame.Rect, typed: bool = False) -> None:
        bg     = self.SLOT_HOVER if rect == self._hovered_rect else (self.SLOT_TYPED_BG if typed else self.SLOT_BG)
        border = self.SLOT_TYPED_BORDER if typed else self.SLOT_BORDER
        pygame.draw.rect(screen, bg,     rect)
        pygame.draw.rect(screen, border, rect, 1)
        if slot and not slot.empty:
            icon = pygame.transform.scale(slot.item.icon, (rect.width - 4, rect.height - 4))
            screen.blit(icon, icon.get_rect(center=rect.center))
            self._draw_weapon_condition(screen, slot.item, rect)

    def _draw_weapon_condition(self, screen: pygame.Surface, item, rect: pygame.Rect) -> None:
        """Полоска чистоты + иконка клина поверх слота с оружием."""
        from items.weapon_item import WeaponItem
        if not isinstance(item, WeaponItem):
            return
        clean = item.cleanliness
        bw    = rect.width - 4
        bh    = 3
        bx    = rect.x + 2
        by    = rect.bottom - bh - 2
        if clean >= 0.75:
            bar_color = (80, 180, 80)
        elif clean >= 0.5:
            bar_color = (200, 180, 40)
        elif clean >= 0.25:
            bar_color = (220, 120, 40)
        else:
            bar_color = (200, 50, 50)
        pygame.draw.rect(screen, (20, 20, 30),  (bx, by, bw, bh))
        pygame.draw.rect(screen, bar_color,     (bx, by, int(bw * clean), bh))
        if item.jammed:
            j = self.font_sm.render("J", True, (220, 60, 60))
            screen.blit(j, (rect.x + 3, rect.y + 3))

    # Hover tooltip (короткий)

    def _get_item_at(self, pos: tuple):
        """Возвращает предмет под курсором в любом открытом слоте."""
        for slot, rect in self._all_interactive_rects():
            if rect.collidepoint(pos) and not slot.empty:
                return slot.item
        return None

    # RMB — открыть инфо-панель

    def handle_rmb(self, pos: tuple) -> None:
        if not self.backpack_open:
            return
        item = self._get_item_at(pos)
        if item is None:
            return
        # не открывать дубликат той же панели
        for panel in self._info_panels:
            if panel["item"] is item:
                return
        pw, ph = 220, 140
        # позиция — рядом с курсором, не выходить за экран
        px = min(pos[0] + 8, self.s.screen_width  - pw - 4)
        py = min(pos[1] + 8, self.s.screen_height - ph - 4)
        self._info_panels.append({
            "item":      item,
            "pos":       pygame.Vector2(px, py),
            "size":      (pw, ph),
            "dragging":  False,
            "drag_off":  pygame.Vector2(0, 0),
        })

    def handle_info_panels_mouse_down(self, pos: tuple) -> bool:
        """ЛКМ по панели — начать перетаскивание или закрыть по X.
        Возвращает True если клик был поглощён панелью."""
        for panel in reversed(self._info_panels):
            px, py = int(panel["pos"].x), int(panel["pos"].y)
            pw, ph = panel["size"]
            # кнопка X (верхний правый угол)
            x_rect = pygame.Rect(px + pw - 16, py + 2, 14, 14)
            if x_rect.collidepoint(pos):
                self._info_panels.remove(panel)
                return True
            # заголовок — перетаскивание
            title_rect = pygame.Rect(px, py, pw, 20)
            if title_rect.collidepoint(pos):
                panel["dragging"] = True
                panel["drag_off"].update(pos[0] - px, pos[1] - py)
                return True
        return False

    def handle_info_panels_mouse_up(self) -> None:
        for panel in self._info_panels:
            panel["dragging"] = False

    def handle_info_panels_mouse_motion(self, pos: tuple) -> None:
        for panel in self._info_panels:
            if panel["dragging"]:
                pw, ph = panel["size"]
                nx = max(0, min(pos[0] - panel["drag_off"].x, self.s.screen_width  - pw))
                ny = max(0, min(pos[1] - panel["drag_off"].y, self.s.screen_height - ph))
                panel["pos"].update(nx, ny)

    def update_info_panels_hover(self, pos: tuple) -> None:
        """Закрывает панель если курсор ушёл далеко за её пределы."""
        for panel in self._info_panels[:]:
            px, py = int(panel["pos"].x), int(panel["pos"].y)
            pw, ph = panel["size"]
            expanded = pygame.Rect(px - 40, py - 40, pw + 80, ph + 80)
            if not expanded.collidepoint(pos):
                self._info_panels.remove(panel)

    # Draw инфо-панелей

    def draw_info_panels(self, screen: pygame.Surface) -> None:
        if not self.backpack_open:
            return
        for panel in self._info_panels:
            self._draw_info_panel(screen, panel)

    def _draw_info_panel(self, screen: pygame.Surface, panel: dict) -> None:
        item  = panel["item"]
        px    = int(panel["pos"].x)
        py    = int(panel["pos"].y)
        pw, ph = panel["size"]
        pad   = 8

        # фон
        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        surf.fill((16, 18, 30, 235))
        screen.blit(surf, (px, py))
        pygame.draw.rect(screen, (60, 65, 100), (px, py, pw, ph), 1, border_radius=6)

        # заголовок
        pygame.draw.rect(screen, (28, 32, 52), (px, py, pw, 22), border_radius=6)
        name_surf = self.font_md.render(item.name, True, (200, 205, 225))
        screen.blit(name_surf, (px + pad, py + 4))

        # кнопка X
        x_rect = pygame.Rect(px + pw - 16, py + 2, 14, 14)
        pygame.draw.rect(screen, (60, 40, 40), x_rect, border_radius=3)
        x_lbl = self.font_sm.render("x", True, (200, 120, 120))
        screen.blit(x_lbl, x_lbl.get_rect(center=x_rect.center))

        # иконка
        icon = pygame.transform.scale(item.icon, (36, 36))
        screen.blit(icon, (px + pad, py + 28))

        # характеристики
        lines = self._item_info_lines(item)
        ty = py + 28
        for line in lines:
            lbl = self.font_sm.render(line, True, (170, 175, 195))
            screen.blit(lbl, (px + pad + 42, ty))
            ty += 14

    def _item_info_lines(self, item) -> list[str]:
        from items.weapon_item import WeaponItem
        from items.ammo import AmmoItem
        from items.armor import Armor
        from items.consumable import Consumable
        from items.cleaning_kit import CleaningKit

        if isinstance(item, WeaponItem):
            s = item.stats
            return [
                f"DMG:    {s.damage}",
                f"AP:     {s.armor_pen}",
                f"Mag:    {item.mag_current}/{s.mag_size}",
                f"Clean:  {int(item.cleanliness * 100)}%",
                f"Fire:   {'auto' if s.auto_fire else 'semi'}",
                f"Reload: {s.reload_time}s",
            ]
        if isinstance(item, AmmoItem):
            return [
                f"Type:  {item.ammo_type.name}",
                f"Count: {item.stack_count}/{item.max_stack}",
            ]
        if isinstance(item, Armor):
            return [
                f"Tier:   {item.tier}",
                f"Dash:   x{item.dash_stamina_mult:.2f}",
                f"Sprint: {item.sprint_stamina_drain}/s",
            ]
        if isinstance(item, CleaningKit):
            return [f"Restores: +{int(item.heal_amount * 100)}% clean"]
        if isinstance(item, Consumable):
            return [item.get_tooltip()]
        return [item.get_tooltip()]
