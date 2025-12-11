import os
import pygame
from typing import Optional
from settings import clamp, load_sound_safe, GREEN, YELLOW, BLUE

class Bird:
    def __init__(self, x: int, y: int, settings: dict):
        self.x = x
        self.y = y
        self.settings = settings
        self.image = pygame.Surface((40, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (255, 200, 0), (0, 0, 40, 30))
        self.w, self.h = self.image.get_size()
        self.vel_y = 0.0
        self.gravity = 0.32
        self.jump_strength = 9.0
        self.max_fall = 7.0
        self.die_sound = load_sound_safe(os.path.join('sounds', 'die.mp3'))

    def draw(self, surf):
        angle = clamp(-self.vel_y * 4, -25, 45)
        rotated = pygame.transform.rotate(self.image, angle)
        rect = rotated.get_rect(center=(int(self.x + self.w/2), int(self.y + self.h/2)))
        surf.blit(rotated, rect.topleft)

    def flap(self):
        self.vel_y = -self.jump_strength

    def update(self):
        self.vel_y += self.gravity
        self.vel_y = clamp(self.vel_y, -self.max_fall, self.max_fall)
        self.y += self.vel_y

    def is_out(self, screen_height: int) -> bool:
        return self.y < -self.h or self.y > screen_height - self.h

    def play_die(self):
        if self.die_sound and not self.settings.get('muted'):
            try:
                self.die_sound.set_volume(self.settings.get('volume', 0.6))
                self.die_sound.play()
            except Exception:
                pass

class Block:
    def __init__(self, x: int, width: int, top_height: int, gap: int):
        self.x = x
        self.w = width
        self.top_h = top_height
        self.gap = gap
        self.passed = False

    def draw(self, surf, screen_height: int):
        pygame.draw.rect(surf, GREEN, (int(self.x), 0, self.w, int(self.top_h)))
        pygame.draw.rect(surf, GREEN, (int(self.x), int(self.top_h + self.gap), self.w, screen_height - int(self.top_h + self.gap)))

    def move(self, speed: float):
        self.x -= speed

    def off_screen(self) -> bool:
        return self.x + self.w < -10

    def collide_with(self, bird: Bird) -> bool:
        brect = pygame.Rect(int(bird.x), int(bird.y), bird.w, bird.h)
        top = pygame.Rect(int(self.x), 0, self.w, int(self.top_h))
        bottom = pygame.Rect(int(self.x), int(self.top_h + self.gap), self.w, int(1e6))
        return brect.colliderect(top) or brect.colliderect(bottom)

class PowerUp:
    TYPES = ('slow', 'double')

    def __init__(self, kind: str, x: int, y: int):
        self.kind = kind if kind in PowerUp.TYPES else 'slow'
        self.x = x
        self.y = y
        self.size = 26
        self.active = True

    def draw(self, surf):
        if self.kind == 'double':
            pygame.draw.circle(surf, YELLOW, (int(self.x + self.size/2), int(self.y + self.size/2)), self.size//2)
        else:
            pygame.draw.rect(surf, BLUE, (int(self.x), int(self.y), self.size, self.size))

    def move(self, speed: float):
        self.x -= speed
        if self.x < -self.size:
            self.active = False

    def collides(self, bird: Bird) -> bool:
        rect = pygame.Rect(int(self.x), int(self.y), self.size, self.size)
        return rect.colliderect(pygame.Rect(int(bird.x), int(bird.y), bird.w, bird.h))
#kaviya