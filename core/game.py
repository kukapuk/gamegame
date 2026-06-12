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
from core.renderer import Renderer
from core.input_handler import InputHandler
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

        self.debug       = False
        self.player_dead = False

        self.renderer      = Renderer(settings, self.clock)
        self.input_handler = InputHandler(settings)

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
            dt  = self.clock.tick(self.settings.fps) / 1000.0
            inp = self.input_handler.process(
                dt,
                player_dead   = self.player_dead,
                dialog_active = self.dialog.active,
                hud_open      = self.hud.is_open(),
            )
            self._apply_input(inp)
            if not self.player_dead:
                self._update(dt)
            self._draw(inp.i_hold_progress)

    # Input

    def _apply_input(self, inp) -> None:
        if inp.quit:
            self.running = False
            return
        if inp.restart:
            self._restart()
            return

        # hold-рюкзак
        if getattr(inp, "toggle_backpack", False):
            if self.hud.is_open():
                self.hud.close_backpack()
            else:
                self.hud.open_backpack()

        if inp.toggle_debug:
            self.debug = not self.debug
        if inp.toggle_pouch:
            self.hud.toggle_pouch()

        # диалог
        if inp.dialog_key != -1:
            self.dialog.handle_key(inp.dialog_key)
            return

        # геймплей
        if inp.switch_weapon != -1:
            self.player.switch_weapon(inp.switch_weapon)
            self._sync_weapon()
        if inp.dash:
            self.player.try_dash()
        if inp.reload:
            self.weapon.try_reload()
        if inp.interact:
            nearby_npc = self.world.get_nearby_npc()
            pending    = self.world.get_pending_level()
            if nearby_npc and nearby_npc.dialog_file:
                self.dialog.start(nearby_npc.dialog_file)
            elif pending:
                self._transition_level(pending)
            else:
                self.loot.try_pickup(self.player, self._sync_weapon)
        if inp.drop_weapon:
            self.loot.try_drop(self.player, self._sync_weapon)
        if inp.save:
            self.save_manager.save(self)
        if inp.load:
            self.save_manager.load(self)
        if inp.use_pouch_slot != -1:
            typed_count = len(self.player.pouch.typed_slots)
            self.player.pouch.use_slot(typed_count + inp.use_pouch_slot, self.player)

        # мышь
        if inp.lmb_down:
            grabbed = self.hud.handle_world_mouse_down(
                pygame.mouse.get_pos(), self.world_items, self.camera.get_offset()
            )
            if not grabbed:
                self.hud.handle_mouse_down(pygame.mouse.get_pos())
        if inp.lmb_up:
            result = self.hud.handle_mouse_up(pygame.mouse.get_pos())
            if result["kill_world_item"]:
                result["kill_world_item"].kill()
            if result["drop_item"]:
                drop_pos = (
                    self.player.pos.x + self.player.facing.x * 48,
                    self.player.pos.y + self.player.facing.y * 48,
                )
                self.loot.spawn(result["drop_item"], drop_pos)
            self._sync_weapon()
        if inp.mouse_motion:
            pos = pygame.mouse.get_pos()
            self.hud.handle_mouse_motion(pos)
            self.hud.update_world_hover(pos, self.world_items, self.camera.get_offset())

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

    def _draw(self, i_hold_progress: float = 0.0) -> None:
        self.renderer.draw(
            self.screen,
            level          = self.world.level,
            camera         = self.camera,
            player         = self.player,
            weapon         = self.weapon,
            enemies        = self.enemies,
            bullets        = self.bullets,
            enemy_bullets  = self.enemy_bullets,
            world_items    = self.world_items,
            npcs           = self.npcs,
            hud            = self.hud,
            world_manager  = self.world,
            loot_manager   = self.loot,
            dialog_manager = self.dialog,
            save_manager   = self.save_manager,
            audio_manager  = self.audio,
            i_hold_progress = i_hold_progress,
            player_dead    = self.player_dead,
            debug          = self.debug,
        )
