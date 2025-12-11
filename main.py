import time
import random
import os
import pygame
from settings import load_settings, save_settings, load_highscore, save_highscore, draw_text, BLUE, GREY, RED
from entities import Bird, Block, PowerUp, load_sound_safe
from audio import MicReader, VolumeSmoother

pygame.init()
try:
    pygame.mixer.init()
except Exception:
    pass

WIDTH, HEIGHT = 800, 500
FPS = 60
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Noisy Bird - Mic Only")
CLOCK = pygame.time.Clock()

class NoisyBirdGame:
    def __init__(self, screen, clock, fps, width, height):
        self.SCREEN = screen
        self.CLOCK = clock
        self.FPS = fps
        self.WIDTH = width
        self.HEIGHT = height
        self.settings = load_settings()
        self.highscore = load_highscore()
        self.bird = Bird(150, 200, self.settings)
        self.score = 0
        self.blocks = []
        self.powerups = []
        self.block_speed = 3.0
        self.block_gap = int(self.bird.h * 5)
        self.block_w = 70
        self.spawn_timer = 0.0
        self.spawn_interval = 2.6
        self.slow_until = 0.0
        self.double_until = 0.0
        self.mic = MicReader()
        self.point_sound = load_sound_safe(os.path.join('sounds', 'point.mp3'))
        self.power_sound = load_sound_safe(os.path.join('sounds', 'power.wav'))
        self.mic_threshold = self.settings.get('mic_threshold', 0.07)
        self.smoother = VolumeSmoother()

    def start_mic(self):
        self.mic.start()

    def stop_mic(self):
        self.mic.stop()

    def spawn_block(self):
        top_h = random.randint(0, self.HEIGHT // 2)
        self.blocks.append(Block(self.WIDTH + 80, self.block_w, top_h, self.block_gap))

    def spawn_powerup(self):
        kind = random.choice(PowerUp.TYPES)
        x = self.WIDTH + 120
        y = random.randint(60, self.HEIGHT - 80)
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
                    if ev.key == pygame.K_m:
                        self.settings['muted'] = not self.settings.get('muted')
                        save_settings(self.settings)
                    elif ev.key == pygame.K_p:
                        paused = not paused
                    elif ev.key == pygame.K_ESCAPE:
                        running = False
            if paused:
                self.SCREEN.fill(BLUE)
                draw_text(self.SCREEN, 'PAUSED', 64, self.WIDTH//2 - 120, self.HEIGHT//2 - 40, (255, 215, 0))
                draw_text(self.SCREEN, 'Press P to resume', 22, self.WIDTH//2 - 110, self.HEIGHT//2 + 30)
                pygame.display.update()
                self.CLOCK.tick(12)
                continue
            self.SCREEN.fill(BLUE)
            volume = self.mic.get_volume()
            self.smoother.add(volume)
            smooth_vol = self.smoother.smooth()
            if smooth_vol * self.settings.get('sensitivity', 0.6) > self.mic_threshold:
                self.bird.flap()
            self.bird.update()
            self.bird.draw(self.SCREEN)
            draw_text(self.SCREEN, f"Mic RMS: {smooth_vol:.4f}", 18, self.WIDTH - 220, self.HEIGHT - 30, GREY)
            draw_text(self.SCREEN, f"Thresh: {self.mic_threshold:.3f}", 14, self.WIDTH - 220, self.HEIGHT - 50, GREY)
            draw_text(self.SCREEN, f"Sensitivity: {self.settings.get('sensitivity', 0.6):.2f}", 14, self.WIDTH - 220, self.HEIGHT - 70, GREY)
            self.spawn_timer += dt
            if self.spawn_timer > self.spawn_interval:
                self.spawn_timer = 0
                self.spawn_block()
                if random.random() < 0.12:
                    self.spawn_powerup()
            speed = self.block_speed * (0.5 if time.time() < self.slow_until else 1.0)
            for block in list(self.blocks):
                block.move(speed)
                block.draw(self.SCREEN, self.HEIGHT)
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
                    pu.draw(self.SCREEN)
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
            draw_text(self.SCREEN, f"Score: {self.score}", 22, 8, 8)
            draw_text(self.SCREEN, f"High: {self.highscore}", 18, 8, 34)
            draw_text(self.SCREEN, "P:Pause  M:Mute  Esc:Quit", 14, self.WIDTH - 260, 8)
            if self.bird.is_out(self.HEIGHT):
                self.bird.play_die()
                running = False
            pygame.display.update()
            self.CLOCK.tick(self.FPS)
        self.stop_mic()
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)
        self.game_over_screen()

    def game_over_screen(self):
        self.SCREEN.fill(BLUE)
        draw_text(self.SCREEN, 'GAME OVER', 64, self.WIDTH//2 - 160, 80, RED)
        draw_text(self.SCREEN, f'Your Score: {self.score}', 32, self.WIDTH//2 - 120, 220)
        draw_text(self.SCREEN, 'Press any key to return to menu', 20, self.WIDTH//2 - 160, 320)
        pygame.display.update()
        waiting = True
        while waiting:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); exit()
                if ev.type == pygame.KEYDOWN:
                    waiting = False
            self.CLOCK.tick(30)

    def run_menu(self):
        while True:
            self.SCREEN.fill(BLUE)
            draw_text(self.SCREEN, 'NOISY BIRD', 64, self.WIDTH//2 - 160, 40)
            draw_text(self.SCREEN, 'Press SPACE to start, ESC to quit', 20, self.WIDTH//2 - 180, 140)
            draw_text(self.SCREEN, f'Highscore: {self.highscore}', 22, self.WIDTH//2 - 120, 220)
            draw_text(self.SCREEN, f"Sensitivity: {self.settings.get('sensitivity', 0.6):.2f}",
                18, self.WIDTH//2 - 120, 260)
            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        pygame.quit()
                        exit()
                    if ev.key == pygame.K_SPACE:
                        self.play()
    
            self.CLOCK.tick(15)


def main():
    save_settings(load_settings())
    game = NoisyBirdGame(screen=SCREEN, clock=CLOCK, fps=FPS, width=WIDTH, height=HEIGHT)
    game.run_menu()

if __name__ == '__main__':
    main()