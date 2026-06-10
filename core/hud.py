import pygame
from core.settings import Settings
from entities.actors.player import Player


class HUD:
    """
    Рисует весь UI поверх игрового мира.
    Получает ссылку на Player и читает данные напрямую.
    Вызывай hud.draw(screen) в конце каждого кадра.
    """

    POUCH_KEY_LABELS = ["Z", "X", "C", "V"]
    SLOT_SIZE        = 48
    SLOT_PAD         = 6
    SLOT_BG          = (35, 35, 45)
    SLOT_BORDER      = (70, 70, 90)
    SLOT_TYPED_BG    = (25, 30, 50)
    SLOT_TYPED_BORDER= (60, 80, 140)
    TEXT_COLOR       = (200, 200, 210)
    TOOLTIP_BG       = (20, 20, 30, 210)

    def __init__(self, settings: Settings, player: Player) -> None:
        self.s = settings
        self.player = player
        self.font_sm = pygame.font.SysFont("monospace", 12)
        self.font_md = pygame.font.SysFont("monospace", 14)
        self._tooltip_text: str = ""

    def draw(self, screen: pygame.Surface) -> None:
        self._draw_hp_bar(screen)
        self._draw_stamina_bar(screen)
        self._draw_pouch(screen)

    def handle_mouse_motion(self, screen_pos: tuple[int, int]) -> None:
        self._tooltip_text = ""
        for slot, rect in self._pouch_slot_rects():
            if rect.collidepoint(screen_pos) and not slot.empty:
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

    def _draw_hp_bar(self, screen: pygame.Surface) -> None:
        s = self.s
        bw, bh = s.player_hp_bar_width, s.player_hp_bar_height
        margin = s.player_hp_bar_margin
        bx = margin
        by = s.screen_height - margin - bh

        pygame.draw.rect(screen, s.player_hp_bar_bg, (bx, by, bw, bh))
        fill = int(bw * self.player.hp / self.player.max_hp)
        if fill > 0:
            pygame.draw.rect(screen, s.player_hp_bar_color, (bx, by, fill, bh))
        pygame.draw.rect(screen, (80, 80, 80), (bx, by, bw, bh), 1)

    def _draw_stamina_bar(self, screen: pygame.Surface) -> None:
        s = self.s
        bw = s.player_hp_bar_width
        margin = s.player_hp_bar_margin
        bx = margin
        by = s.screen_height - margin - s.player_hp_bar_height - 10

        stamina_h = 6
        by -= stamina_h

        pygame.draw.rect(screen, (30, 30, 50), (bx, by, bw, stamina_h))
        fill = int(bw * self.player.stamina / self.player.stats.max_stamina)
        if fill > 0:
            pygame.draw.rect(screen, (80, 140, 220), (bx, by, fill, stamina_h))
        pygame.draw.rect(screen, (60, 60, 90), (bx, by, bw, stamina_h), 1)

    def _draw_pouch(self, screen: pygame.Surface) -> None:
        all_slots = self.player.pouch.all_slots()
        typed_count = len(self.player.pouch.typed_slots)
        total = len(all_slots)

        ss = self.SLOT_SIZE
        pad = self.SLOT_PAD
        total_w = total * ss + (total - 1) * pad
        start_x = (self.s.screen_width - total_w) // 2
        y = self.s.screen_height - ss - 20

        for i, slot in enumerate(all_slots):
            x = start_x + i * (ss + pad)
            rect = pygame.Rect(x, y, ss, ss)
            is_typed = i < typed_count

            bg = self.SLOT_TYPED_BG if is_typed else self.SLOT_BG
            border = self.SLOT_TYPED_BORDER if is_typed else self.SLOT_BORDER

            pygame.draw.rect(screen, bg, rect)
            pygame.draw.rect(screen, border, rect, 1)

            if is_typed:
                label_text = ["W", "W", "A"][i] if i < 3 else ""
                lbl = self.font_sm.render(label_text, True, (80, 100, 160))
                screen.blit(lbl, (x + 3, y + 3))

            if not slot.empty:
                icon = slot.item.icon
                icon_rect = icon.get_rect(center=rect.center)
                screen.blit(icon, icon_rect)

            key_idx = i - typed_count
            if 0 <= key_idx < len(self.POUCH_KEY_LABELS):
                key_lbl = self.font_sm.render(self.POUCH_KEY_LABELS[key_idx], True, (120, 120, 140))
                screen.blit(key_lbl, (x + ss - key_lbl.get_width() - 3, y + ss - key_lbl.get_height() - 2))

    def _pouch_slot_rects(self):
        all_slots = self.player.pouch.all_slots()
        total = len(all_slots)
        ss = self.SLOT_SIZE
        pad = self.SLOT_PAD
        total_w = total * ss + (total - 1) * pad
        start_x = (self.s.screen_width - total_w) // 2
        y = self.s.screen_height - ss - 20

        for i, slot in enumerate(all_slots):
            x = start_x + i * (ss + pad)
            yield slot, pygame.Rect(x, y, ss, ss)
