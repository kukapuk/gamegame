from dataclasses import dataclass, field
import pygame


@dataclass
class Settings:
    # Window
    screen_width: int = 1280
    screen_height: int = 720
    title: str = "gamegame"
    fps: int = 60

    # Player
    player_speed: float = 250.0
    player_size: int = 32
    player_color: tuple = (80, 140, 255)

    # World
    bg_color: tuple = (18, 20, 26)
    grid_color: tuple = (25, 28, 36)
    grid_size: int = 64

    # Weapon
    weapon_width: int = 20
    weapon_height: int = 8
    weapon_offset: int = 20
    weapon_color: tuple = (220, 180, 80)

    # Bullet
    bullet_speed: float = 600.0
    bullet_size: int = 6
    bullet_color: tuple = (255, 240, 100)
    bullet_lifetime: float = 2.0
    bullet_damage: int = 10
    fire_rate: float = 0.15

    # Enemy
    enemy_hp_bar_width: int = 32
    enemy_hp_bar_height: int = 4
    enemy_hp_bar_color: tuple = (220, 50, 50)
    enemy_hp_bar_bg: tuple = (60, 20, 20)
    enemy_contact_damage: int = 15
    enemy_contact_cooldown: float = 0.5

    # Player HUD
    player_hp_bar_width: int = 200
    player_hp_bar_height: int = 16
    player_hp_bar_color: tuple = (60, 200, 90)
    player_hp_bar_bg: tuple = (40, 40, 40)
    player_hp_bar_margin: int = 20

    # Inventory
    backpack_hold_time: float = 1.0
    pouch_hotkeys: tuple = (pygame.K_z, pygame.K_x, pygame.K_c, pygame.K_v)

    # Armor penetration
    armor_partial_chance: float = 0.5
    armor_damage_gap1: float    = 0.5
    armor_damage_gap2: float    = 0.35
    armor_damage_gap3: float    = 0.2
    armor_pen_se_mult: float    = 0.1

    # Sound
    gunshot_sound_radius: float = 400.0

    # Footsteps
    step_radius_walk:   float = 120.0
    step_radius_sprint: float = 180.0
    step_radius_dash:   float = 240.0
    step_radius_crouch: float = 35.0    # очень тихо
    step_interval_walk: float = 0.4
    step_interval_sprint: float = 0.2
    step_interval_crouch: float = 0.6   # медленнее шаги
    crouch_speed_mult:  float = 0.8
