import pygame
from combat.calculator import resolve_hit
from core.settings import Settings


class CombatManager:
    """
    Управляет боевыми взаимодействиями:
    - пули игрока → враги
    - пули врагов → игрок
    - контактный урон врагов → игрок
    - пули → стены
    """

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def update(
        self,
        player,
        enemies: pygame.sprite.Group,
        bullets: pygame.sprite.Group,
        enemy_bullets: pygame.sprite.Group,
        walls: pygame.sprite.Group,
    ) -> None:
        self._check_bullet_hits(player, enemies, bullets)
        self._check_bullet_wall_hits(bullets, enemy_bullets, walls)
        self._check_contact_damage(player, enemies)
        self._check_enemy_bullet_hits(player, enemy_bullets)

    def _check_bullet_hits(self, player, enemies, bullets) -> None:
        active    = player.get_active_weapon()
        armor_pen = active.stats.armor_pen if active else 0
        hits      = pygame.sprite.groupcollide(enemies, bullets, False, True)
        for enemy, bullet_list in hits.items():
            for bullet in bullet_list:
                damage, se = resolve_hit(
                    base_damage=bullet.damage,
                    base_se=bullet.stopping_effect,
                    armor_pen=armor_pen,
                    armor_class=enemy.armor_class,
                    settings=self.s,
                )
                enemy.take_damage(damage)
                if se > 0 and bullet.velocity.length() > 0:
                    enemy.apply_stopping_effect(bullet.velocity, se)

    def _check_bullet_wall_hits(self, bullets, enemy_bullets, walls) -> None:
        pygame.sprite.groupcollide(bullets,       walls, True, False)
        pygame.sprite.groupcollide(enemy_bullets, walls, True, False)

    def _check_contact_damage(self, player, enemies) -> None:
        armor_class = player.get_armor_class()
        for enemy in enemies:
            damage, _ = resolve_hit(
                base_damage=self.s.enemy_contact_damage,
                base_se=0.0,
                armor_pen=0,
                armor_class=armor_class,
                settings=self.s,
            )
            enemy.try_deal_contact_damage(player, damage, self.s.enemy_contact_cooldown)

    def _check_enemy_bullet_hits(self, player, enemy_bullets) -> None:
        armor_class = player.get_armor_class()
        for bullet in enemy_bullets:
            if player.rect.colliderect(bullet.rect):
                damage, _ = resolve_hit(
                    base_damage=bullet.damage,
                    base_se=0.0,
                    armor_pen=0,
                    armor_class=armor_class,
                    settings=self.s,
                )
                player.take_damage(damage)
                bullet.kill()
