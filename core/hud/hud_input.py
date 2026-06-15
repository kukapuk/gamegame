"""
hud_input.py — обработка мыши и клавиатуры для HUD.
"""
import pygame


class HUDInput:

    def handle_mouse_down(self, pos: tuple) -> None:
        if not self.is_open():
            return
        if self.handle_info_panels_mouse_down(pos):
            return
        if self.backpack_open and self._grid_ui.handle_mouse_down(pos):
            return
        for slot, rect in self._pouch_interactive_rects():
            if rect.collidepoint(pos) and not slot.empty:
                item = slot.take()
                self._grid_ui.start_drag_from_slot(item, slot)
                return

    def handle_world_mouse_down(self, pos: tuple, world_items, camera_offset) -> bool:
        if not self.backpack_open:
            return False
        return self._grid_ui.handle_world_mouse_down(pos, world_items, camera_offset)

    def update_world_hover(self, pos: tuple, world_items, camera_offset) -> None:
        if not self.backpack_open:
            self._hovered_world_item = None
            return
        self._hovered_world_item = None
        for wi in world_items:
            if not wi.is_in_pickup_range(self.player.pos):
                continue
            screen_rect = wi.rect.move(-camera_offset.x, -camera_offset.y)
            if screen_rect.collidepoint(pos):
                self._hovered_world_item = wi
                break

    def handle_mouse_up(self, pos: tuple) -> dict:
        result = {"kill_world_item": None, "drop_item": None}
        self.handle_info_panels_mouse_up()

        if self._grid_ui._panel_dragging:
            self._grid_ui.handle_mouse_up(pos)
            return result

        if not self._grid_ui.is_dragging:
            return result

        drag_item    = self._grid_ui.get_drag_item()
        source_world = self._grid_ui._drag.source_world_item if self._grid_ui._drag else None
        source_grid  = self._grid_ui._drag.source_grid       if self._grid_ui._drag else None
        source_slot  = self._grid_ui._drag.source_slot       if self._grid_ui._drag else None

        for slot, rect in self._pouch_interactive_rects():
            if not rect.collidepoint(pos):
                continue

            target_item = slot.item

            from items.cleaning_kit import CleaningKit
            from items.weapon_item import WeaponItem
            if isinstance(drag_item, CleaningKit) and isinstance(target_item, WeaponItem):
                drag_item.apply_to_weapon(target_item)
                self._grid_ui._drag = None
                if source_world:
                    result["kill_world_item"] = source_world
                return result

            if (target_item and drag_item.stackable
                    and type(target_item) == type(drag_item)
                    and hasattr(target_item, "ammo_type")
                    and target_item.ammo_type == drag_item.ammo_type
                    and target_item.stack_count < target_item.max_stack):
                space = target_item.max_stack - target_item.stack_count
                take  = min(space, drag_item.stack_count)
                target_item.stack_count += take
                drag_item.stack_count   -= take
                if drag_item.stack_count <= 0:
                    self._grid_ui._drag = None
                else:
                    if source_grid:
                        source_grid.add(drag_item)
                    elif source_slot and source_slot.item is None:
                        source_slot.item = drag_item
                    self._grid_ui._drag = None
                if source_world:
                    result["kill_world_item"] = source_world
                return result

            if not slot.accepts(drag_item):
                continue

            old_item = slot.take()
            slot.put(drag_item)
            self._grid_ui._drag = None

            if old_item:
                if source_grid is not None:
                    if not source_grid.add(old_item):
                        result["drop_item"] = old_item
                else:
                    if not self.player.backpack.add(old_item):
                        result["drop_item"] = old_item

            if source_world:
                result["kill_world_item"] = source_world
            return result

        grid_result = self._grid_ui.handle_mouse_up(pos)
        result["kill_world_item"] = grid_result["kill_world_item"]
        result["drop_item"]       = grid_result["drop_item"]
        return result

    def handle_mouse_motion(self, pos: tuple) -> None:
        self.handle_info_panels_mouse_motion(pos)
        self._grid_ui.handle_mouse_motion(pos)
        self._tooltip_text = ""
        self._hovered_rect = None
        for slot, rect in self._pouch_interactive_rects():
            if rect.collidepoint(pos):
                self._hovered_rect = rect
                if not slot.empty:
                    self._tooltip_text = slot.item.get_tooltip()
        if not self._tooltip_text and self.backpack_open:
            self._tooltip_text = self._grid_ui.get_tooltip(pos)

    def handle_key_down(self, key: int) -> None:
        if self.backpack_open:
            self._grid_ui.handle_key_down(key)

    def try_use_hovered(self, player, pos: tuple) -> bool:
        if not self.backpack_open:
            return False
        slot, item = self._get_item_at(pos)
        if item is None:
            return False
        from items.consumable import Consumable, TimedConsumable

        def _remove():
            if slot is not None:
                slot.take()
            else:
                self.player.backpack.remove(item)

        if isinstance(item, TimedConsumable):
            started = player.start_timed_use(item, slot)
            if started and slot is None:
                self.player.backpack.remove(item)
            return started
        if isinstance(item, Consumable):
            item.use(player)
            _remove()
            return True
        return False
