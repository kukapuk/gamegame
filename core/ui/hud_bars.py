"""
hud_bars.py — отрисовка HP, стамины, прогресс-баров.
Функции принимают hud как первый аргумент.
"""
import pygame


def draw_hp_bar(hud, screen: pygame.Surface) -> None:
    s      = hud.s
    bw, bh = s.player_hp_bar_width, s.player_hp_bar_height
    bx, by = hud.MARGIN, hud._bar_baseline() - bh
    pygame.draw.rect(screen, s.player_hp_bar_bg,    (bx, by, bw, bh))
    fill = int(bw * hud.player.hp / hud.player.max_hp)
    if fill > 0:
        pygame.draw.rect(screen, s.player_hp_bar_color, (bx, by, fill, bh))
    pygame.draw.rect(screen, (80, 80, 80), (bx, by, bw, bh), 1)


def draw_stamina_bar(hud, screen: pygame.Surface) -> None:
    s   = hud.s
    bw  = s.player_hp_bar_width
    bh  = 5
    bx  = hud.MARGIN
    by  = hud._bar_baseline() - s.player_hp_bar_height - 3 - bh
    pygame.draw.rect(screen, (30, 30, 50),    (bx, by, bw, bh))
    fill = int(bw * hud.player.stamina / hud.player.stats.max_stamina)
    if fill > 0:
        pygame.draw.rect(screen, (80, 140, 220), (bx, by, fill, bh))
    pygame.draw.rect(screen, (60, 60, 90),    (bx, by, bw, bh), 1)


def draw_i_progress(hud, screen: pygame.Surface, progress: float) -> None:
    bw, bh = 120, 6
    cx     = hud.s.screen_width // 2
    by     = hud.s.screen_height - hud.MARGIN - bh - 60
    bx     = cx - bw // 2
    pygame.draw.rect(screen, (30, 30, 50),    (bx, by, bw, bh))
    fill = int(bw * min(progress, 1.0))
    if fill > 0:
        pygame.draw.rect(screen, (120, 160, 220), (bx, by, fill, bh))
    pygame.draw.rect(screen, (60, 65, 90),    (bx, by, bw, bh), 1)
    label = "Opening..." if not hud.backpack_open else "Closing..."
    lbl   = hud.font_sm.render(label, True, (140, 150, 180))
    screen.blit(lbl, (cx - lbl.get_width() // 2, by - 16))


def draw_use_progress(hud, screen: pygame.Surface, player) -> None:
    if player.use_time_total <= 0:
        return
    progress = min(player.use_timer / player.use_time_total, 1.0)
    item     = player._using_item
    bw, bh   = 160, 8
    cx       = hud.s.screen_width // 2
    by       = hud.s.screen_height - hud.MARGIN - bh - 44
    bx       = cx - bw // 2
    bar_colors = {
        "Bandage":      (220, 180, 120),
        "Medkit":       (80,  200, 100),
        "Surgical Kit": (100, 180, 220),
    }
    bar_color = bar_colors.get(item.name, (180, 180, 220))
    pygame.draw.rect(screen, (20, 20, 35),  (bx - 1, by - 1, bw + 2, bh + 2))
    pygame.draw.rect(screen, (30, 30, 50),  (bx, by, bw, bh))
    fill = int(bw * progress)
    if fill > 0:
        pygame.draw.rect(screen, bar_color, (bx, by, fill, bh))
    pygame.draw.rect(screen, (80, 85, 110), (bx, by, bw, bh), 1)
    lbl = hud.font_sm.render(f"Using {item.name}...", True, bar_color)
    screen.blit(lbl, (cx - lbl.get_width() // 2, by - 15))


def draw_ammo_counter(hud, screen: pygame.Surface, weapon) -> None:
    ox      = hud.MARGIN + hud.s.player_hp_bar_width + 12
    ss      = hud.SMALL_SLOT
    pad     = hud.SLOT_PAD
    slots_w = len(list(hud.player.pouch.slots)) * (ss + pad)
    x       = ox + slots_w + 12
    y       = hud._bar_baseline() - ss

    if weapon.jammed:
        lbl = hud.font_md.render("JAMMED", True, (220, 60, 60))
        screen.blit(lbl, (x, y))
        hint = hud.font_sm.render("[R] reload  [T] unjam", True, (160, 80, 80))
        screen.blit(hint, (x, y + lbl.get_height() + 2))
        return

    if weapon.unjamming:
        progress = 1.0 - weapon._unjam_timer / 0.5
        bw, bh   = 90, 7
        lbl = hud.font_md.render("CYCLING...", True, (200, 120, 60))
        screen.blit(lbl, (x, y - lbl.get_height() - 3))
        pygame.draw.rect(screen, (0, 0, 0),      (x - 1, y - 1, bw + 2, bh + 2))
        pygame.draw.rect(screen, (60, 50, 30),   (x, y, bw, bh))
        pygame.draw.rect(screen, (220, 120, 40), (x, y, int(bw * progress), bh))
        return

    if weapon.reloading:
        progress = 1.0 - weapon._reload_timer / weapon._weapon_item.stats.reload_time
        bw, bh   = 90, 7
        lbl = hud.font_md.render("RELOADING", True, (220, 180, 60))
        screen.blit(lbl, (x, y - lbl.get_height() - 3))
        pygame.draw.rect(screen, (0, 0, 0),      (x - 1, y - 1, bw + 2, bh + 2))
        pygame.draw.rect(screen, (60, 55, 20),   (x, y, bw, bh))
        pygame.draw.rect(screen, (220, 180, 40), (x, y, int(bw * progress), bh))
        return

    text  = f"{weapon.mag_current} / {weapon.mag_size}"
    color = (220, 220, 220) if weapon.mag_current > 0 else (220, 60, 60)
    lbl   = hud.font_md.render(text, True, color)
    screen.blit(lbl, (x, y + (ss - lbl.get_height()) // 2))

    wi = weapon._weapon_item
    if wi:
        bw, bh = 90, 3
        by2    = y + ss - bh - 2
        clean  = wi.cleanliness
        if clean >= 0.75:   bar_color = (80, 180, 80)
        elif clean >= 0.5:  bar_color = (200, 180, 40)
        elif clean >= 0.25: bar_color = (220, 120, 40)
        else:               bar_color = (200, 50, 50)
        pygame.draw.rect(screen, (30, 30, 50), (x, by2, bw, bh))
        pygame.draw.rect(screen, bar_color,    (x, by2, int(bw * clean), bh))
