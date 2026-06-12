import pygame
from items.world_item import WorldItem
from items.weapon_item import WeaponItem
from items.item import ItemType


class LootManager:
    """
    Управляет предметами в игровом мире: спавн, подбор, дроп, стакование.
    Держит ссылку на группу world_items и игрока.
    """

    HINT_COLOR    = (240, 220, 140)
    HINT_BG       = (10, 10, 20, 180)

    def __init__(self, world_items: pygame.sprite.Group) -> None:
        self.world_items       = world_items
        self._nearby: WorldItem = None
        self._font = pygame.font.SysFont("monospace", 14)

    # Public API

    def spawn(self, item, pos: tuple) -> WorldItem:
        return WorldItem(item=item, pos=pos, groups=[self.world_items])

    def spawn_many(self, items: list[tuple]) -> None:
        for item, pos in items:
            self.spawn(item, pos)

    def update(self, player) -> None:
        self._nearby = None
        closest = float("inf")
        for wi in self.world_items:
            dist = (wi.world_pos - player.pos).length()
            if wi.is_in_pickup_range(player.pos) and dist < closest:
                closest = dist
                self._nearby = wi

    def get_nearby(self) -> WorldItem | None:
        return self._nearby

    def try_pickup(self, player, sync_weapon_fn) -> bool:
        if not self._nearby:
            return False
        item   = self._nearby.item
        picked = False

        if isinstance(item, WeaponItem):
            picked = self._pickup_weapon(item, player)
        elif item.stackable:
            remainder = self._pickup_stackable(item, player)
            picked = remainder < item.stack_count
            if picked and remainder > 0:
                item.stack_count = remainder
                picked = False
        else:
            picked = player.backpack.add(item) or player.pouch.add(item)

        if picked:
            self._nearby.kill()
            self._nearby = None
            sync_weapon_fn()

        return picked

    def try_drop(self, player, sync_weapon_fn) -> bool:
        weapon_slots = [s for s in player.pouch.typed_slots
                        if s.allowed_type == ItemType.WEAPON]
        slot = weapon_slots[player.active_weapon_slot]
        if slot.empty:
            return False
        item = slot.take()
        drop_pos = (
            player.pos.x + player.facing.x * 48,
            player.pos.y + player.facing.y * 48,
        )
        self.spawn(item, drop_pos)
        sync_weapon_fn()
        return True

    def draw_hint(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        if not self._nearby:
            return
        item       = self._nearby.item
        screen_pos = self._nearby.rect.move(-camera_offset.x, -camera_offset.y)
        text       = f"[E]  {item.name}"
        surf       = self._font.render(text, True, self.HINT_COLOR)
        pad        = 5
        bg         = pygame.Surface(
            (surf.get_width() + pad * 2, surf.get_height() + pad * 2),
            pygame.SRCALPHA,
        )
        bg.fill(self.HINT_BG)
        bx = screen_pos.centerx - bg.get_width() // 2
        by = screen_pos.top - bg.get_height() - 6
        surface.blit(bg,   (bx, by))
        surface.blit(surf, (bx + pad, by + pad))

    # Private helpers

    def _pickup_weapon(self, item: WeaponItem, player) -> bool:
        weapon_slots = [s for s in player.pouch.typed_slots
                        if s.allowed_type == ItemType.WEAPON]
        for slot in weapon_slots:
            if slot.empty:
                slot.item = item
                return True
        old = weapon_slots[player.active_weapon_slot].item
        weapon_slots[player.active_weapon_slot].item = item
        if old and self._nearby:
            WorldItem(item=old, pos=self._nearby.world_pos, groups=[self.world_items])
        return True

    def _pickup_stackable(self, item, player) -> int:
        remaining = item.stack_count
        for inv in [player.backpack, player.pouch]:
            for slot in inv.all_slots():
                if remaining <= 0:
                    break
                if (slot.item
                        and type(slot.item) == type(item)
                        and hasattr(slot.item, "ammo_type")
                        and slot.item.ammo_type == item.ammo_type
                        and slot.item.stack_count < slot.item.max_stack):
                    space = slot.item.max_stack - slot.item.stack_count
                    take  = min(space, remaining)
                    slot.item.stack_count += take
                    remaining -= take
            if remaining <= 0:
                break
        if remaining > 0:
            from items.ammo import AmmoItem
            temp = AmmoItem(item.ammo_type, remaining)
            for inv in [player.backpack, player.pouch]:
                if inv.add(temp):
                    remaining = 0
                    break
        return remaining
