from dataclasses import dataclass


@dataclass
class Settings:
    # Window
    screen_width: int = 1280
    screen_height: int = 720
    title: str = "gamegame"
    fps: int = 60

    player_speed: float = 250.0
    player_size: int = 32
    player_color: tuple = (80, 140, 255)

    bg_color: tuple = (18, 20, 26)
    grid_color: tuple = (25, 28, 36)
    grid_size: int = 64