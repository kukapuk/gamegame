import pygame
from core.settings import Settings
from entities.actors.player import Player
from entities.items.item import ItemType


class HUD:
    """
    Рисует весь UI поверх игрового мира.
    Получает ссылку на Player и читает данные напрямую.
    """

    POUCH_KEY_LABELS  = ["Z", "X", "C", "V"]
    SLOT_SIZE         = 48
    SMALL_SLOT        = 24
    SLOT_PAD          = 4
    SLOT_BG           = (35, 35, 45)
    SLOT_BORDER       = (70, 70, 90)
    SLOT_TYPED_BG     = (25, 30, 50)
    SLOT_TYPED_BORDER = (60, 80, 140)
    TEXT_COLOR        = (200, 200, 210)
    TOOLTIP_BG        = (20, 20, 30, 210)
    PANEL_BG          = (20, 22, 32, 230)
    PANEL_BORDER      = (60, 65, 90)
    MARGIN            = 20

    def __init__(self, settings: Settings, player: Player) -> None:
        self.s = settings
        self.player = player
        self.font_sm = pygame.font.SysFont("monospace", 11)
        self.font_md = pygame.font.SysFont("monospace", 13)
        self._tooltip_text: str = ""
        self.pouch_open: bool = False

    def draw(self, screen: pygame.Surface) -> None:
        self._draw_hp_bar(screen)
        self._draw_stamina_bar(screen)
        self._draw_quick_slots(screen)
        if self.pouch_open:
            self._draw_pouch_panel(screen)

    def toggle_pouch(self) -> None:
        self.pouch_open = not self.pouch_open

    def handle_mouse_motion(self, screen_pos: tuple[int, int]) -> None:
        self._tooltip_text = ""
        for slot, rect in self._quick_slot_rects():
            if rect.collidepoint(screen_pos) and slot and not slot.empty:
                self._tooltip_text = slot.item.get_tooltip()

    def draw_tooltip(self, screen: pygame.Surface, pos: tuple[int, int]) -> None:
        if not self._tooltip_text:
            return
        surf = self.font_sm.render(self._tooltip_text, True, (255, 255, 200))
        pad = 6
        bg = pygame.Surface((surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA)
        bg.fill(self.TOOLTIP_BG)
        screen.blit(bg, (pos[0] + 12, pos[1] - bg.get_height()))
        screen.blit(surf, (pos[0] + 12 + pad, pos[1] - bg.get_height() + pad))

    def _bar_baseline(self) -> int:
        return self.s.screen_height - self.MARGIN

    def _draw_hp_bar(self, screen: pygame.Surface) -> None:
        s = self.s
        bw, bh = s.player_hp_bar_width, s.player_hp_bar_height
        bx = self.MARGIN
        by = self._bar_baseline() - bh

        pygame.draw.rect(screen, s.player_hp_bar_bg, (bx, by, bw, bh))
        fill = int(bw * self.player.hp / self.player.max_hp)
        if fill > 0:
            pygame.draw.rect(screen, s.player_hp_bar_color, (bx, by, fill, bh))
        pygame.draw.rect(screen, (80, 80, 80), (bx, by, bw, bh), 1)

    def _draw_stamina_bar(self, screen: pygame.Surface) -> None:
        s = self.s
        bw = s.player_hp_bar_width
        bh = 5
        bx = self.MARGIN
        by = self._bar_baseline() - s.player_hp_bar_height - 3 - bh

        pygame.draw.rect(screen, (30, 30, 50), (bx, by, bw, bh))
        fill = int(bw * self.player.stamina / self.player.stats.max_stamina)
        if fill > 0:
            pygame.draw.rect(screen, (80, 140, 220), (bx, by, fill, bh))
        pygame.draw.rect(screen, (60, 60, 90), (bx, by, bw, bh), 1)

    def _quick_slots_origin(self) -> tuple[int, int]:
        s = self.s
        hp_right = self.MARGIN + s.player_hp_bar_width + 12
        ss = self.SMALL_SLOT
        pad = self.SLOT_PAD
        y = self._bar_baseline() - ss
        return hp_right, y

    def _quick_slot_rects(self):
        typed_count = len(self.player.pouch.typed_slots)
        consumable_slots = self.player.pouch.slots
        ox, oy = self._quick_slots_origin()
        ss = self.SMALL_SLOT
        pad = self.SLOT_PAD
        for i, slot in enumerate(consumable_slots):
            x = ox + i * (ss + pad)
            yield slot, pygame.Rect(x, oy, ss, ss)

    def _draw_quick_slots(self, screen: pygame.Surface) -> None:
        ss = self.SMALL_SLOT
        pad = self.SLOT_PAD

        for i, (slot, rect) in enumerate(self._quick_slot_rects()):
            pygame.draw.rect(screen, self.SLOT_BG, rect)
            pygame.draw.rect(screen, self.SLOT_BORDER, rect, 1)

            if slot and not slot.empty:
                icon = pygame.transform.scale(slot.item.icon, (ss - 4, ss - 4))
                screen.blit(icon, icon.get_rect(center=rect.center))

            if i < len(self.POUCH_KEY_LABELS):
                lbl = self.font_sm.render(self.POUCH_KEY_LABELS[i], True, (100, 100, 120))
                screen.blit(lbl, (rect.right - lbl.get_width() - 2, rect.bottom - lbl.get_height() - 1))

    def _draw_pouch_panel(self, screen: pygame.Surface) -> None:
        ss = self.SLOT_SIZE
        pad = self.SLOT_PAD
        weapon_w = 56
        weapon_h = 28
        armor_size = 64
        inner_pad = 10

        panel_w = weapon_w * 2 + armor_size + inner_pad * 4
        panel_h = armor_size + inner_pad * 2

        ox = self.MARGIN
        oy = self._bar_baseline() - self.s.player_hp_bar_height - panel_h - 16

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(self.PANEL_BG)
        screen.blit(panel_surf, (ox, oy))
        pygame.draw.rect(screen, self.PANEL_BORDER, (ox, oy, panel_w, panel_h), 1)

        typed_slots = self.player.pouch.typed_slots
        weapon_slots = [s for s in typed_slots if s.allowed_type == ItemType.WEAPON]
        armor_slots  = [s for s in typed_slots if s.allowed_type == ItemType.ARMOR]

        cx = ox + inner_pad
        cy = oy + inner_pad

        for i, slot in enumerate(weapon_slots):
            rect = pygame.Rect(cx, cy + i * (weapon_h + pad), weapon_w, weapon_h)
            self._draw_slot(screen, slot, rect, typed=True)
            lbl = self.font_sm.render("WEAPON", True, (70, 90, 150))
            screen.blit(lbl, (rect.x + 3, rect.y + 3))

        cx += weapon_w + inner_pad

        for slot in armor_slots:
            rect = pygame.Rect(cx, cy, armor_size, armor_size)
            self._draw_slot(screen, slot, rect, typed=True)
            lbl = self.font_sm.render("ARMOR", True, (70, 90, 150))
            screen.blit(lbl, (rect.x + 3, rect.y + 3))

    def _draw_slot(self, screen: pygame.Surface, slot, rect: pygame.Rect, typed: bool = False) -> None:
        bg     = self.SLOT_TYPED_BG if typed else self.SLOT_BG
        border = self.SLOT_TYPED_BORDER if typed else self.SLOT_BORDER
        pygame.draw.rect(screen, bg, rect)
        pygame.draw.rect(screen, border, rect, 1)
        if slot and not slot.empty:
            icon = pygame.transform.scale(slot.item.icon, (rect.width - 4, rect.height - 4))
            screen.blit(icon, icon.get_rect(center=rect.center))
