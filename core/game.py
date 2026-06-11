import pygame
from core.settings import Settings
from core.camera import Camera
from core.hud import HUD
from core.level import Level
from core.audio import AudioManager
from core.pathfinder import Pathfinder
from core.save_manager import SaveManager
from core.dialog_manager import DialogManager
from core.loot_manager import LootManager
from core.combat_manager import CombatManager
from actors.player import Player
from actors.enemy import make_grunt, make_shooter
from actors.npc import NPC
from combat.weapon import Weapon
from items.world_item import WorldItem
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

        self.level = Level("levels/level_1.tmx", settings.grid_size)

        spawn       = self.level.player_spawn
        self.player = Player(spawn, settings, groups=[self.all_sprites])

        self.pathfinder = Pathfinder(settings.grid_size)
        self.pathfinder.build_from_walls(self.level.walls, self.level.cols, self.level.rows)

        self.weapon = Weapon(
            owner=self.player,
            settings=settings,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
        )

        self.loot   = LootManager(self.world_items)
        self.combat = CombatManager(settings)

        self._spawn_from_level()
        self._give_test_items()
        self._spawn_world_items()
        self._sync_weapon()

        self.camera       = Camera(settings)
        self.hud          = HUD(settings, self.player)
        self.audio        = AudioManager(settings)
        self.save_manager = SaveManager()
        self.dialog       = DialogManager(settings)

        self.debug       = True
        self.player_dead = False

        self._i_held_time: float = 0.0
        self._i_triggered: bool  = False
        self._nearby_npc         = None

        self._font_interact  = pygame.font.SysFont("monospace", 14)
        self._death_font_big = pygame.font.SysFont("monospace", 72, bold=True)
        self._death_font_sm  = pygame.font.SysFont("monospace", 24)

    # ------------------------------------------------------------------
    # Init helpers
    # ------------------------------------------------------------------

    def _sync_weapon(self) -> None:
        item = self.player.get_active_weapon()
        if item is self.weapon._weapon_item:
            return
        self.weapon.equip(item if item else None)

    def _spawn_from_level(self) -> None:
        for obj in self.level.objects:
            t     = obj["type"]
            pos   = (obj["x"], obj["y"])
            props = obj["props"]

            if t == "enemy_grunt":
                e = make_grunt(
                    pos=pos, target=self.player,
                    armor_class=props.get("armor_class", 0),
                    groups=[self.all_sprites, self.enemies],
                )
                e.pathfinder    = self.pathfinder
                e.enemies_group = self.enemies
                patrol = self._parse_patrol(props)
                if patrol:
                    e.set_patrol(patrol)

            elif t == "enemy_shooter":
                e = make_shooter(
                    pos=pos, target=self.player,
                    armor_class=props.get("armor_class", 0),
                    groups=[self.all_sprites, self.enemies],
                    bullet_group=self.enemy_bullets,
                    all_sprites=self.all_sprites,
                )
                e.pathfinder    = self.pathfinder
                e.enemies_group = self.enemies

            elif t == "npc":
                NPC(
                    pos=pos,
                    name=props.get("npc_name", "NPC"),
                    dialog_file=props.get("dialog_file", ""),
                    groups=[self.all_sprites, self.npcs],
                )

    def _parse_patrol(self, props: dict) -> list:
        points = []
        i = 1
        while f"patrol_x{i}" in props and f"patrol_y{i}" in props:
            points.append((props[f"patrol_x{i}"], props[f"patrol_y{i}"]))
            i += 1
        return points

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

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            self._handle_i_hold(dt)
            self._handle_events()
            if not self.player_dead:
                self._update(dt)
            self._draw()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

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
                    if self._nearby_npc and self._nearby_npc.dialog_file:
                        self.dialog.start(self._nearby_npc.dialog_file)
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

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def _update(self, dt: float) -> None:
        if self.dialog.active:
            self.camera.follow(self.player)
            return

        self.player.update(dt, self.level.walls)
        self.enemies.update(dt, self.level.walls)
        self.bullets.update(dt)
        self.enemy_bullets.update(dt)
        self.world_items.update(dt)
        self.weapon.update(dt, self.camera.get_offset())
        self.audio.update(dt)
        self.loot.update(self.player)

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
            self.level.walls,
        )
        self._update_nearby_npc()
        self.camera.follow(self.player)

        if not self.player.alive:
            self.player_dead = True

    def _check_sound_events(self) -> None:
        for ev in self.audio.get_sound_events():
            for enemy in self.enemies:
                enemy.hear_sound(ev["pos"], ev["radius"])

    def _update_nearby_npc(self) -> None:
        self._nearby_npc = None
        for npc in self.npcs:
            if npc.is_in_interact_range(self.player.pos):
                self._nearby_npc = npc
                break

    # ------------------------------------------------------------------
    # Restart
    # ------------------------------------------------------------------

    def _restart(self) -> None:
        self.player_dead = False
        self.all_sprites.empty()
        self.bullets.empty()
        self.enemies.empty()
        self.world_items.empty()
        self.enemy_bullets.empty()
        self.npcs.empty()

        spawn       = self.level.player_spawn
        self.player = Player(spawn, self.settings, groups=[self.all_sprites])
        self.weapon = Weapon(
            owner=self.player,
            settings=self.settings,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
        )
        self.hud    = HUD(self.settings, self.player)
        self.camera = Camera(self.settings)
        self.loot   = LootManager(self.world_items)
        self.combat = CombatManager(self.settings)

        self._spawn_from_level()
        self._give_test_items()
        self._spawn_world_items()
        self._sync_weapon()

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self.level.draw_floor(self.screen, self.camera.get_offset())
        self._draw_sprites()
        self._draw_enemy_hp_bars()
        self.hud.draw_world_hover(self.screen, self.camera.get_offset())
        self.loot.draw_hint(self.screen, self.camera.get_offset())
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
        for sprite in self.level.walls:
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
        if not self._nearby_npc:
            return
        screen_pos = self.camera.apply(self._nearby_npc.rect)
        text       = f"[E]  Talk to {self._nearby_npc.name}"
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
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        for enemy in self.enemies:
            enemy.draw_debug(self.screen, self.camera.get_offset())
        self.audio.draw_debug(self.screen, self.camera.get_offset())
        p.draw_debug(self.screen, self.camera.get_offset())
