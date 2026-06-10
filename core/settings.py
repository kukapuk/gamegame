from dataclasses import dataclass


@dataclass
class Settings:
    # Window
    screen_width: int = 1280
    screen_height: int = 720
    title: str = "TopDown Shooter"
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