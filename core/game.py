import pygame
from core.settings import Settings
from core.camera import Camera
from core.hud import HUD
from core.audio import AudioManager
from core.save_manager import SaveManager
from core.dialog_manager import DialogManager
from core.loot_manager import LootManager
from core.combat_manager import CombatManager
from core.world_manager import WorldManager
from actors.player import Player
from combat.weapon import Weapon
from items.consumable import make_medkit
from items.weapon_item import make_carbine, make_shotgun, make_sniper
from items.ammo import make_ammo, AmmoType


class Game:
    """Central game loop, renderer, and scene owner."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen   = pygame.display.set_mode((settings.screen_width, settings.screen_height))
        pygame.display.set_caption(settings.title)
        self.clock   = pygame.time.Clock()
        self.running = True

        self.all_sprites   = pygame.sprite.Group()
        self.bullets       = pygame.sprite.Group()
        self.enemies       = pygame.sprite.Group()
        self.world_items   = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.npcs          = pygame.sprite.Group()

        self.loot   = LootManager(self.world_items)
        self.combat = CombatManager(settings)
        self.world  = WorldManager(
            settings=settings,
            all_sprites=self.all_sprites,
            enemies=self.enemies,
            enemy_bullets=self.enemy_bullets,
            npcs=self.npcs,
            loot=self.loot,
        )

        self.player = None
        self.weapon = None
        self._load_level("levels/level_1.tmx")

        self.camera       = Camera(settings)
        self.hud          = HUD(settings, self.player)
        self.audio        = AudioManager(settings)
        self.save_manager = SaveManager()
        self.dialog       = DialogManager(settings)

        self.debug       = True
        self.player_dead = False

        self._i_held_time: float = 0.0
        self._i_triggered: bool  = False

        self._font_interact  = pygame.font.SysFont("monospace", 14)
        self._death_font_big = pygame.font.SysFont("monospace", 72, bold=True)
        self._death_font_sm  = pygame.font.SysFont("monospace", 24)

    # Level loading

    def _load_level(self, path: str, keep_player: bool = False) -> None:
        self.all_sprites.empty()
        self.bullets.empty()
        self.enemies.empty()
        self.world_items.empty()
        self.enemy_bullets.empty()
        self.npcs.empty()

        if not keep_player or self.player is None:
            spawn       = self._get_spawn(path)
            self.player = Player(spawn, self.settings, groups=[self.all_sprites])
        else:
            self.all_sprites.add(self.player)

        self.weapon = Weapon(
            owner=self.player,
            settings=self.settings,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
        )

        self.world.load_level(path, self.player, self.bullets)

        self._give_test_items()
        self._spawn_world_items()
        self._sync_weapon()

        if hasattr(self, "hud") and self.hud:
            self.hud = HUD(self.settings, self.player)
        if hasattr(self, "camera") and self.camera:
            self.camera = Camera(self.settings)

    def _get_spawn(self, path: str) -> tuple:
        from core.level import Level
        tmp = Level(path, self.settings.grid_size)
        return tmp.player_spawn

    def _sync_weapon(self) -> None:
        item = self.player.get_active_weapon()
        if item is self.weapon._weapon_item:
            return
        self.weapon.equip(item if item else None)

    # TODO: убрать когда предметы будут задаваться в tmx
    def _give_test_items(self) -> None:
        test_items = [
            make_ammo(AmmoType.CARBINE, 90),
            make_ammo(AmmoType.SHOTGUN, 48),
            make_ammo(AmmoType.SNIPER,  20),
            make_medkit(30),
            make_medkit(30),
        ]
        for i, item in enumerate(test_items):
            slot = self.player.backpack.get_slot(i)
            if slot:
                slot.put(item)

    # TODO: убрать когда предметы будут задаваться в tmx
    def _spawn_world_items(self) -> None:
        from items.armor import make_light_armor, make_medium_armor, make_heavy_armor
        cx, cy = self.settings.screen_width // 2, self.settings.screen_height // 2
        self.loot.spawn_many([
            (make_carbine(),                  (cx + 120, cy + 60)),
            (make_shotgun(),                  (cx - 140, cy + 80)),
            (make_sniper(),                   (cx + 60,  cy - 120)),
            (make_ammo(AmmoType.CARBINE, 30), (cx + 180, cy - 40)),
            (make_ammo(AmmoType.SHOTGUN, 16), (cx - 60,  cy - 100)),
            (make_ammo(AmmoType.SNIPER,  5),  (cx - 180, cy + 40)),
            (make_light_armor(),              (cx + 240, cy + 120)),
            (make_medium_armor(),             (cx - 240, cy - 60)),
            (make_heavy_armor(),              (cx,       cy + 160)),
        ])

    # Main loop

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            self._handle_i_hold(dt)
            self._handle_events()
            if not self.player_dead:
                self._update(dt)
            self._draw()

    # Events

    def _handle_i_hold(self, dt: float) -> None:
        if self.dialog.active:
            return
        keys = pygame.key.get_pressed()
        if keys[pygame.K_i]:
            self._i_held_time += dt
            if self._i_held_time >= self.settings.backpack_hold_time and not self._i_triggered:
                self._i_triggered = True
                if self.hud.is_open():
                    self.hud.close_backpack()
                else:
                    self.hud.open_backpack()
        else:
            self._i_held_time = 0.0
            self._i_triggered = False

    def _handle_events(self) -> None:
        if self.player_dead:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self._restart()
            return

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if self.dialog.active:
                    self.dialog.handle_key(event.key)
                    return

                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_1:
                    self.player.switch_weapon(0)
                    self._sync_weapon()
                elif event.key == pygame.K_2:
                    self.player.switch_weapon(1)
                    self._sync_weapon()
                elif event.key == pygame.K_TAB:
                    self.hud.toggle_pouch()
                elif event.key == pygame.K_F1:
                    self.debug = not self.debug
                elif event.key == pygame.K_SPACE:
                    self.player.try_dash()
                elif event.key == pygame.K_r:
                    self.weapon.try_reload()
                elif event.key == pygame.K_e:
                    nearby_npc = self.world.get_nearby_npc()
                    pending    = self.world.get_pending_level()
                    if nearby_npc and nearby_npc.dialog_file:
                        self.dialog.start(nearby_npc.dialog_file)
                    elif pending:
                        self._transition_level(pending)
                    else:
                        self.loot.try_pickup(self.player, self._sync_weapon)
                elif event.key == pygame.K_g:
                    self.loot.try_drop(self.player, self._sync_weapon)
                elif event.key == pygame.K_F5:
                    self.save_manager.save(self)
                elif event.key == pygame.K_F9:
                    self.save_manager.load(self)
                else:
                    if not self.hud.is_open():
                        typed_count = len(self.player.pouch.typed_slots)
                        for i, key in enumerate(self.settings.pouch_hotkeys):
                            if event.key == key:
                                self.player.pouch.use_slot(typed_count + i, self.player)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    grabbed = self.hud.handle_world_mouse_down(
                        event.pos, self.world_items, self.camera.get_offset()
                    )
                    if not grabbed:
                        self.hud.handle_mouse_down(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    result = self.hud.handle_mouse_up(event.pos)
                    if result["kill_world_item"]:
                        result["kill_world_item"].kill()
                    if result["drop_item"]:
                        drop_pos = (
                            self.player.pos.x + self.player.facing.x * 48,
                            self.player.pos.y + self.player.facing.y * 48,
                        )
                        self.loot.spawn(result["drop_item"], drop_pos)
                    self._sync_weapon()

            elif event.type == pygame.MOUSEMOTION:
                self.hud.handle_mouse_motion(event.pos)
                self.hud.update_world_hover(event.pos, self.world_items, self.camera.get_offset())

    # Update

    def _update(self, dt: float) -> None:
        if self.dialog.active:
            self.camera.follow(self.player)
            return

        self.player.update(dt, self.world.level.walls)
        self.enemies.update(dt, self.world.level.walls)
        self.bullets.update(dt)
        self.enemy_bullets.update(dt)
        self.world_items.update(dt)
        self.weapon.update(dt, self.camera.get_offset())
        self.audio.update(dt)
        self.loot.update(self.player)
        self.world.update(self.player)

        self._check_sound_events()

        if pygame.mouse.get_pressed()[0] and not self.hud.is_open():
            if self.weapon.try_shoot():
                radius = (self.weapon._weapon_item.stats.sound_radius
                          if self.weapon.has_weapon
                          else self.settings.gunshot_sound_radius)
                self.audio.play_at("gunshot", self.player.pos, radius)

        self.combat.update(
            self.player, self.enemies,
            self.bullets, self.enemy_bullets,
            self.world.level.walls,
        )
        self.camera.follow(self.player)

        if not self.player.alive:
            self.player_dead = True

    def _check_sound_events(self) -> None:
        for ev in self.audio.get_sound_events():
            for enemy in self.enemies:
                enemy.hear_sound(ev["pos"], ev["radius"])

    def _transition_level(self, target: str) -> None:
        self.world.consume_pending_level()
        self._load_level(f"levels/{target}", keep_player=True)

    # Restart

    def _restart(self) -> None:
        self.player_dead = False
        self.player      = None
        self._load_level("levels/level_1.tmx", keep_player=False)

    # Draw

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self.world.level.draw_floor(self.screen, self.camera.get_offset())
        self._draw_sprites()
        self._draw_enemy_hp_bars()
        self.hud.draw_world_hover(self.screen, self.camera.get_offset())
        self.loot.draw_hint(self.screen, self.camera.get_offset())
        self.world.draw(self.screen, self.camera.get_offset())
        self._draw_npc_hint()
        self.hud.draw(self.screen,
                      i_hold_progress=self._i_held_time / self.settings.backpack_hold_time,
                      weapon=self.weapon)
        if self.debug:
            self._draw_debug_info()
        if self.player_dead:
            self._draw_death_screen()
        self._draw_save_hint(self.screen)
        self.dialog.draw(self.screen)
        pygame.display.flip()

    def _draw_sprites(self) -> None:
        for sprite in self.world.level.walls:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        for sprite in self.world_items:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        for npc in self.npcs:
            self.screen.blit(npc.image, self.camera.apply(npc.rect))
            npc.draw_name(self.screen, self.camera.get_offset())
        for sprite in [*self.enemy_bullets.sprites(), *self.bullets.sprites(),
                       *self.enemies.sprites(), self.player]:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        if self.weapon.has_weapon:
            self.screen.blit(self.weapon.image, self.camera.apply(self.weapon.rect))

    def _draw_enemy_hp_bars(self) -> None:
        s = self.settings
        for enemy in self.enemies:
            bar_rect = self.camera.apply(enemy.rect)
            bx = bar_rect.centerx - s.enemy_hp_bar_width // 2
            by = bar_rect.top - 8
            pygame.draw.rect(self.screen, s.enemy_hp_bar_bg,
                             (bx, by, s.enemy_hp_bar_width, s.enemy_hp_bar_height))
            fill = int(s.enemy_hp_bar_width * enemy.hp / enemy.max_hp)
            if fill > 0:
                pygame.draw.rect(self.screen, s.enemy_hp_bar_color,
                                 (bx, by, fill, s.enemy_hp_bar_height))

    def _draw_npc_hint(self) -> None:
        nearby_npc = self.world.get_nearby_npc()
        if not nearby_npc:
            return
        screen_pos = self.camera.apply(nearby_npc.rect)
        text       = f"[E]  Talk to {nearby_npc.name}"
        surf       = self._font_interact.render(text, True, (200, 220, 255))
        pad        = 5
        bg         = pygame.Surface(
            (surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA
        )
        bg.fill((10, 10, 20, 180))
        bx = screen_pos.centerx - bg.get_width() // 2
        by = screen_pos.top - bg.get_height() - 6
        self.screen.blit(bg,   (bx, by))
        self.screen.blit(surf, (bx + pad, by + pad))

    def _draw_death_screen(self) -> None:
        overlay = pygame.Surface(
            (self.settings.screen_width, self.settings.screen_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        cx = self.settings.screen_width  // 2
        cy = self.settings.screen_height // 2
        title = self._death_font_big.render("YOU DIED", True, (200, 40, 40))
        hint  = self._death_font_sm.render("press any key to restart", True, (160, 160, 160))
        self.screen.blit(title, title.get_rect(center=(cx, cy - 40)))
        self.screen.blit(hint,  hint.get_rect(center=(cx, cy + 40)))

    def _draw_save_hint(self, screen: pygame.Surface) -> None:
        font = pygame.font.SysFont("monospace", 12)
        has  = self.save_manager.has_save()
        line = "F5 save  |  F9 load" + (" ✓" if has else "")
        surf = font.render(line, True, (100, 100, 120))
        screen.blit(surf, (self.settings.screen_width - surf.get_width() - 12, 8))

    def _draw_debug_info(self) -> None:
        font  = pygame.font.SysFont("monospace", 16)
        p     = self.player
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({p.pos.x:.0f}, {p.pos.y:.0f})",
            f"stamina: {p.stamina:.0f} / {p.stats.max_stamina:.0f}",
            f"dash cd: {p._dash_cooldown:.2f}s",
            f"bullets: {len(self.bullets)}  enemies: {len(self.enemies)}",
            f"world_items: {len(self.world_items)}",
            f"enemy_bullets: {len(self.enemy_bullets)}",
            f"level: {self.world.level.path if hasattr(self.world.level, 'path') else '?'}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        for enemy in self.enemies:
            enemy.draw_debug(self.screen, self.camera.get_offset())
        self.audio.draw_debug(self.screen, self.camera.get_offset())
        self.world.draw_debug(self.screen, self.camera.get_offset())
        p.draw_debug(self.screen, self.camera.get_offset())
