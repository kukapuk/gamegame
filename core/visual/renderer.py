import pygame
from core.settings import Settings
from core.visual.impact_particles import impact_particles
from core.visual.bullet_decals import bullet_decals
from core.visual.muzzle_smoke import muzzle_smoke


def _draw_bullet_trail(
    surface: pygame.Surface,
    bullet,
    offset: pygame.math.Vector2,
) -> None:
    """
    Рисует трассерный шлейф за пулей.
    Линия от хвоста к голове, ширина и яркость убывают к хвосту.
    """
    trail = getattr(bullet, "_trail", None)
    if not trail:
        return

    from combat.bullet import _TRAIL_DURATION

    # голова — текущая позиция пули
    head = (round(bullet.pos.x - offset.x), round(bullet.pos.y - offset.y))

    # строим точки: хвост → голова
    points = []
    for x, y, age in trail:
        t = 1.0 - age / _TRAIL_DURATION   # 1 у головы, 0 у хвоста
        points.append((round(x - offset.x), round(y - offset.y), t))
    points.append((*head, 1.0))

    if len(points) < 2:
        return

    r, g, b = bullet.color

    # рисуем сегментами: ширина и альфа убывают к хвосту
    for i in range(len(points) - 1):
        x0, y0, t0 = points[i]
        x1, y1, t1 = points[i + 1]

        # средняя яркость сегмента
        t_mid  = (t0 + t1) * 0.5
        alpha  = int(220 * t_mid * t_mid)       # квадратично — резкий хвост
        width  = max(1, round(bullet.size * t_mid * 0.9))

        if alpha < 8:
            continue

        # рисуем через Surface с альфой
        length = max(1, int(((x1 - x0)**2 + (y1 - y0)**2) ** 0.5) + 1)
        seg = pygame.Surface((length + width * 2, width * 2 + 2), pygame.SRCALPHA)
        pygame.draw.line(
            seg,
            (r, g, b, alpha),
            (width, width + 1),
            (length + width, width + 1),
            width,
        )

        import math
        angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
        rotated = pygame.transform.rotate(seg, -angle)
        rx, ry = rotated.get_size()
        surface.blit(rotated, (x0 - rx // 2, y0 - ry // 2))


class Renderer:
    """
    Отвечает за весь рендеринг кадра.
    Не знает об игровой логике — только рисует то, что ей передают.

    Вызов из GameScene:
        renderer.draw(screen, ctx)
    где ctx — RenderContext с данными кадра.
    """

    def __init__(self, settings: Settings, clock: pygame.time.Clock) -> None:
        self.s     = settings
        self.clock = clock

        self._font_interact  = pygame.font.SysFont("monospace", 14)
        self._font_save_hint = pygame.font.SysFont("monospace", 12)
        self._font_debug     = pygame.font.SysFont("monospace", 16)
        self._death_font_big = pygame.font.SysFont("monospace", 72, bold=True)
        self._death_font_sm  = pygame.font.SysFont("monospace", 24)

        # буфер для зума — мировая часть рисуется сюда, потом масштабируется
        self._world_surf = pygame.Surface(
            (settings.screen_width, settings.screen_height), pygame.SRCALPHA
        )

        pygame.mouse.set_visible(False)

    # Public entry point

    def draw(
        self,
        screen: pygame.Surface,
        *,
        level,
        camera,
        player,
        weapon,
        enemies:       pygame.sprite.Group,
        bullets:       pygame.sprite.Group,
        enemy_bullets: pygame.sprite.Group,
        world_items:   pygame.sprite.Group,
        npcs:          pygame.sprite.Group,
        hud,
        world_manager,
        loot_manager,
        dialog_manager,
        save_manager,
        audio_manager,
        blood_drops:   pygame.sprite.Group = None,
        casings:       pygame.sprite.Group = None,
        popups:        pygame.sprite.Group = None,
        i_hold_progress: float = 0.0,
        player_dead: bool = False,
        debug: bool = False,
        vision_system = None,
        patrol_groups: list = (),
        snow = None,
    ) -> None:
        offset = camera.get_offset()
        zoom   = camera.zoom

        # --- мировая сцена рисуется в буфер ---
        world = self._world_surf
        world.fill(self.s.bg_color)
        level.draw_floor(world, offset)

        # следы пуль — под всем, прямо на полу
        bullet_decals.draw(world, offset)

        # кровь и гильзы — под акторами
        if blood_drops:
            for drop in blood_drops:
                world.blit(drop.image, drop.rect.move(-offset.x, -offset.y))
        if casings:
            for casing in casings:
                world.blit(casing.image, casing.rect.move(-offset.x, -offset.y))

        # FOV floor layer
        if vision_system is not None:
            vision_system.render_floor_layer(world, offset, debug=debug)

        self._draw_sprites(world, camera, level, world_items, npcs, enemies,
                           enemy_bullets, bullets, player, weapon,
                           vision_system=vision_system, debug=debug)
        self._draw_enemy_hp_bars(world, camera, enemies,
                                   vision_system=vision_system, debug=debug)

        # FOV sprite layer
        if vision_system is not None:
            vision_system.render_sprite_layer(world, offset, debug=debug)

        if popups:
            for popup in popups:
                world.blit(popup.image, popup.rect.move(-offset.x, -offset.y))

        # частицы попаданий (стена / броня / плоть)
        impact_particles.draw(world, offset)

        # дым у ствола — поверх всего в мире
        muzzle_smoke.draw(world, offset)

        hud.draw_world_hover(world, offset)
        loot_manager.draw_hint(world, offset)
        world_manager.draw(world, offset)
        self._draw_npc_hint(world, camera, world_manager)

        # --- масштабируем буфер и блитим на экран ---
        screen.fill((0, 0, 0))
        if zoom == 1.0:
            screen.blit(world, (0, 0))
        else:
            sw, sh = self.s.screen_width, self.s.screen_height
            scaled_w = round(sw * zoom)
            scaled_h = round(sh * zoom)
            scaled = pygame.transform.scale(world, (scaled_w, scaled_h))
            # центрируем — «зум к центру экрана»
            bx = (sw - scaled_w) // 2
            by = (sh - scaled_h) // 2
            screen.blit(scaled, (bx, by))

        # --- HUD и оверлеи поверх (без зума) ---
        if snow is not None:
            snow.draw(screen)

        hud.draw(screen, i_hold_progress=i_hold_progress, weapon=weapon, player=player)

        if debug:
            self._draw_debug(screen, camera, player, enemies,
                             enemy_bullets, bullets, world_items,
                             world_manager, audio_manager, patrol_groups)

        if player_dead:
            self._draw_death_screen(screen)

        dialog_manager.draw(screen)
        self._draw_cursor(screen, weapon, hud, player, offset)
        fps_surf = self._font_save_hint.render(
            f"{self.clock.get_fps():.0f} fps", True, (120, 120, 120))
        screen.blit(fps_surf, (self.s.screen_width - fps_surf.get_width() - 8, 8))
        # zoom hint
        zoom_surf = self._font_save_hint.render(
            f"zoom {zoom:.1f}x", True, (90, 90, 90))
        screen.blit(zoom_surf, (self.s.screen_width - zoom_surf.get_width() - 8, 24))

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _draw_sprites(
        self, screen, camera, level,
        world_items, npcs, enemies, enemy_bullets, bullets, player, weapon,
        vision_system=None, debug=False,
    ) -> None:
        vs = vision_system if (vision_system and not debug) else None

        for sprite in level.walls:
            screen.blit(sprite.image, camera.apply(sprite.rect))

        # предметы на земле — скрыть если не видно
        for sprite in world_items:
            if vs and not vs.is_visible(sprite.rect.center):
                continue
            screen.blit(sprite.image, camera.apply(sprite.rect))

        # NPC — скрыть если не видно
        for npc in npcs:
            if vs and not vs.is_visible(npc.rect.center):
                continue
            screen.blit(npc.image, camera.apply(npc.rect))
            npc.draw_name(screen, camera.get_offset())

        # пули — сначала шлейф, потом сам снаряд
        offset = camera.get_offset()
        for sprite in [*enemy_bullets.sprites(), *bullets.sprites()]:
            _draw_bullet_trail(screen, sprite, offset)
        for sprite in [*enemy_bullets.sprites(), *bullets.sprites()]:
            screen.blit(sprite.image, camera.apply(sprite.rect))

        # враги — скрыть если не видно
        for sprite in enemies.sprites():
            if vs and not vs.is_visible(sprite.rect.center):
                continue
            screen.blit(sprite.image, camera.apply(sprite.rect))

        # игрок и оружие: порядок зависит от стороны прицеливания
        # оружие слева (facing_left) → рисуем оружие ДО игрока (за ним)
        # оружие справа             → рисуем оружие ПОСЛЕ игрока (поверх)
        weapon_facing_left = (
            weapon.has_weapon and weapon.aim_dir.x < 0
        )

        if weapon_facing_left and weapon.has_weapon:
            screen.blit(weapon.image, camera.apply(weapon.rect))

        screen.blit(player.image, camera.apply(player.rect))

        if not weapon_facing_left and weapon.has_weapon:
            screen.blit(weapon.image, camera.apply(weapon.rect))

        # оружие врагов — вместе с врагом
        for enemy in enemies:
            if vs and not vs.is_visible(enemy.rect.center):
                continue
            if enemy.weapon_image is not None and enemy.weapon_rect is not None:
                screen.blit(enemy.weapon_image, camera.apply(enemy.weapon_rect))

    def _draw_enemy_hp_bars(
        self, screen: pygame.Surface, camera, enemies: pygame.sprite.Group,
        vision_system=None, debug=False,
    ) -> None:
        vs = vision_system if (vision_system and not debug) else None
        s = self.s
        for enemy in enemies:
            if vs and not vs.is_visible(enemy.rect.center):
                continue
            bar_rect = camera.apply(enemy.rect)
            bx = bar_rect.centerx - s.enemy_hp_bar_width // 2
            by = bar_rect.top - 8
            pygame.draw.rect(screen, s.enemy_hp_bar_bg,
                             (bx, by, s.enemy_hp_bar_width, s.enemy_hp_bar_height))
            fill = int(s.enemy_hp_bar_width * enemy.hp / enemy.max_hp)
            if fill > 0:
                pygame.draw.rect(screen, s.enemy_hp_bar_color,
                                 (bx, by, fill, s.enemy_hp_bar_height))

    def _draw_npc_hint(self, screen: pygame.Surface, camera, world_manager) -> None:
        nearby_npc = world_manager.get_nearby_npc()
        if not nearby_npc:
            return
        screen_pos = camera.apply(nearby_npc.rect)
        text = f"[E]  Talk to {nearby_npc.name}"
        surf = self._font_interact.render(text, True, (200, 220, 255))
        pad  = 5
        bg   = pygame.Surface(
            (surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA
        )
        bg.fill((10, 10, 20, 180))
        bx = screen_pos.centerx - bg.get_width() // 2
        by = screen_pos.top - bg.get_height() - 6
        screen.blit(bg,   (bx, by))
        screen.blit(surf, (bx + pad, by + pad))

    def _draw_death_screen(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface(
            (self.s.screen_width, self.s.screen_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        cx = self.s.screen_width  // 2
        cy = self.s.screen_height // 2
        title = self._death_font_big.render("YOU DIED", True, (200, 40, 40))
        hint  = self._death_font_sm.render("press any key to restart", True, (160, 160, 160))
        screen.blit(title, title.get_rect(center=(cx, cy - 40)))
        screen.blit(hint,  hint.get_rect(center=(cx, cy + 40)))

    def _draw_debug(
        self, screen, camera, player, enemies,
        enemy_bullets, bullets, world_items, world_manager, audio_manager,
        patrol_groups=(),
    ) -> None:
        p     = player
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({p.pos.x:.0f}, {p.pos.y:.0f})",
            f"stamina: {p.stamina:.0f} / {p.stats.max_stamina:.0f}",
            f"dash cd: {p._dash_cooldown:.2f}s",
            f"bullets: {len(bullets)}  enemies: {len(enemies)}",
            f"world_items: {len(world_items)}",
            f"enemy_bullets: {len(enemy_bullets)}",
            f"level: {getattr(world_manager.level, 'path', '?')}",
        ]
        for i, line in enumerate(lines):
            surf = self._font_debug.render(line, True, (180, 220, 180))
            screen.blit(surf, (10, 10 + i * 20))
        offset = camera.get_offset()
        for enemy in enemies:
            enemy.draw_debug(screen, offset)
        audio_manager.draw_debug(screen, offset)
        for pg in patrol_groups:
            pg.draw_debug(screen, offset)
        from core.managers.cover_system import cover_system
        cover_system.draw_debug(screen, offset, player.pos, player.walls if hasattr(player, "walls") else None)
        world_manager.draw_debug(screen, offset)
        p.draw_debug(screen, offset)
    def _draw_cursor(
        self,
        screen: pygame.Surface,
        weapon,
        hud,
        player,
        camera_offset: pygame.math.Vector2,
    ) -> None:
        mx, my     = pygame.mouse.get_pos()
        has_weapon = weapon and weapon.has_weapon and not hud.is_open()

        if has_weapon:
            radius     = self._weapon_item_aim_radius(weapon)
            player_scr = player.pos - camera_offset

            ring_surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(
                ring_surf, (255, 255, 255, 35),
                (radius + 1, radius + 1), radius, 1
            )
            screen.blit(
                ring_surf,
                (round(player_scr.x) - radius - 1,
                 round(player_scr.y) - radius - 1),
            )

            pygame.draw.circle(screen, (0, 0, 0),       (mx, my), 9, 1)
            pygame.draw.circle(screen, (220, 220, 220),  (mx, my), 8, 1)
            pygame.draw.circle(screen, (220, 220, 220),  (mx, my), 2)
        else:
            size = 8
            pygame.draw.rect(screen, (20, 20, 20),
                             (mx - size // 2, my - size // 2, size, size))

        # иконка крадущегося режима
        if player.is_crouching:
            font = pygame.font.SysFont("monospace", 11)
            lbl  = font.render("[C]", True, (100, 180, 255))
            screen.blit(lbl, (mx + 14, my + 10))

    @staticmethod
    def _weapon_item_aim_radius(weapon) -> float:
        if weapon and weapon._weapon_item:
            return weapon._weapon_item.stats.aim_radius
        return 160.0
