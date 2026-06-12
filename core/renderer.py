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
        i_hold_progress: float = 0.0,
        player_dead: bool = False,
        debug: bool = False,
    ) -> None:
        offset = camera.get_offset()

        screen.fill(self.s.bg_color)
        level.draw_floor(screen, offset)

        self._draw_sprites(screen, camera, level, world_items, npcs, enemies,
                           enemy_bullets, bullets, player, weapon)
        self._draw_enemy_hp_bars(screen, camera, enemies)

        hud.draw_world_hover(screen, offset)
        loot_manager.draw_hint(screen, offset)
        world_manager.draw(screen, offset)

        self._draw_npc_hint(screen, camera, world_manager)

        hud.draw(screen, i_hold_progress=i_hold_progress, weapon=weapon)

        if debug:
            self._draw_debug(screen, camera, player, enemies,
                             enemy_bullets, bullets, world_items,
                             world_manager, audio_manager)

        if player_dead:
            self._draw_death_screen(screen)

        self._draw_save_hint(screen, save_manager)
        dialog_manager.draw(screen)
        pygame.display.flip()

    def _draw_sprites(
        self, screen, camera, level,
        world_items, npcs, enemies, enemy_bullets, bullets, player, weapon,
    ) -> None:
        for sprite in level.walls:
            screen.blit(sprite.image, camera.apply(sprite.rect))
        for sprite in world_items:
            screen.blit(sprite.image, camera.apply(sprite.rect))
        for npc in npcs:
            screen.blit(npc.image, camera.apply(npc.rect))
            npc.draw_name(screen, camera.get_offset())
        for sprite in [*enemy_bullets.sprites(), *bullets.sprites(),
                       *enemies.sprites(), player]:
            screen.blit(sprite.image, camera.apply(sprite.rect))
        if weapon.has_weapon:
            screen.blit(weapon.image, camera.apply(weapon.rect))

    def _draw_enemy_hp_bars(
        self, screen: pygame.Surface, camera, enemies: pygame.sprite.Group,
    ) -> None:
        s = self.s
        for enemy in enemies:
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

    def _draw_save_hint(self, screen: pygame.Surface, save_manager) -> None:
        has  = save_manager.has_save()
        line = "F5 save  |  F9 load" + (" ✓" if has else "")
        surf = self._font_save_hint.render(line, True, (100, 100, 120))
        screen.blit(surf, (self.s.screen_width - surf.get_width() - 12, 8))

    def _draw_debug(
        self, screen, camera, player, enemies,
        enemy_bullets, bullets, world_items, world_manager, audio_manager,
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
        world_manager.draw_debug(screen, offset)
        p.draw_debug(screen, offset)
