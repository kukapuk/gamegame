import pygame
from core.settings import Settings
from core.camera import Camera
from core.hud import HUD
from core.managers.spawn_manager import SpawnManager


class LevelLoader:
    """
    Загружает уровень: очищает группы спрайтов, создаёт Player и Weapon,
    передаёт управление WorldManager и SpawnManager.

    Единственная точка входа — load():
        weapon, player = level_loader.load(path, keep_player=False)
    После вызова game.camera и game.hud пересоздаются автоматически.
    """

    FIRST_LEVEL = "levels/level_1.tmx"

    def __init__(
        self,
        settings:      Settings,
        all_sprites:   pygame.sprite.Group,
        bullets:       pygame.sprite.Group,
        enemies:       pygame.sprite.Group,
        world_items:   pygame.sprite.Group,
        enemy_bullets: pygame.sprite.Group,
        npcs:          pygame.sprite.Group,
        world_manager,
        spawn_manager: SpawnManager,
        casings_group: pygame.sprite.Group = None,
    ) -> None:
        self.s             = settings
        self.all_sprites   = all_sprites
        self.bullets       = bullets
        self.enemies       = enemies
        self.world_items   = world_items
        self.enemy_bullets = enemy_bullets
        self.npcs          = npcs
        self.world         = world_manager
        self.spawn         = spawn_manager
        self.casings_group = casings_group

    def load(
        self,
        path: str,
        keep_player: bool = False,
        current_player=None,
    ):
        """
        Загружает уровень. Возвращает (player, weapon, camera, hud).
        keep_player=True — сохранить текущего игрока (переход между уровнями).
        """
        self._clear_groups()

        player = self._setup_player(path, keep_player, current_player)
        weapon = self._setup_weapon(player)

        self.world.load_level(path, player, self.bullets)

        self.spawn.populate(
            level=self.world.level,
            player=player,
            pathfinder=self.world.pathfinder,
            bullets=self.bullets,
        )

        camera = Camera(self.s)
        hud    = HUD(self.s, player)

        self._sync_weapon(player, weapon)

        return player, weapon, camera, hud

    def _clear_groups(self) -> None:
        self.all_sprites.empty()
        self.bullets.empty()
        self.enemies.empty()
        self.world_items.empty()
        self.enemy_bullets.empty()
        self.npcs.empty()

    def _setup_player(self, path: str, keep_player: bool, current_player):
        from actors.player import Player
        if keep_player and current_player is not None:
            self.all_sprites.add(current_player)
            return current_player
        spawn  = self._get_spawn(path)
        return Player(spawn, self.s, groups=[self.all_sprites])

    def _get_spawn(self, path: str) -> tuple:
        from core.level.level import Level
        return Level(path, self.s.grid_size).player_spawn

    def _setup_weapon(self, player):
        from combat.weapon import Weapon
        return Weapon(
            owner=player,
            settings=self.s,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
            casings_group=self.casings_group,
        )

    def _sync_weapon(self, player, weapon) -> None:
        item = player.get_active_weapon()
        if item is not weapon._weapon_item:
            weapon.equip(item if item else None)
