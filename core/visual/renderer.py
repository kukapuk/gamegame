import pygame
from core.settings import Settings


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
    ) -> None:
        offset = camera.get_offset()

        screen.fill(self.s.bg_color)
        level.draw_floor(screen, offset)

        # кровь и гильзы рисуются поверх пола, но под акторами
        if blood_drops:
            for drop in blood_drops:
                screen.blit(drop.image, drop.rect.move(-offset.x, -offset.y))
        if casings:
            for casing in casings:
                screen.blit(casing.image, casing.rect.move(-offset.x, -offset.y))

        # FOV floor layer — после пола, ДО спрайтов
        if vision_system is not None:
            vision_system.render_floor_layer(screen, offset, debug=debug)

        self._draw_sprites(screen, camera, level, world_items, npcs, enemies,
                           enemy_bullets, bullets, player, weapon,
                           vision_system=vision_system, debug=debug)
        self._draw_enemy_hp_bars(screen, camera, enemies,
                                   vision_system=vision_system, debug=debug)

        # FOV sprite layer — поверх спрайтов (силуэты видны)
        if vision_system is not None:
            vision_system.render_sprite_layer(screen, offset, debug=debug)

        if popups:
            for popup in popups:
                screen.blit(popup.image, popup.rect.move(-offset.x, -offset.y))

        hud.draw_world_hover(screen, offset)
        loot_manager.draw_hint(screen, offset)
        world_manager.draw(screen, offset)

        self._draw_npc_hint(screen, camera, world_manager)

        hud.draw(screen, i_hold_progress=i_hold_progress, weapon=weapon, player=player)

        if debug:
            self._draw_debug(screen, camera, player, enemies,
                             enemy_bullets, bullets, world_items,
                             world_manager, audio_manager, patrol_groups)

        if player_dead:
            self._draw_death_screen(screen)

        dialog_manager.draw(screen)
        self._draw_cursor(screen, weapon, hud, player, offset)
        # FPS всегда виден
        fps_surf = self._font_save_hint.render(
            f"{self.clock.get_fps():.0f} fps", True, (120, 120, 120))
        screen.blit(fps_surf, (self.s.screen_width - fps_surf.get_width() - 8, 8))
        pygame.display.flip()

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

        # пули всегда видны (они в воздухе, их видно)
        for sprite in [*enemy_bullets.sprites(), *bullets.sprites()]:
            screen.blit(sprite.image, camera.apply(sprite.rect))

        # враги — скрыть если не видно
        for sprite in enemies.sprites():
            if vs and not vs.is_visible(sprite.rect.center):
                continue
            screen.blit(sprite.image, camera.apply(sprite.rect))

        # игрок всегда
        screen.blit(player.image, camera.apply(player.rect))

        # оружие врагов — вместе с врагом
        for enemy in enemies:
            if vs and not vs.is_visible(enemy.rect.center):
                continue
            if enemy.weapon_image is not None and enemy.weapon_rect is not None:
                screen.blit(enemy.weapon_image, camera.apply(enemy.weapon_rect))

        if weapon.has_weapon:
            screen.blit(weapon.image, camera.apply(weapon.rect))

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
