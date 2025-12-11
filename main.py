import os
import time
import random
import json
import pygame
import numpy as np
import sounddevice as sd

pygame.init()
try:
    pygame.mixer.init()
except Exception:
    pass

WIDTH, HEIGHT = 800, 500
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Noisy Bird - Reduced")
CLOCK = pygame.time.Clock()
FPS = 60

WHITE = (255, 255, 255)
BLUE = (64, 224, 208)
GREEN = (34, 139, 34)
YELLOW = (255, 215, 0)
RED = (220, 20, 60)
GREY = (180, 180, 180)

os.makedirs('images', exist_ok=True)
os.makedirs('sounds', exist_ok=True)
os.makedirs('score', exist_ok=True)
SETTINGS_PATH = os.path.join('score', 'settings.json')
HIGHSCORE_PATH = os.path.join('score', 'highscore.save')

# Reduced noise sensitivity by default:
DEFAULT_SETTINGS = {
    "volume": 0.6,
    "muted": False,
    "sensitivity": 0.6,   # lower = less sensitive to mic noise
    "mic_threshold": 0.07  # higher = less sensitive to mic noise
}

def load_settings():
    try:
        with open(SETTINGS_PATH, 'r') as f:
            s = json.load(f)
    except Exception:
        s = {}
    for k, v in DEFAULT_SETTINGS.items():
        s.setdefault(k, v)
    return s

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

def save_highscore(value):
    try:
        with open(HIGHSCORE_PATH, 'w') as f:
            f.write(str(int(value)))
    except Exception:
        pass

def draw_text(surf, text, size, x, y, color=WHITE):
    font = pygame.font.Font('freesansbold.ttf', size)
    surf.blit(font.render(text, True, color), (x, y))

def clamp(value, low, high):
    return max(low, min(value, high))

def load_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except Exception:
        return None

class Bird:
    def __init__(self, x, y, settings):
        self.x = x
        self.y = y
        self.settings = settings
        self.image = pygame.Surface((40, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (255, 200, 0), (0, 0, 40, 30))
        self.w, self.h = self.image.get_size()
        self.vel_y = 0.0

        # ===== Updated movement parameters: slower fall, stronger flap =====
        # Recommended values for slower descent:
        self.gravity = 0.32        # reduced from 0.5 -> falls more slowly
        self.jump_strength = 9.0   # increased from 8.0 -> flaps feel stronger/longer
        self.max_fall = 7.0        # reduced from 12.0 -> limits terminal velocity

        self.die_sound = load_sound(os.path.join('sounds', 'die.mp3'))

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

    def is_out(self):
        return self.y < -self.h or self.y > HEIGHT - self.h

    def play_die(self):
        if self.die_sound and not self.settings.get('muted'):
            try:
                self.die_sound.set_volume(self.settings.get('volume', 0.6))
                self.die_sound.play()
            except Exception:
                pass

class Block:
    def __init__(self, x, width, top_height, gap):
        self.x = x
        self.w = width
        self.top_h = top_height
        self.gap = gap
        self.passed = False

    def draw(self, surf):
        pygame.draw.rect(surf, GREEN, (int(self.x), 0, self.w, int(self.top_h)))
        pygame.draw.rect(surf, GREEN, (int(self.x), int(self.top_h + self.gap), self.w, HEIGHT))

    def move(self, speed):
        self.x -= speed

    def off_screen(self):
        return self.x + self.w < -10

    def collide_with(self, bird):
        brect = pygame.Rect(int(bird.x), int(bird.y), bird.w, bird.h)
        top = pygame.Rect(int(self.x), 0, self.w, int(self.top_h))
        bottom = pygame.Rect(int(self.x), int(self.top_h + self.gap), self.w, HEIGHT - int(self.top_h + self.gap))
        return brect.colliderect(top) or brect.colliderect(bottom)

class PowerUp:
    TYPES = ('slow', 'double')

    def __init__(self, kind, x, y):
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

    def move(self, speed):
        self.x -= speed
        if self.x < -self.size:
            self.active = False

    def collides(self, bird):
        rect = pygame.Rect(int(self.x), int(self.y), self.size, self.size)
        return rect.colliderect(pygame.Rect(int(bird.x), int(bird.y), bird.w, bird.h))

class NoisyBirdGame:
    _last_volume = 0.0

    def __init__(self):
        self.settings = load_settings()
        self.highscore = load_highscore()
        self.bird = Bird(150, 200, self.settings)
        self.score = 0
        self.blocks = []
        self.powerups = []
        self.block_speed = 3.0

        # Keep larger vertical gap and spacing tweaks
        self.block_gap = int(self.bird.h * 5)  # larger vertical gap
        self.block_w = 70  # pipe width
        self.spawn_timer = 0.0
        self.spawn_interval = 2.6  # increased spawn interval => more horizontal spacing

        self.slow_until = 0.0
        self.double_until = 0.0
        self.stream = None
        self.point_sound = load_sound(os.path.join('sounds', 'point.mp3'))
        self.power_sound = load_sound(os.path.join('sounds', 'power.wav'))
        # mic threshold comes from settings (default reduced sensitivity)
        self.mic_threshold = self.settings.get('mic_threshold', DEFAULT_SETTINGS['mic_threshold'])
        self._volume_history = []  # small smoothing buffer

    @staticmethod
    def audio_cb(indata, frames, time_info, status):
        if status:
            print("Audio status:", status)
        try:
            rms = float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))
        except Exception as e:
            print("audio_cb error:", e)
            rms = 0.0
        NoisyBirdGame._last_volume = rms

    def start_mic(self):
        try:
            try:
                dev_info = sd.query_devices(kind='input')
                samplerate = int(dev_info['default_samplerate'])
            except Exception:
                samplerate = 44100
            self.stream = sd.InputStream(callback=NoisyBirdGame.audio_cb,
                                         channels=1,
                                         samplerate=samplerate,
                                         blocksize=1024,
                                         dtype='float32')
            self.stream.start()
            print("Microphone stream started (samplerate:", samplerate, ")")
        except Exception as e:
            print("Failed to start microphone stream:", e)
            self.stream = None

    def stop_mic(self):
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
        except Exception as e:
            print("Error stopping microphone:", e)
            self.stream = None

    def spawn_block(self):
        top_h = random.randint(0, HEIGHT // 2)
        self.blocks.append(Block(WIDTH + 80, self.block_w, top_h, self.block_gap))

    def spawn_powerup(self):
        kind = random.choice(PowerUp.TYPES)
        x = WIDTH + 120
        y = random.randint(60, HEIGHT - 80)
        self.powerups.append(PowerUp(kind, x, y))
        if self.power_sound and not self.settings.get('muted'):
            try:
                self.power_sound.set_volume(self.settings.get('volume', 0.6))
                self.power_sound.play()
            except Exception:
                pass

    def play(self):
        self.bird = Bird(150, 200, self.settings)
        self.score = 0
        self.blocks = []
        self.powerups = []
        self.block_speed = 3.0
        self.spawn_timer = 0.0
        self.slow_until = 0.0
        self.double_until = 0.0
        paused = False

        self.start_mic()
        last_time = time.time()
        running = True

        while running:
            now = time.time()
            dt = now - last_time
            last_time = now

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_SPACE:
                        self.bird.flap()
                    elif ev.key == pygame.K_m:
                        self.settings['muted'] = not self.settings.get('muted')
                        save_settings(self.settings)
                    elif ev.key == pygame.K_p:
                        paused = not paused
                    elif ev.key == pygame.K_ESCAPE:
                        running = False

            if paused:
                SCREEN.fill(BLUE)
                draw_text(SCREEN, 'PAUSED', 64, WIDTH//2 - 120, HEIGHT//2 - 40, YELLOW)
                draw_text(SCREEN, 'Press P to resume', 22, WIDTH//2 - 110, HEIGHT//2 + 30)
                pygame.display.update()
                CLOCK.tick(12)
                continue

            SCREEN.fill(BLUE)

            # use RMS volume measured by audio_cb
            volume = NoisyBirdGame._last_volume

            # small smoothing for stable readout
            self._volume_history.append(volume)
            if len(self._volume_history) > 6:
                self._volume_history.pop(0)
            smooth_vol = sum(self._volume_history) / len(self._volume_history)

            # If exceeded threshold (tunable), flap
            if smooth_vol * self.settings.get('sensitivity', DEFAULT_SETTINGS['sensitivity']) > self.mic_threshold:
                self.bird.flap()

            # Draw bird & HUD
            self.bird.update()
            self.bird.draw(SCREEN)

            # show debug audio level on screen and current sensitivity
            draw_text(SCREEN, f"Mic RMS: {smooth_vol:.4f}", 18, WIDTH - 220, HEIGHT - 30, GREY)
            draw_text(SCREEN, f"Thresh: {self.mic_threshold:.3f}", 14, WIDTH - 220, HEIGHT - 50, GREY)
            draw_text(SCREEN, f"Sensitivity: {self.settings.get('sensitivity', DEFAULT_SETTINGS['sensitivity']):.2f}", 14, WIDTH - 220, HEIGHT - 70, GREY)

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
                if block.collide_with(self.bird):
                    self.bird.play_die()
                    running = False
                    break
                if not block.passed and block.x + block.w < self.bird.x:
                    block.passed = True
                    pts = 2 if time.time() < self.double_until else 1
                    self.score += pts
                    if self.point_sound and not self.settings.get('muted'):
                        try:
                            self.point_sound.set_volume(self.settings.get('volume', 0.6))
                            self.point_sound.play()
                        except Exception:
                            pass
                if block.off_screen():
                    try:
                        self.blocks.remove(block)
                    except Exception:
                        pass

            for pu in list(self.powerups):
                pu.move(speed)
                if pu.active:
                    pu.draw(SCREEN)
                    if pu.collides(self.bird):
                        pu.active = False
                        if pu.kind == 'slow':
                            self.slow_until = time.time() + 4.0
                        else:
                            self.double_until = time.time() + 5.0
                        if self.point_sound and not self.settings.get('muted'):
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
            draw_text(SCREEN, "P:Pause  M:Mute  Esc:Quit", 14, WIDTH - 260, 8)

            if self.bird.is_out():
                self.bird.play_die()
                running = False

            pygame.display.update()
            CLOCK.tick(FPS)

        self.stop_mic()
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)
        self.game_over_screen()

    def game_over_screen(self):
        SCREEN.fill(BLUE)
        draw_text(SCREEN, 'GAME OVER', 64, WIDTH//2 - 160, 80, RED)
        draw_text(SCREEN, f'Your Score: {self.score}', 32, WIDTH//2 - 120, 220)
        draw_text(SCREEN, 'Press any key to return to menu', 20, WIDTH//2 - 160, 320)
        pygame.display.update()
        waiting = True
        while waiting:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    waiting = False
            CLOCK.tick(30)

    def run(self):
        while True:
            SCREEN.fill(BLUE)
            draw_text(SCREEN, 'NOISY BIRD', 64, WIDTH//2 - 160, 40)
            draw_text(SCREEN, 'Press SPACE or make noise to start, ESC to quit', 20, WIDTH//2 - 260, 140)
            draw_text(SCREEN, f'Highscore: {self.highscore}', 22, WIDTH//2 - 120, 220)
            draw_text(SCREEN, f"Sensitivity: {self.settings.get('sensitivity', DEFAULT_SETTINGS['sensitivity']):.2f}", 18, WIDTH//2 - 120, 260)
            pygame.display.update()
            started = False
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        pygame.quit(); exit()
                    else:
                        started = True
            if NoisyBirdGame._last_volume * self.settings.get('sensitivity', DEFAULT_SETTINGS['sensitivity']) > self.mic_threshold:
                started = True
            if started:
                self.play()
            CLOCK.tick(15)

def main():
    save_settings(load_settings())
    game = NoisyBirdGame()
    game.run()

if __name__ == '__main__':
    main()