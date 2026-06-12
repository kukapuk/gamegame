import random
import pygame
from combat.calculator import resolve_hit, HitZone
from core.settings import Settings


def _armor_protects_limbs(player) -> bool:
    """Возвращает True если экипированная броня защищает конечности."""
    from items.armor import Armor
    from items.item import ItemType
    armor_slots = [s for s in player.pouch.typed_slots if s.allowed_type == ItemType.ARMOR]
    if armor_slots and not armor_slots[0].empty:
        item = armor_slots[0].item
        if isinstance(item, Armor):
            return item.protects_limbs
    return False


class CombatManager:
    """
    Боевые взаимодействия: пули <-> акторы, контакт, стены.
    Использует head_rect/body_rect для определения зоны попадания.
    """

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def update(
        self,
        player,
        enemies:       pygame.sprite.Group,
        bullets:       pygame.sprite.Group,
        enemy_bullets: pygame.sprite.Group,
        walls:         pygame.sprite.Group,
    ) -> None:
        self._check_bullet_hits(player, enemies, bullets)
        self._check_bullet_wall_hits(bullets, enemy_bullets, walls)
        self._check_contact_damage(player, enemies)
        self._check_enemy_bullet_hits(player, enemy_bullets)

    def _check_bullet_hits(self, player, enemies, bullets) -> None:
        active    = player.get_active_weapon()
        armor_pen = active.stats.armor_pen if active else 0

        hits = pygame.sprite.groupcollide(enemies, bullets, False, True)
        for enemy, bullet_list in hits.items():
            for bullet in bullet_list:
                hit_head = enemy.head_rect.colliderect(bullet.rect)
                result   = resolve_hit(
                    base_damage     = bullet.damage,
                    base_se         = bullet.stopping_effect,
                    armor_pen       = armor_pen,
                    armor_class     = enemy.armor_class,
                    hit_head_hitbox = hit_head,
                    settings        = self.s,
                )
                enemy.take_damage(result.damage)
                enemy.last_hit_zone = result.zone
                enemy.take_hit_from_direction(bullet.velocity)
                if result.stopping_effect > 0 and bullet.velocity.length() > 0:
                    enemy.apply_stopping_effect(bullet.velocity, result.stopping_effect)

    def _check_bullet_wall_hits(self, bullets, enemy_bullets, walls) -> None:
        pygame.sprite.groupcollide(enemy_bullets, walls, True, False)

        normal_bullets   = [b for b in bullets if not b.can_ricochet or b.ricocheted]
        ricochet_bullets = [b for b in bullets if b.can_ricochet and not b.ricocheted]

        for bullet in normal_bullets:
            if pygame.sprite.spritecollide(bullet, walls, False):
                bullet.kill()

        for bullet in ricochet_bullets:
            hit_walls = pygame.sprite.spritecollide(bullet, walls, False)
            if hit_walls:
                if not bullet.do_ricochet(hit_walls[0].rect):
                    bullet.kill()

    def _check_contact_damage(self, player, enemies) -> None:
        armor_class = player.get_armor_class()
        for enemy in enemies:
            result = resolve_hit(
                base_damage     = self.s.enemy_contact_damage,
                base_se         = 0.0,
                armor_pen       = 0,
                armor_class     = armor_class,
                hit_head_hitbox = False,
                settings        = self.s,
            )
            enemy.try_deal_contact_damage(player, result.damage,
                                          self.s.enemy_contact_cooldown)

    def _check_enemy_bullet_hits(self, player, enemy_bullets) -> None:
        armor_class = player.get_armor_class()
        for bullet in list(enemy_bullets):
            hit_head = player.head_rect.colliderect(bullet.rect)
            hit_body = player.body_rect.colliderect(bullet.rect)
            if not hit_head and not hit_body:
                continue
            result = resolve_hit(
                base_damage     = bullet.damage,
                base_se         = 0.0,
                armor_pen       = 0,
                armor_class     = armor_class,
                hit_head_hitbox = hit_head,
                settings        = self.s,
            )
            player.take_damage(result.damage)
            player.last_hit_zone = result.zone

            if result.penetrated:
                if result.zone == HitZone.ARMS:
                    # дебафф конечностей только если броня не защищает их
                    if not _armor_protects_limbs(player):
                        player.apply_arms_debuff()
                elif result.zone == HitZone.LEGS:
                    if not _armor_protects_limbs(player):
                        player.apply_legs_debuff()

                bleed_chance = {
                    HitZone.TORSO: 0.20,
                    HitZone.ARMS:  0.40,
                    HitZone.LEGS:  0.40,
                }.get(result.zone, 0.0)
                if bleed_chance > 0 and random.random() < bleed_chance:
                    player.apply_bleeding()

            bullet.kill()
