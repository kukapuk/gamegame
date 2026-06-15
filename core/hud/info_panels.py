"""
info_panels.py — плавающие инфо-панели предметов (RMB).
"""
import pygame


class InfoPanels:

    def handle_rmb(self, pos: tuple, player=None) -> None:
        if not self.backpack_open:
            return
        _, item = self._get_item_at(pos)
        if item is None:
            return
        for panel in self._info_panels:
            if panel["item"] is item:
                return
        pw, ph = 220, 140
        px = min(pos[0] + 8, self.s.screen_width  - pw - 4)
        py = min(pos[1] + 8, self.s.screen_height - ph - 4)
        self._info_panels.append({
            "item":     item,
            "pos":      pygame.Vector2(px, py),
            "size":     (pw, ph),
            "dragging": False,
            "drag_off": pygame.Vector2(0, 0),
        })

    def handle_info_panels_mouse_down(self, pos: tuple) -> bool:
        for panel in reversed(self._info_panels):
            px, py = int(panel["pos"].x), int(panel["pos"].y)
            pw, ph = panel["size"]
            x_rect = pygame.Rect(px + pw - 16, py + 2, 14, 14)
            if x_rect.collidepoint(pos):
                self._info_panels.remove(panel)
                return True
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
        for panel in self._info_panels[:]:
            px, py = int(panel["pos"].x), int(panel["pos"].y)
            pw, ph = panel["size"]
            if not pygame.Rect(px - 40, py - 40, pw + 80, ph + 80).collidepoint(pos):
                self._info_panels.remove(panel)

    def draw_info_panels(self, screen: pygame.Surface) -> None:
        if not self.backpack_open:
            return
        for panel in self._info_panels:
            self._draw_info_panel(screen, panel)

    def _draw_info_panel(self, screen: pygame.Surface, panel: dict) -> None:
        item   = panel["item"]
        px, py = int(panel["pos"].x), int(panel["pos"].y)
        pw, ph = panel["size"]
        pad    = 8

        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        surf.fill((16, 18, 30, 235))
        screen.blit(surf, (px, py))
        pygame.draw.rect(screen, (60, 65, 100), (px, py, pw, ph), 1, border_radius=6)

        pygame.draw.rect(screen, (28, 32, 52), (px, py, pw, 22), border_radius=6)
        name_surf = self.font_md.render(item.name, True, (200, 205, 225))
        screen.blit(name_surf, (px + pad, py + 4))

        x_rect = pygame.Rect(px + pw - 16, py + 2, 14, 14)
        pygame.draw.rect(screen, (60, 40, 40), x_rect, border_radius=3)
        x_lbl = self.font_sm.render("x", True, (200, 120, 120))
        screen.blit(x_lbl, x_lbl.get_rect(center=x_rect.center))

        icon = pygame.transform.scale(item.icon, (36, 36))
        screen.blit(icon, (px + pad, py + 28))

        lines = self._item_info_lines(item)
        ty    = py + 28
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
            return [f"Type:  {item.ammo_type.name}", f"Count: {item.stack_count}/{item.max_stack}"]
        if isinstance(item, Armor):
            return [
                f"Tier:   {item.tier}",
                f"Dash:   x{item.dash_stamina_mult:.2f}",
                f"Sprint: {item.sprint_stamina_drain}/s",
            ]
        if isinstance(item, CleaningKit):
            return [f"Restores: +{int(item.heal_amount * 100)}% clean"]
        return [item.get_tooltip()]
