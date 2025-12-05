import os
import time
import random
import json

import pygame
import numpy as np
import sounddevice as sd

# Basic init and configuration
pygame.init()
try:
    pygame.mixer.init()
except Exception:
    # mixer may fail on some systems; game still runs without sound
    pass

WIDTH, HEIGHT = 800, 500
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Noisy Bird - ~500 lines")

CLOCK = pygame.time.Clock()
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (34, 139, 34)
BLUE = (64, 224, 208)
YELLOW = (255, 215, 0)
GREY = (180, 180, 180)
RED = (220, 20, 60)

# Ensure folders
os.makedirs('images', exist_ok=True)
os.makedirs('sounds', exist_ok=True)
os.makedirs('score', exist_ok=True)

SETTINGS_PATH = os.path.join('score', 'settings.json')
HIGHSCORE_PATH = os.path.join('score', 'highscore.save')

DEFAULT_SETTINGS = {
    "volume": 0.6,
    "muted": False,
    "sensitivity": 1.0,
    "show_debug": False
}

# Utility functions
def load_image(path, size=None):
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.scale(img, size)
        return img
    except Exception:
        w, h = size if size else (40, 30)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((200, 0, 200, 255))
        return surf

def clamp(v, a, b):
    return max(a, min(b, v))

def load_settings():
    try:
        with open(SETTINGS_PATH, 'r') as f:
            s = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in s:
                    s[k] = v
            return s
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(s):
    try:
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(s, f)
    except Exception:
        pass

def load_highscore():
    try:
        with open(HIGHSCORE_PATH, 'r') as f:
            return int(f.read())
    except Exception:
        return 0

def save_highscore(val):
    try:
        with open(HIGHSCORE_PATH, 'w') as f:
            f.write(str(int(val)))
    except Exception:
        pass

# Game objects
class Bird:
    def __init__(self, x, y, settings):
        self.x = x
        self.y = y
        self.settings = settings
        self.image = load_image(os.path.join('images', 'bird.png'), size=(40, 30))
        self.w = self.image.get_width()
        self.h = self.image.get_height()
        self.vel_y = 0.0
        self.gravity = 0.5
        self.jump = 8.0
        self.max_fall = 12.0
        try:
            self.die_sound = pygame.mixer.Sound(os.path.join('sounds', 'die.mp3'))
        except Exception:
            self.die_sound = None

    def draw(self, surf):
        tilt = clamp(-self.vel_y * 4, -25, 45)
        img = pygame.transform.rotate(self.image, tilt)
        rect = img.get_rect(center=(int(self.x + self.w / 2), int(self.y + self.h / 2)))
        surf.blit(img, rect.topleft)

    def flap(self):
        self.vel_y = -self.jump

    def step(self):
        self.vel_y += self.gravity
        self.vel_y = clamp(self.vel_y, -self.max_fall, self.max_fall)
        self.y += self.vel_y

    def is_out(self):
        return self.y < -self.h or self.y > HEIGHT - self.h

    def play_die(self):
        if self.die_sound and not self.settings.get('muted', False):
            try:
                self.die_sound.set_volume(self.settings.get('volume', 0.6))
                self.die_sound.play()
            except Exception:
                pass

class Block:
    def __init__(self, x, w, top_h, gap):
        self.x = x
        self.w = w
        self.top_h = top_h
        self.gap = gap
        self.passed = False

    def draw(self, surf):
        pygame.draw.rect(surf, GREEN, (int(self.x), 0, self.w, int(self.top_h)))
        pygame.draw.rect(surf, GREEN, (int(self.x), int(self.top_h + self.gap), self.w, HEIGHT))

    def move(self, speed):
        self.x -= speed

    def off(self):
        return self.x + self.w < -10

    def collide(self, bird):
        bird_rect = pygame.Rect(int(bird.x), int(bird.y), bird.w, bird.h)
        top = pygame.Rect(int(self.x), 0, self.w, int(self.top_h))
        bottom = pygame.Rect(int(self.x), int(self.top_h + self.gap), self.w, HEIGHT - int(self.top_h + self.gap))
        return bird_rect.colliderect(top) or bird_rect.colliderect(bottom)

class PowerUp:
    TYPES = ('slow', 'double')
    def __init__(self, kind, x, y):
        self.kind = kind if kind in PowerUp.TYPES else 'slow'
        self.x = x
        self.y = y
        self.size = 26
        self.active = True
        self.rect = pygame.Rect(self.x, self.y, self.size, self.size)
    def draw(self, surf):
        if self.kind == 'double':
            pygame.draw.circle(surf, YELLOW, (int(self.x + self.size/2), int(self.y + self.size/2)), self.size//2)
        else:
            pygame.draw.rect(surf, BLUE, self.rect)
    def move(self, speed):
        self.x -= speed
        self.rect.topleft = (int(self.x), int(self.y))
        if self.x < -self.size:
            self.active = False
    def check(self, bird):
        if self.rect.colliderect(pygame.Rect(int(bird.x), int(bird.y), bird.w, bird.h)):
            self.active = False
            return True
        return False

# UI helper
def draw_text(surf, txt, size, x, y, color=WHITE):
    font = pygame.font.Font('freesansbold.ttf', size)
    surf.blit(font.render(txt, True, color), (x, y))

# Main game controller
class NoisyBird:
    _last_volume = 0.0
    def __init__(self):
        self.settings = load_settings()
        self.highscore = load_highscore()
        self.bird = Bird(150, 200, self.settings)
        self.score = 0
        self.blocks = []
        self.powerups = []
        self.block_speed = 3.0
        self.block_gap = self.bird.h * 4
        self.block_w = 60
        self.spawn_timer = 0.0
        self.spawn_interval = 1.8
        self.slow_until = 0.0
        self.double_until = 0.0
        self.stream = None
        self.paused = False
        self.show_fps = False
        try:
            self.point_sound = pygame.mixer.Sound(os.path.join('sounds', 'point.mp3'))
        except Exception:
            self.point_sound = None
        try:
            self.power_sound = pygame.mixer.Sound(os.path.join('sounds', 'power.wav'))
        except Exception:
            self.power_sound = None

    @staticmethod
    def audio_cb(indata, outdata, frames, time_info, status):
        try:
            vol = np.linalg.norm(indata) * 10.0
        except Exception:
            vol = 0.0
        NoisyBird._last_volume = vol

    def try_start_stream(self):
        try:
            self.stream = sd.InputStream(callback=NoisyBird.audio_cb)
            self.stream.start()
        except Exception:
            self.stream = None

    def stop_stream(self):
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
        except Exception:
            self.stream = None

    def spawn_block(self):
        top_h = random.randint(0, HEIGHT // 2)
        self.blocks.append(Block(WIDTH + 20, self.block_w, top_h, self.block_gap))

    def spawn_powerup(self):
        kind = random.choice(PowerUp.TYPES)
        x = WIDTH + 50
        y = random.randint(60, HEIGHT - 80)
        p = PowerUp(kind, x, y)
        self.powerups.append(p)
        if self.power_sound and not self.settings.get('muted', False):
            try:
                self.power_sound.set_volume(self.settings.get('volume', 0.6))
                self.power_sound.play()
            except Exception:
                pass

    def main_menu(self):
        sel = 0
        opts = ['Start', 'Instructions', 'Settings', 'Quit']
        while True:
            SCREEN.fill(BLUE)
            draw_text(SCREEN, "NOISY BIRD", 64, WIDTH//2 - 160, 40)
            for i, o in enumerate(opts):
                c = WHITE if i == sel else GREY
                draw_text(SCREEN, o, 32, WIDTH//2 - 80, 180 + i*60, c)
            draw_text(SCREEN, "UP/DOWN to move, ENTER to select", 18, 40, HEIGHT - 40)
            pygame.display.update()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_UP:
                        sel = (sel - 1) % len(opts)
                    elif ev.key == pygame.K_DOWN:
                        sel = (sel + 1) % len(opts)
                    elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if opts[sel] == 'Start':
                            return
                        if opts[sel] == 'Instructions':
                            self.instructions()
                        if opts[sel] == 'Settings':
                            self.settings_screen()
                        if opts[sel] == 'Quit':
                            pygame.quit(); exit()
            CLOCK.tick(30)

    def instructions(self):
        SCREEN.fill(BLUE)
        lines = [
            "Instructions:",
            "- Make noise into your mic to flap the bird.",
            "- Press SPACE to flap if mic is not available.",
            "- Avoid pipes; collect power-ups.",
            "- Press M to mute, P to pause, F to toggle FPS.",
            "",
            "Press any key to return."
        ]
        for i, l in enumerate(lines):
            draw_text(SCREEN, l, 20, 30, 50 + i*30)
        pygame.display.update()
        wait = True
        while wait:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    wait = False
            CLOCK.tick(30)

    def settings_screen(self):
        vol = self.settings.get('volume', 0.6)
        sens = self.settings.get('sensitivity', 1.0)
        muted = self.settings.get('muted', False)
        debug = self.settings.get('show_debug', False)
        sel = 0
        items = ['Volume', 'Sensitivity', 'Toggle Mute', 'Toggle Debug', 'Back']
        run = True
        while run:
            SCREEN.fill(BLUE)
            draw_text(SCREEN, "Settings", 40, WIDTH//2 - 60, 40)
            for i, it in enumerate(items):
                c = WHITE if i == sel else GREY
                draw_text(SCREEN, it, 26, 80, 130 + i*50, c)
                if it == 'Volume':
                    draw_text(SCREEN, f"{vol:.2f}", 22, 420, 130 + i*50)
                if it == 'Sensitivity':
                    draw_text(SCREEN, f"{sens:.2f}", 22, 420, 130 + i*50)
                if it == 'Toggle Mute':
                    draw_text(SCREEN, "ON" if muted else "OFF", 22, 420, 130 + i*50)
                if it == 'Toggle Debug':
                    draw_text(SCREEN, "ON" if debug else "OFF", 22, 420, 130 + i*50)
            draw_text(SCREEN, "Use arrows to change, ENTER to toggle, Back to save", 16, 40, HEIGHT - 40)
            pygame.display.update()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_UP:
                        sel = (sel - 1) % len(items)
                    elif ev.key == pygame.K_DOWN:
                        sel = (sel + 1) % len(items)
                    elif ev.key == pygame.K_LEFT:
                        if items[sel] == 'Volume':
                            vol = clamp(vol - 0.05, 0.0, 1.0)
                        if items[sel] == 'Sensitivity':
                            sens = clamp(sens - 0.1, 0.1, 5.0)
                    elif ev.key == pygame.K_RIGHT:
                        if items[sel] == 'Volume':
                            vol = clamp(vol + 0.05, 0.0, 1.0)
                        if items[sel] == 'Sensitivity':
                            sens = clamp(sens + 0.1, 0.1, 5.0)
                    elif ev.key == pygame.K_RETURN:
                        if items[sel] == 'Toggle Mute':
                            muted = not muted
                        elif items[sel] == 'Toggle Debug':
                            debug = not debug
                        elif items[sel] == 'Back':
                            run = False
            self.settings['volume'] = vol
            self.settings['sensitivity'] = sens
            self.settings['muted'] = muted
            self.settings['show_debug'] = debug
            save_settings(self.settings)
            CLOCK.tick(30)

    def play(self):
        self.bird = Bird(150, 200, self.settings)
        self.score = 0
        self.blocks = []
        self.powerups = []
        self.block_speed = 3.0
        self.spawn_timer = 0.0
        self.slow_until = 0.0
        self.double_until = 0.0
        self.paused = False
        self.show_fps = False
        self.try_start_stream()
        last = time.time()
        running = True
        while running:
            now = time.time()
            dt = now - last
            last = now
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False; break
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_SPACE:
                        self.bird.flap()
                    elif ev.key == pygame.K_m:
                        self.settings['muted'] = not self.settings.get('muted', False)
                        save_settings(self.settings)
                    elif ev.key == pygame.K_p:
                        self.paused = not self.paused
                    elif ev.key == pygame.K_f:
                        self.show_fps = not self.show_fps
                    elif ev.key == pygame.K_s:
                        self.settings_screen()
                    elif ev.key == pygame.K_ESCAPE:
                        running = False; break
            if not running:
                break
            if self.paused:
                draw_text(SCREEN, "PAUSED", 64, WIDTH//2 - 120, HEIGHT//2 - 40, YELLOW)
                draw_text(SCREEN, "Press P to resume", 22, WIDTH//2 - 110, HEIGHT//2 + 30)
                pygame.display.update()
                CLOCK.tick(12)
                continue
            SCREEN.fill(BLUE)
            volume = NoisyBird._last_volume
            if volume * self.settings.get('sensitivity', 1.0) > 1.0:
                self.bird.flap()
            self.bird.step()
            self.bird.draw(SCREEN)
            self.spawn_timer += dt
            if self.spawn_timer > self.spawn_interval:
                self.spawn_timer = 0
                self.spawn_block()
                if random.random() < 0.12:
                    self.spawn_powerup()
            speed = self.block_speed * (0.5 if time.time() < self.slow_until else 1.0)
            for block in list(self.blocks):
                block.move(speed)
                block.draw(SCREEN)
                if block.collide(self.bird):
                    self.bird.play_die()
                    running = False
                    break
                if not block.passed and block.x + block.w < self.bird.x:
                    block.passed = True
                    pts = 2 if time.time() < self.double_until else 1
                    self.score += pts
                    if self.point_sound and not self.settings.get('muted', False):
                        try:
                            self.point_sound.set_volume(self.settings.get('volume', 0.6))
                            self.point_sound.play()
                        except Exception:
                            pass
                if block.off():
                    try:
                        self.blocks.remove(block)
                    except Exception:
                        pass
            for pu in list(self.powerups):
                pu.move(speed)
                if pu.active:
                    pu.draw(SCREEN)
                    if pu.check(self.bird):
                        if pu.kind == 'slow':
                            self.slow_until = time.time() + 4.0
                        else:
                            self.double_until = time.time() + 5.0
                        if self.point_sound and not self.settings.get('muted', False):
                            try:
                                self.point_sound.set_volume(self.settings.get('volume', 0.6))
                                self.point_sound.play()
                            except Exception:
                                pass
                else:
                    try:
                        self.powerups.remove(pu)
                    except Exception:
                        pass
            draw_text(SCREEN, f"Score: {self.score}", 22, 8, 8)
            draw_text(SCREEN, f"High: {self.highscore}", 18, 8, 34)
            draw_text(SCREEN, "P:Pause  F:FPS  M:Mute  S:Settings", 14, WIDTH - 320, 8)
            if self.settings.get('show_debug', False) or self.show_fps:
                draw_text(SCREEN, f"Vol:{volume:.2f} Blocks:{len(self.blocks)}", 16, 8, HEIGHT - 22)
                if self.show_fps:
                    draw_text(SCREEN, f"FPS:{int(CLOCK.get_fps())}", 16, WIDTH - 90, HEIGHT - 22)
            if self.bird.is_out():
                self.bird.play_die()
                running = False
            pygame.display.update()
            CLOCK.tick(FPS)
        self.stop_stream()
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)
        self.game_over_screen()

    def game_over_screen(self):
        SCREEN.fill(BLUE)
        draw_text(SCREEN, "GAME OVER", 64, WIDTH//2 - 160, 80, RED)
        draw_text(SCREEN, f"Your Score: {self.score}", 32, WIDTH//2 - 120, 220)
        draw_text(SCREEN, "Press any key to return to menu", 20, WIDTH//2 - 160, 320)
        pygame.display.update()
        wait = True
        while wait:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    wait = False
            CLOCK.tick(30)

    def run(self):
        while True:
            self.main_menu()
            self.play()

# Entry point
def main():
    save_settings(load_settings())
    game = NoisyBird()
    game.run()

if __name__ == '__main__':
    main()