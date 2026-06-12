import pygame
from core.settings import Settings
from core.loot_manager import LootManager


class SpawnManager:
    """
    Читает объекты уровня из tmx и создаёт игровые сущности:
    врагов, NPC и предметы на полу.

    Полностью заменяет:
      - WorldManager._spawn_from_level / _parse_patrol
      - Game._give_test_items / _spawn_world_items

    Поддерживаемые типы объектов в tmx:
      enemy_grunt    — props: armor_class, patrol_x1/y1, patrol_x2/y2, …
      enemy_shooter  — props: armor_class
      npc            — props: npc_name, dialog_file
      item_spawn     — props: item_id, count (опц.), slot (опц. «backpack»/«pouch»)
      player_spawn   — обрабатывается в Level, здесь игнорируется
      level_exit     — обрабатывается в WorldManager, здесь игнорируется
    """

    def __init__(
        self,
        settings: Settings,
        all_sprites:   pygame.sprite.Group,
        enemies:       pygame.sprite.Group,
        enemy_bullets: pygame.sprite.Group,
        npcs:          pygame.sprite.Group,
        loot:          LootManager,
    ) -> None:
        self.s             = settings
        self.all_sprites   = all_sprites
        self.enemies       = enemies
        self.enemy_bullets = enemy_bullets
        self.npcs          = npcs
        self.loot          = loot

    # Public API

    def populate(self, level, player, pathfinder, bullets) -> None:
        """
        Спавнит всё что описано в tmx-объектах уровня.
        Вызывается из LevelLoader после загрузки уровня.
        """
        for obj in level.objects:
            t     = obj["type"]
            pos   = (obj["x"], obj["y"])
            props = obj["props"]

            if t == "enemy_grunt":
                self._spawn_grunt(pos, props, player, pathfinder)
            elif t == "enemy_shooter":
                self._spawn_shooter(pos, props, player, pathfinder, bullets)
            elif t == "npc":
                self._spawn_npc(pos, props)
            elif t == "item_spawn":
                self._spawn_item(pos, props, player)

    # Enemies

    def _spawn_grunt(self, pos, props, player, pathfinder) -> None:
        from actors.enemy import make_grunt
        e = make_grunt(
            pos=pos,
            target=player,
            armor_class=props.get("armor_class", 0),
            groups=[self.all_sprites, self.enemies],
        )
        e.pathfinder    = pathfinder
        e.enemies_group = self.enemies
        patrol = self._parse_patrol(props)
        if patrol:
            e.set_patrol(patrol)

    def _spawn_shooter(self, pos, props, player, pathfinder, bullets) -> None:
        from actors.enemy import make_shooter
        e = make_shooter(
            pos=pos,
            target=player,
            armor_class=props.get("armor_class", 0),
            groups=[self.all_sprites, self.enemies],
            bullet_group=self.enemy_bullets,
            all_sprites=self.all_sprites,
        )
        e.pathfinder    = pathfinder
        e.enemies_group = self.enemies

    def _parse_patrol(self, props: dict) -> list:
        points = []
        i = 1
        while f"patrol_x{i}" in props and f"patrol_y{i}" in props:
            points.append((props[f"patrol_x{i}"], props[f"patrol_y{i}"]))
            i += 1
        return points

    # NPC

    def _spawn_npc(self, pos, props) -> None:
        from actors.npc import NPC
        NPC(
            pos=pos,
            name=props.get("npc_name", "NPC"),
            dialog_file=props.get("dialog_file", ""),
            groups=[self.all_sprites, self.npcs],
        )

    # Items

    def _spawn_item(self, pos, props: dict, player) -> None:
        """
        Спавнит предмет из tmx. Примеры props в Tiled:
          item_id=carbine                    → оружие на пол
          item_id=ammo_carbine  count=30     → патроны на пол
          item_id=medkit_30     slot=backpack → сразу в рюкзак игрока
          item_id=armor_2       slot=pouch   → сразу в подсумок
        """
        from items.item_registry import deserialize_item
        item_id = props.get("item_id", "")
        count   = int(props.get("count", 1))
        slot    = props.get("slot", "world")   # "world" | "backpack" | "pouch"

        item = self._make_item(item_id, count)
        if item is None:
            print(f"[spawn] unknown item_id: {item_id!r}")
            return

        if slot == "backpack":
            player.backpack.add(item)
        elif slot == "pouch":
            player.pouch.add(item)
        else:
            self.loot.spawn(item, pos)

    def _make_item(self, item_id: str, count: int):
        """Фабрика предметов по строковому id."""
        import inspect
        from items.item_registry import REGISTRY, WEAPON_REGISTRY, register_weapons

        register_weapons()

        if item_id in REGISTRY:
            factory = REGISTRY[item_id]
            sig     = inspect.signature(factory)
            if "count" in sig.parameters:
                return factory(count)
            return factory()

        if item_id in WEAPON_REGISTRY:
            return WEAPON_REGISTRY[item_id]()

        return None
