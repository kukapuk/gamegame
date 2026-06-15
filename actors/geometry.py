"""
geometry.py — вспомогательные функции для ray/segment пересечений.
"""
import pygame


def segment_intersects_rect(p1, p2, rect) -> bool:
    edges = [
        ((rect.left, rect.top),    (rect.right, rect.top)),
        ((rect.right, rect.top),   (rect.right, rect.bottom)),
        ((rect.right, rect.bottom),(rect.left,  rect.bottom)),
        ((rect.left,  rect.bottom),(rect.left,  rect.top)),
    ]
    for a, b in edges:
        if segments_intersect(p1, p2, pygame.math.Vector2(a), pygame.math.Vector2(b)):
            return True
    return False


def segments_intersect(p1, p2, p3, p4) -> bool:
    d1    = p2 - p1
    d2    = p4 - p3
    cross = d1.x * d2.y - d1.y * d2.x
    if abs(cross) < 1e-10:
        return False
    d3 = p3 - p1
    t  = (d3.x * d2.y - d3.y * d2.x) / cross
    u  = (d3.x * d1.y - d3.y * d1.x) / cross
    return 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0


def ray_rect_hit_point(origin, end, rect):
    edges = [
        ((rect.left, rect.top),    (rect.right, rect.top)),
        ((rect.right, rect.top),   (rect.right, rect.bottom)),
        ((rect.right, rect.bottom),(rect.left,  rect.bottom)),
        ((rect.left,  rect.bottom),(rect.left,  rect.top)),
    ]
    closest_t = float("inf")
    closest   = None
    d1 = end - origin
    for a, b in edges:
        p3 = pygame.math.Vector2(a)
        p4 = pygame.math.Vector2(b)
        d2    = p4 - p3
        cross = d1.x * d2.y - d1.y * d2.x
        if abs(cross) < 1e-10:
            continue
        d3 = p3 - origin
        t  = (d3.x * d2.y - d3.y * d2.x) / cross
        u  = (d3.x * d1.y - d3.y * d1.x) / cross
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0 and t < closest_t:
            closest_t = t
            closest   = origin + d1 * t
    return closest
