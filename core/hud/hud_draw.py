"""
hud_draw.py — все методы рендеринга HUD.
Подмешивается в класс HUD через наследование.
"""
import time
import pygame


class HUDDraw:

    def draw(self, screen: pygame.Surface, i_hold_progress: float = 0.0,
             weapon=None, player=None) -> None:
        self._draw_hp_bar(screen)
        self._draw_stamina_bar(screen)
        self._draw_quick_slots(screen)
        if weapon and weapon.has_weapon:
            self._draw_ammo_counter(screen, weapon)
        if self.pouch_open:
            self._draw_pouch_panel(screen)
        if self.backpack_open:
            self._grid_ui.draw(screen)
        if self._grid_ui.is_dragging:
            self._grid_ui.draw_dragged_item(screen)
        elif self._drag:
            self._draw_dragged_item(screen)
        if i_hold_progress > 0:
            self._draw_i_progress(screen, i_hold_progress)
        if player and player.is_using_item:
            self._draw_use_progress(screen, player)
        if player:
            self._draw_status_flags(screen, player)
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
        pygame.draw.rect(screen, (30, 30, 50),    (bx, by, bw, bh))
        fill = int(bw * self.player.stamina / self.player.stats.max_stamina)
        if fill > 0:
            pygame.draw.rect(screen, (80, 140, 220), (bx, by, fill, bh))
        pygame.draw.rect(screen, (60, 60, 90),    (bx, by, bw, bh), 1)

    def _draw_quick_slots(self, screen: pygame.Surface) -> None:
        ss = self.SMALL_SLOT
        for i, (slot, rect) in enumerate(self._quick_slot_rects()):
            bg = self.SLOT_HOVER if rect == self._hovered_rect else self.SLOT_BG
            pygame.draw.rect(screen, bg,               rect)
            pygame.draw.rect(screen, self.SLOT_BORDER,  rect, 1)
            if not slot.empty:
                icon = pygame.transform.scale(slot.item.icon, (ss - 4, ss - 4))
                screen.blit(icon, icon.get_rect(center=rect.center))
            if i < len(self.POUCH_KEY_LABELS):
                lbl = self.font_sm.render(self.POUCH_KEY_LABELS[i], True, (100, 100, 120))
                screen.blit(lbl, (rect.right - lbl.get_width() - 2, rect.bottom - lbl.get_height() - 1))

    def _draw_ammo_counter(self, screen: pygame.Surface, weapon) -> None:
        ox      = self.MARGIN + self.s.player_hp_bar_width + 12
        ss      = self.SMALL_SLOT
        pad     = self.SLOT_PAD
        slots_w = len(list(self.player.pouch.slots)) * (ss + pad)
        x       = ox + slots_w + 12
        y       = self._bar_baseline() - ss

        if weapon.jammed:
            lbl = self.font_md.render("JAMMED", True, (220, 60, 60))
            screen.blit(lbl, (x, y))
            hint = self.font_sm.render("[R] reload  [T] unjam", True, (160, 80, 80))
            screen.blit(hint, (x, y + lbl.get_height() + 2))
            return

        if weapon.unjamming:
            progress = 1.0 - weapon._unjam_timer / 0.5
            bw, bh   = 90, 5
            lbl = self.font_md.render("CYCLING...", True, (200, 120, 60))
            screen.blit(lbl, (x, y))
            pygame.draw.rect(screen, (40, 40, 60),   (x, y + lbl.get_height() + 4, bw, bh))
            pygame.draw.rect(screen, (200, 100, 40), (x, y + lbl.get_height() + 4, int(bw * progress), bh))
            return

        if weapon.reloading:
            progress = 1.0 - weapon._reload_timer / weapon._weapon_item.stats.reload_time
            bw, bh   = 90, 5
            lbl = self.font_md.render("RELOADING", True, (220, 180, 60))
            screen.blit(lbl, (x, y))
            pygame.draw.rect(screen, (40, 40, 60),   (x, y + lbl.get_height() + 4, bw, bh))
            pygame.draw.rect(screen, (180, 140, 40), (x, y + lbl.get_height() + 4, int(bw * progress), bh))
        else:
            text  = f"{weapon.mag_current} / {weapon.mag_size}"
            color = (220, 220, 220) if weapon.mag_current > 0 else (220, 60, 60)
            lbl   = self.font_md.render(text, True, color)
            screen.blit(lbl, (x, y + (ss - lbl.get_height()) // 2))

        wi = weapon._weapon_item
        if wi:
            bw, bh = 90, 3
            by2    = y + ss - bh - 2
            clean  = wi.cleanliness
            if   clean >= 0.75: bar_color = (80,  180, 80)
            elif clean >= 0.5:  bar_color = (200, 180, 40)
            elif clean >= 0.25: bar_color = (220, 120, 40)
            else:               bar_color = (200, 50,  50)
            pygame.draw.rect(screen, (30, 30, 50), (x, by2, bw, bh))
            pygame.draw.rect(screen, bar_color,    (x, by2, int(bw * clean), bh))

    def _draw_pouch_panel(self, screen: pygame.Surface) -> None:
        from items.item import ItemType
        weapon_w  = 28
        weapon_h  = 56
        helmet_sz = 36
        armor_sz  = 56
        inner_pad = 8
        pad       = self.SLOT_PAD

        equip_h   = helmet_sz + pad + armor_sz
        panel_w   = weapon_w + inner_pad + armor_sz + inner_pad + weapon_w + inner_pad * 2
        panel_h   = equip_h + inner_pad * 2
        ox        = self.MARGIN
        oy        = self._bar_baseline() - self.s.player_hp_bar_height - panel_h - 16

        surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        surf.fill(self.PANEL_BG)
        screen.blit(surf, (ox, oy))
        pygame.draw.rect(screen, self.PANEL_BORDER, (ox, oy, panel_w, panel_h), 1)

        typed_slots  = self.player.pouch.typed_slots
        weapon_slots = [s for s in typed_slots if s.allowed_type == ItemType.WEAPON]
        armor_slots  = [s for s in typed_slots if s.allowed_type == ItemType.ARMOR]
        helmet_slots = [s for s in typed_slots if s.allowed_type == ItemType.HELMET]

        self._pouch_panel_slot_rects = []
        cy_center = oy + inner_pad + (equip_h - weapon_h) // 2

        if len(weapon_slots) > 0:
            r = pygame.Rect(ox + inner_pad, cy_center, weapon_w, weapon_h)
            self._pouch_panel_slot_rects.append((weapon_slots[0], r))
            self._draw_slot(screen, weapon_slots[0], r, typed=True, rotate_icon=True)
            lbl = self.font_sm.render("W1", True, (70, 90, 150))
            screen.blit(lbl, (r.x + 3, r.y + 3))

        cx = ox + inner_pad + weapon_w + inner_pad
        for i, (slot, label, sz) in enumerate([
            *[(s, "HELM",  helmet_sz) for s in helmet_slots],
            *[(s, "ARMOR", armor_sz)  for s in armor_slots],
        ]):
            ry = oy + inner_pad + (helmet_sz + pad) * i
            offset_x = (armor_sz - sz) // 2
            r  = pygame.Rect(cx + offset_x, ry, sz, sz)
            self._pouch_panel_slot_rects.append((slot, r))
            self._draw_slot(screen, slot, r, typed=True)
            color = (80, 140, 80) if label == "HELM" else (70, 90, 150)
            lbl   = self.font_sm.render(label, True, color)
            screen.blit(lbl, (r.x + 3, r.y + 3))

        if len(weapon_slots) > 1:
            r = pygame.Rect(cx + armor_sz + inner_pad, cy_center, weapon_w, weapon_h)
            self._pouch_panel_slot_rects.append((weapon_slots[1], r))
            self._draw_slot(screen, weapon_slots[1], r, typed=True, rotate_icon=True)
            lbl = self.font_sm.render("W2", True, (70, 90, 150))
            screen.blit(lbl, (r.x + 3, r.y + 3))

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

    def _draw_use_progress(self, screen: pygame.Surface, player) -> None:
        if player.use_time_total <= 0:
            return
        progress  = min(player.use_timer / player.use_time_total, 1.0)
        item      = player._using_item
        bw, bh    = 160, 8
        cx        = self.s.screen_width // 2
        by        = self.s.screen_height - self.MARGIN - bh - 44
        bx        = cx - bw // 2
        bar_color = {"Bandage": (220, 180, 120), "Medkit": (80, 200, 100),
                     "Surgical Kit": (100, 180, 220)}.get(item.name, (180, 180, 220))
        pygame.draw.rect(screen, (20, 20, 35),  (bx - 1, by - 1, bw + 2, bh + 2))
        pygame.draw.rect(screen, (30, 30, 50),  (bx, by, bw, bh))
        if int(bw * progress) > 0:
            pygame.draw.rect(screen, bar_color, (bx, by, int(bw * progress), bh))
        pygame.draw.rect(screen, (80, 85, 110), (bx, by, bw, bh), 1)
        lbl = self.font_sm.render(f"Using {item.name}...", True, bar_color)
        screen.blit(lbl, (cx - lbl.get_width() // 2, by - 15))

    def _draw_status_flags(self, screen: pygame.Surface, player) -> None:
        flags = []
        if player.bleeding:
            flags.append(("BLEED", (200, 40, 40)))
        if getattr(player, "arms_damaged", False):
            flags.append(("ARMS",  (220, 130, 40)))
        if getattr(player, "legs_damaged", False):
            flags.append(("LEGS",  (220, 130, 40)))
        if not flags:
            return
        bx = self.MARGIN
        by = self._bar_baseline() - self.s.player_hp_bar_height - 22
        fw, fh, pad = 46, 14, 4
        for i, (label, color) in enumerate(flags):
            visible = int(time.time() * 2) % 2 == 0
            fx      = bx + i * (fw + pad)
            bg      = pygame.Surface((fw, fh), pygame.SRCALPHA)
            bg.fill((*color, 80) if visible else (*color, 30))
            screen.blit(bg, (fx, by))
            pygame.draw.rect(screen, color, (fx, by, fw, fh), 1, border_radius=3)
            lbl = self.font_sm.render(label, True, color if visible else (80, 80, 80))
            screen.blit(lbl, lbl.get_rect(center=(fx + fw // 2, by + fh // 2)))

    def _draw_dragged_item(self, screen: pygame.Surface) -> None:
        mx, my = pygame.mouse.get_pos()
        sz     = self._drag.icon_size
        icon   = pygame.transform.scale(self._drag.item.icon, (sz, sz))
        screen.blit(icon, (mx - sz // 2, my - sz // 2))

    def _draw_tooltip(self, screen: pygame.Surface, pos: tuple) -> None:
        if not self._tooltip_text or self._grid_ui.is_dragging or self._drag:
            return
        surf = self.font_sm.render(self._tooltip_text, True, (255, 255, 200))
        pad  = 6
        bg   = pygame.Surface((surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA)
        bg.fill(self.TOOLTIP_BG)
        screen.blit(bg,   (pos[0] + 12, pos[1] - bg.get_height()))
        screen.blit(surf, (pos[0] + 12 + pad, pos[1] - bg.get_height() + pad))

    def _draw_slot(self, screen, slot, rect, typed=False, rotate_icon=False):
        bg     = self.SLOT_HOVER if rect == self._hovered_rect else (self.SLOT_TYPED_BG if typed else self.SLOT_BG)
        border = self.SLOT_TYPED_BORDER if typed else self.SLOT_BORDER
        pygame.draw.rect(screen, bg,     rect)
        pygame.draw.rect(screen, border, rect, 1)
        if slot and not slot.empty:
            if rotate_icon:
                side = min(rect.width, rect.height) - 4
                icon = pygame.transform.scale(slot.item.icon, (side, side))
                icon = pygame.transform.rotate(icon, 90)
            else:
                icon = pygame.transform.scale(slot.item.icon, (rect.width - 4, rect.height - 4))
            screen.blit(icon, icon.get_rect(center=rect.center))
            self._draw_weapon_condition(screen, slot.item, rect)

    def _draw_weapon_condition(self, screen: pygame.Surface, item, rect: pygame.Rect) -> None:
        from items.weapon_item import WeaponItem
        if not isinstance(item, WeaponItem):
            return
        clean = item.cleanliness
        bw, bh = rect.width - 4, 3
        bx, by = rect.x + 2, rect.bottom - bh - 2
        if   clean >= 0.75: bar_color = (80,  180, 80)
        elif clean >= 0.5:  bar_color = (200, 180, 40)
        elif clean >= 0.25: bar_color = (220, 120, 40)
        else:               bar_color = (200, 50,  50)
        pygame.draw.rect(screen, (20, 20, 30), (bx, by, bw, bh))
        pygame.draw.rect(screen, bar_color,    (bx, by, int(bw * clean), bh))
        if item.jammed:
            j = self.font_sm.render("J", True, (220, 60, 60))
            screen.blit(j, (rect.x + 3, rect.y + 3))
