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
from core.spawn_manager import SpawnManager
from core.level_loader import LevelLoader
from core.renderer import Renderer
from core.input_handler import InputHandler


class Game:
    """
    оркестратор: владеет системами, запускает цикл.
    Вся логика делегирована спец менеджерам.
    """

    FIRST_LEVEL = "levels/level_1.tmx"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen   = pygame.display.set_mode((settings.screen_width, settings.screen_height))
        pygame.display.set_caption(settings.title)
        self.clock   = pygame.time.Clock()
        self.running = True

        # Группы спрайтов
        self.all_sprites   = pygame.sprite.Group()
        self.bullets       = pygame.sprite.Group()
        self.enemies       = pygame.sprite.Group()
        self.world_items   = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.npcs          = pygame.sprite.Group()

        # Системы
        self.loot   = LootManager(self.world_items)
        self.combat = CombatManager(settings)
        self.audio  = AudioManager(settings)
        self.dialog = DialogManager(settings)
        self.save_manager = SaveManager()

        self.world = WorldManager(
            settings=settings,
            all_sprites=self.all_sprites,
            enemies=self.enemies,
            enemy_bullets=self.enemy_bullets,
            npcs=self.npcs,
            loot=self.loot,
        )

        self.spawn = SpawnManager(
            settings=settings,
            all_sprites=self.all_sprites,
            enemies=self.enemies,
            enemy_bullets=self.enemy_bullets,
            npcs=self.npcs,
            loot=self.loot,
        )

        self.level_loader = LevelLoader(
            settings=settings,
            all_sprites=self.all_sprites,
            bullets=self.bullets,
            enemies=self.enemies,
            world_items=self.world_items,
            enemy_bullets=self.enemy_bullets,
            npcs=self.npcs,
            world_manager=self.world,
            spawn_manager=self.spawn,
        )

        self.renderer      = Renderer(settings, self.clock)
        self.input_handler = InputHandler(settings)

        self.debug       = False
        self.player_dead = False

        # Загружаем первый уровень
        self.player, self.weapon, self.camera, self.hud = \
            self.level_loader.load(self.FIRST_LEVEL)

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

        if getattr(inp, "toggle_backpack", False):
            if self.hud.is_open():
                self.hud.close_backpack()
            else:
                self.hud.open_backpack()

        if inp.toggle_debug:
            self.debug = not self.debug
        if inp.toggle_pouch:
            self.hud.toggle_pouch()

        if inp.dialog_key != -1:
            self.dialog.handle_key(inp.dialog_key)
            return

        if inp.switch_weapon != -1:
            self.player.switch_weapon(inp.switch_weapon)
            self._sync_weapon()
        if inp.dash:
            self.player.try_dash()
        if inp.reload:
            self.weapon.try_reload()
        if inp.interact:
            self._handle_interact()
        if inp.drop_weapon:
            self.loot.try_drop(self.player, self._sync_weapon)
        if inp.save:
            self.save_manager.save(self)
        if inp.load:
            self.save_manager.load(self)
        if inp.use_pouch_slot != -1:
            typed_count = len(self.player.pouch.typed_slots)
            self.player.pouch.use_slot(typed_count + inp.use_pouch_slot, self.player)

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

    def _handle_interact(self) -> None:
        nearby_npc = self.world.get_nearby_npc()
        pending    = self.world.get_pending_level()
        if nearby_npc and nearby_npc.dialog_file:
            self.dialog.start(nearby_npc.dialog_file)
        elif pending:
            self._transition_level(pending)
        else:
            self.loot.try_pickup(self.player, self._sync_weapon)

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

        self._propagate_sound_events()

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

    def _propagate_sound_events(self) -> None:
        for ev in self.audio.get_sound_events():
            for enemy in self.enemies:
                enemy.hear_sound(ev["pos"], ev["radius"])

    # Level transitions

    def _transition_level(self, target: str) -> None:
        self.world.consume_pending_level()
        self.player, self.weapon, self.camera, self.hud = self.level_loader.load(
            f"levels/{target}", keep_player=True, current_player=self.player
        )

    def _restart(self) -> None:
        self.player_dead = False
        self.player, self.weapon, self.camera, self.hud = \
            self.level_loader.load(self.FIRST_LEVEL)

    # Helpers

    def _sync_weapon(self) -> None:
        item = self.player.get_active_weapon()
        if item is not self.weapon._weapon_item:
            self.weapon.equip(item if item else None)

    # Draw

    def _draw(self, i_hold_progress: float = 0.0) -> None:
        self.renderer.draw(
            self.screen,
            level           = self.world.level,
            camera          = self.camera,
            player          = self.player,
            weapon          = self.weapon,
            enemies         = self.enemies,
            bullets         = self.bullets,
            enemy_bullets   = self.enemy_bullets,
            world_items     = self.world_items,
            npcs            = self.npcs,
            hud             = self.hud,
            world_manager   = self.world,
            loot_manager    = self.loot,
            dialog_manager  = self.dialog,
            save_manager    = self.save_manager,
            audio_manager   = self.audio,
            i_hold_progress = i_hold_progress,
            player_dead     = self.player_dead,
            debug           = self.debug,
        )
