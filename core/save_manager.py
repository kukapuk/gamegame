import json
import os
import pygame
from items.item_registry import serialize_item, deserialize_item


SAVE_DIR  = "saves"
SAVE_FILE = os.path.join(SAVE_DIR, "save_0.json")


class SaveManager:
    """
    Сохраняет и загружает состояние игры в JSON.
    F5 — сохранить, F9 — загрузить.
    """

    def save(self, game) -> bool:
        os.makedirs(SAVE_DIR, exist_ok=True)
        try:
            data = self._serialize(game)
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[save] saved to {SAVE_FILE}")
            return True
        except Exception as e:
            print(f"[save] error: {e}")
            return False

    def load(self, game) -> bool:
        if not os.path.exists(SAVE_FILE):
            print("[save] no save file found")
            return False
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._deserialize(game, data)
            print(f"[save] loaded from {SAVE_FILE}")
            return True
        except Exception as e:
            print(f"[save] error: {e}")
            return False

    def has_save(self) -> bool:
        return os.path.exists(SAVE_FILE)

    def _serialize(self, game) -> dict:
        p = game.player
        return {
            "player": {
                "pos":                 [p.pos.x, p.pos.y],
                "hp":                  p.hp,
                "stamina":             p.stamina,
                "active_weapon_slot":  p.active_weapon_slot,
            },
            "pouch":      self._serialize_inventory(p.pouch),
            "backpack":   self._serialize_inventory(p.backpack),
            "enemies":    self._serialize_enemies(game),
            "world_items": self._serialize_world_items(game),
        }

    def _serialize_inventory(self, inventory) -> list:
        result = []
        for slot in inventory.all_slots():
            result.append({
                "allowed_type": slot.allowed_type.name if slot.allowed_type else None,
                "item":         serialize_item(slot.item),
            })
        return result

    def _serialize_enemies(self, game) -> list:
        result = []
        for enemy in game.enemies:
            result.append({
                "pos":         [enemy.pos.x, enemy.pos.y],
                "hp":          enemy.hp,
                "armor_class": enemy.armor_class,
                "state":       enemy.state,
                "type":        "shooter" if enemy.can_shoot else "grunt",
            })
        return result

    def _serialize_world_items(self, game) -> list:
        result = []
        for wi in game.world_items:
            data = serialize_item(wi.item)
            if data:
                result.append({
                    "pos":  [wi.world_pos.x, wi.world_pos.y],
                    "item": data,
                })
        return result

    def _deserialize(self, game, data: dict) -> None:
        game.player_dead = False
        game.all_sprites.empty()
        game.bullets.empty()
        game.enemies.empty()
        game.world_items.empty()
        game.enemy_bullets.empty()

        from actors.player import Player
        from combat.weapon import Weapon
        from core.hud import HUD
        from core.camera import Camera

        pd    = data["player"]
        spawn = tuple(pd["pos"])

        game.player = Player(spawn, game.settings, groups=[game.all_sprites])
        game.player.hp              = pd.get("hp", game.player.max_hp)
        game.player.stamina         = pd.get("stamina", game.player.stats.max_stamina)
        game.player.active_weapon_slot = pd.get("active_weapon_slot", 0)

        self._deserialize_inventory(game.player.pouch,    data.get("pouch", []))
        self._deserialize_inventory(game.player.backpack, data.get("backpack", []))

        game.weapon = Weapon(
            owner=game.player,
            settings=game.settings,
            bullet_group=game.bullets,
            all_sprites=game.all_sprites,
        )

        self._deserialize_enemies(game, data.get("enemies", []))
        self._deserialize_world_items(game, data.get("world_items", []))

        game.hud    = HUD(game.settings, game.player)
        game.camera = Camera(game.settings)
        game._sync_weapon()

    def _deserialize_inventory(self, inventory, slots_data: list) -> None:
        all_slots = inventory.all_slots()
        for i, slot_data in enumerate(slots_data):
            if i >= len(all_slots):
                break
            item_data = slot_data.get("item")
            if item_data:
                item = deserialize_item(item_data)
                if item:
                    all_slots[i].put(item)

    def _deserialize_enemies(self, game, enemies_data: list) -> None:
        from actors.enemy import make_grunt, make_shooter, EnemyState

        grunt_patrol  = [(800, 300), (800, 600), (1100, 600), (1100, 300)]

        for ed in enemies_data:
            pos         = tuple(ed["pos"])
            armor_class = ed.get("armor_class", 0)
            hp          = ed.get("hp", 60)
            state       = ed.get("state", EnemyState.IDLE)
            etype       = ed.get("type", "grunt")

            if etype == "shooter":
                e = make_shooter(
                    pos=pos, target=game.player,
                    armor_class=armor_class,
                    groups=[game.all_sprites, game.enemies],
                    bullet_group=game.enemy_bullets,
                    all_sprites=game.all_sprites,
                )
            else:
                e = make_grunt(
                    pos=pos, target=game.player,
                    armor_class=armor_class,
                    groups=[game.all_sprites, game.enemies],
                )
                e.set_patrol(grunt_patrol)

            e.hp            = hp
            e.state         = state
            e.pathfinder    = game.pathfinder
            e.enemies_group = game.enemies

    def _deserialize_world_items(self, game, items_data: list) -> None:
        from items.world_item import WorldItem
        for wd in items_data:
            item = deserialize_item(wd.get("item"))
            if item:
                pos = tuple(wd["pos"])
                WorldItem(item=item, pos=pos, groups=[game.world_items])
