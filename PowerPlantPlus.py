#---------INITIAL SETUP
import pygame
import pygame.surfarray
import sys
import os
#import PowerPlantBattle
from collections import Counter
#import psutil
import copy
import time
import gc
import random
import math
import asyncio
import numpy as np
import pandas as pd

gc.set_debug(gc.DEBUG_STATS)

from pygame.locals import (
    K_UP,
    K_DOWN,
    K_LEFT,
    K_RIGHT,
    K_RETURN,
    K_TAB,
    KEYDOWN,
    KEYUP,
    QUIT,
)

pygame.init()

# Set up display
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
scale_factor = 5

screen = pygame.display.set_mode([SCREEN_WIDTH * scale_factor, SCREEN_HEIGHT * scale_factor])
pygame.display.set_caption("PowerPlant")

if getattr(sys, 'frozen', False):  # If running as a packaged executable
    PATH_START = sys._MEIPASS  # Temporary folder PyInstaller uses
else:
    PATH_START = os.path.dirname(__file__)  # Script folder

IMAGES_DICT = {}

def load_images_from_folder(base_path, folder_names, target_dict):
    for folder in folder_names:
        folder_path = os.path.join(base_path, folder)
        if not os.path.isdir(folder_path):
            continue  # skip if folder doesn't exist

        folder_key = os.path.basename(folder_path)
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                image_key = f"{folder_key}_{file}"
                target_dict[image_key] = pygame.image.load(file_path).convert_alpha()

# Usage
folders_to_load = [
    "BattleTerrain", "Fonts", "FullSprites", "Objects",
    "Plants", "Player", "Tiles", "UI"
]

load_images_from_folder(PATH_START, folders_to_load, IMAGES_DICT)

#---------BATTLE CLASSES AND FUNCTIONS
class Power:
    def __init__(self, name, short_name, desc, type, power, accuracy=100, priority=0, additionalEffect=None):
        self.name = name
        self.short_name = short_name
        self.desc = desc
        self.type = type
        self.power = power
        self.accuracy = accuracy
        self.priority = priority
        self.additionalEffect = additionalEffect
        self.hasAdditionalEffect = additionalEffect is not None

class Plant_Species:
    def __init__(self, name, base_hp, base_attack, base_defense, base_special_attack, base_special_defense, base_speed, money_dropped=None):
        self.name = name
        self.base_hp = base_hp
        self.base_attack = base_attack
        self.base_defense = base_defense
        self.base_special_attack = base_special_attack
        self.base_special_defense = base_special_defense
        self.base_speed = base_speed
        self.money_dropped = money_dropped

class Specific_Plant:
    def __init__(self, species, hp_ev, attack_ev, defense_ev, special_attack_ev, special_defense_ev, speed_ev, attacks, status=None, accuracy_stage=0, evasion_stage=0):#, ability_number):
        self.species_name = species.name
        self.base_hp = species.base_hp
        self.base_attack = species.base_attack
        self.base_defense = species.base_defense
        self.base_special_attack = species.base_special_attack
        self.base_special_defense = species.base_special_defense
        self.base_speed = species.base_speed
        self.status = status
        self.accuracy_stage = 0
        self.evasion_stage = 0
        self.ev_hp = hp_ev
        self.ev_attack = attack_ev
        self.ev_defense = defense_ev
        self.ev_special_attack = special_attack_ev
        self.ev_special_defense = special_defense_ev
        self.ev_speed = speed_ev
        self.attacks = attacks
        self.money_dropped = species.money_dropped
        self.calculate_stats()

    def calculate_stats(self):
        self.max_hp = math.floor((((2 * self.base_hp + 31 + (self.ev_hp//4)) * 5)//100)) + 5 + 10
        self.attack = math.floor(((((2 * self.base_attack + 31 + (self.ev_attack//4)) * 5)//100) + 5))
        self.defense = math.floor(((((2 * self.base_defense + 31 + (self.ev_defense//4)) * 5)//100) + 5)) 
        self.special_attack = math.floor(((((2 * self.base_special_attack + 31 + (self.ev_special_attack//4)) * 5)//100) + 5))
        self.special_defense = math.floor(((((2 * self.base_special_defense + 31 + (self.ev_special_defense//4)) * 5)//100) + 5))
        self.speed = math.floor(((((2 * self.base_speed + 31 + (self.ev_speed//4)) * 5)//100) + 5))
        self.current_hp = self.max_hp
        self.effective_speed = self.speed

    def take_damage(self, damage):
        self.current_hp -= damage
        if self.current_hp < 0:
            self.current_hp = 0

    def is_fainted(self):
        return self.current_hp == 0
    
    def update_status(self, new_status):
        if self.status != None:
            return(False)
        else:
            if new_status == 'Paralysis':
                self.status = new_status
                self.effective_speed = int(self.effective_speed * .25)

def calculate_damage(user, attack, opponent):
    damage = (2 * 5)
    damage = damage//5
    damage = damage + 2
    damage = damage * attack.power
    if attack.type == 'Special':
            ad = user.special_attack/opponent.special_defense
    else:
            ad = user.attack/opponent.defense
    damage = damage * ad
    damage = damage//50
    damage = damage + 2
    damage = int(damage * random.uniform(0.85, 1.0))
    return damage


def getStageModifierAccuracyOrEvasion(stage):
    modifiers = [33, 36, 43, 50, 60, 75, 100, 133, 166, 200, 250, 266, 300]
    return modifiers[stage + 6]

def checkAccuracy(user, target, attack):
    #print('')
    accuracy_move = attack.accuracy
    adjusted_stages = getStageModifierAccuracyOrEvasion(user.accuracy_stage - target.evasion_stage)
    accuracy_modified = int(accuracy_move * (adjusted_stages / 100))
    random_number = random.randint(1, 100)
    if random_number <= accuracy_modified:
        return True
    else:
        return False
    #Modifiers need abilities and items to be relevant

def useAttack(user, target, attack):
    #print('')
    accuracyCheck = checkAccuracy(user, target, attack)
    if accuracyCheck:
        #print('')
        damage = calculate_damage(user, attack, target)
        if damage != 0:
            target.take_damage(damage)
            #print(f"{user.species_name} used {attack.name} against {target.species_name} for {damage} damage.")
            if attack.hasAdditionalEffect:
                attack.additionalEffect(user, target)
            return [user, target, attack, damage, True]
    else:
        #print(f"Foe {user.species_name}'s {attack.name} missed!") #Fix this to be correct for the player
        damage = 0
        return [user, target, attack, damage, False]

def movePhase(curr_player_plant, curr_opponent, opponent_attack, player_attack):
    #Assumptions: Player always attacks since there is no shifting, set order
    #No status conditions yet
    #No stat changes mid battle yet but ready
    #No accuracy checks yet but ready
    #No priority yet but ready
    #print('Starting move phase Dec 30')
    things_to_return = []
    if player_attack.priority > opponent_attack.priority:
        playerGoFirst = True
    elif player_attack.priority < opponent_attack.priority:
        playerGoFirst = False
    else:
        if curr_player_plant.effective_speed > curr_opponent.effective_speed:
            playerGoFirst = True
        elif curr_player_plant.effective_speed < curr_opponent.effective_speed:
            playerGoFirst = False
        else:
            playerGoFirst = random.choice([True, False])
    if playerGoFirst:
        things_to_return.append(useAttack(curr_player_plant, curr_opponent, player_attack))
        if not curr_opponent.is_fainted():
            things_to_return.append(useAttack(curr_opponent, curr_player_plant, opponent_attack))
    else:
        things_to_return.append(useAttack(curr_opponent, curr_player_plant, opponent_attack))
        if not curr_player_plant.is_fainted():
            things_to_return.append(useAttack(curr_player_plant, curr_opponent, player_attack))
    things_to_return.append(['FINAL', curr_player_plant, curr_opponent])
    return things_to_return


#def get_memory_usage():
#    process = psutil.Process(os.getpid())  # Get the current process
#    memory_info = process.memory_info()   # Get memory info
#    mb_used = memory_info.rss / (1024 * 1024)  # Convert bytes to MB
#    print(f"RAM Usage: {mb_used:.2f} MB")

#These will get added to either the individual sprite class or combined into their own class later
#---------SOUND EFFECTS
def select_sound():
    if not sfx_channel.get_busy():
        # Play the sound
        sfx_channel.play(sound_effect_select)

def damage_sound():
    # Play the sound
    sfx_channel.play(sound_effect_hit)

def cancel_sound():
    # Play the sound
    sfx_channel.play(sound_effect_cancel)

def buy_sound():
    # Play the sound
    sfx_channel.play(sound_effect_buy)

def faint_sound():
    sfx_channel.play(sound_effect_faint)

#---------INDIVIDUAL SPRITE SET UP
class Regular_Font_Letter(pygame.sprite.Sprite):
    def __init__(self, letter, topright_input, recolor=True):
        super().__init__()
        self.letter = letter
        if letter == 'DownArrow':
            full_image = IMAGES_DICT["Fonts_down_arrow.png"]
            self.topright_input = topright_input
            self.curr_frame = 0
            self.animate_buffer = 0
            
            self.frame_1 = full_image.subsurface((0, 0, 8, 16))
            self.frame_2 = full_image.subsurface((0, 16, 8, 16))
            self.frame_3 = full_image.subsurface((0, 32, 8, 16))
            self.frames = [self.frame_1, self.frame_2, self.frame_3, self.frame_2]

            self.surf = pygame.Surface((8, 16), pygame.SRCALPHA)
            self.surf.blit(self.frame_3, (0, 0))

        else:
            full_image = IMAGES_DICT["Fonts_monogram-bitmap_white.png"] if recolor else IMAGES_DICT["Fonts_monogram-bitmap.png"]
            self.topright_input = topright_input
            self.recolor = recolor
            char_map = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'
            custom_chars = {'elipses': (90, 60), 'selection': (24, 72)}
            if letter in custom_chars:
                x, y = custom_chars[letter]
            elif letter in char_map:
                index = char_map.index(letter)
                x = (index % 16) * 6
                y = (index // 16) * 12  # 11 height + 1 line padding assumed
            else:
                print(f"Character '{letter}' not supported in font map.")

            self.surf = full_image.subsurface(pygame.Rect(x, y, 6, 11))
        self.rect = self.surf.get_rect()
        self.rect.topright = (400, 400)  # initial placeholder position
        self.width = self.rect.width
        self.height = self.rect.height
        self.surface_to_return = self.surf

    def reveal(self):
        self.rect.topright = self.topright_input

    def hide(self):
        self.rect.topright = (400, 400)

    def animate_arrow(self):
        if self.curr_frame > 3:
            self.curr_frame = 0
        if self.animate_buffer == 16:
            frame_to_select = self.frames[self.curr_frame]
            self.surf = pygame.Surface((8, 16), pygame.SRCALPHA)
            self.surf.blit(frame_to_select, (0, 0))
            self.rect = self.surf.get_rect()
            self.rect.topright = self.topright_input
            self.curr_frame = self.curr_frame + 1
            self.animate_buffer = 0
        else:
            self.animate_buffer += 1


class Individual_Sprite(pygame.sprite.Sprite):
    def __init__(self, image_key, subsurface_rect, start_pos, uses_alpha=False, gen_image=False, 
                 level=None, dirt=None, tile_number=None, player=False, tile_row=None, tile_column=None, opponent_sprite=False, player_sprite=False, plant_species = None,
                 status_bar=None):
        super().__init__()
        #self.image_key = image_key good for debug don't use otherwise
        if gen_image:
            square_width, square_height = 240, 160
            self.surf = pygame.Surface((square_width, square_height), pygame.SRCALPHA)  # Use SRCALPHA for transparency
            self.surf.fill((0, 0, 0, 255))  # Fill with black color
        elif status_bar:
            self.full_hp = status_bar[0]
            self.curr_hp = status_bar[1]
            self.plant_name = status_bar[2]
            self.hero_or_opponent = status_bar[4]
            self.hero_or_opponent_width = 32 if self.hero_or_opponent == "Hero" else 29
            self.full_image = IMAGES_DICT[f"UI_{self.hero_or_opponent}_Status_Bar.png"]
            self.very_temp_surf = self.full_image.subsurface((0, 0, 100, self.hero_or_opponent_width))
            self.temp_surf = pygame.Surface((100, self.hero_or_opponent_width))
            self.temp_surf.blit(self.very_temp_surf, (0, 0))
            self._render_text(self.plant_name, 7, 4, self.temp_surf)
            self.surf = pygame.Surface((100, 32))
            self.surf.blit(self.temp_surf, (0, 0))
            self._update_hp_bar()
            if self.hero_or_opponent == "Hero":
                self._render_hp_text()
            self.updating_hp = False
            self.hp_bar_units = 48
            self.updating_hp_frame = 0
            self.hp_frames_left = None
            self.hp_to_lose_each_frame = None
        else:
            if level == None:
                self.full_image = IMAGES_DICT[image_key]
            else:
                temp_image_key = image_key + f"{level}.png"
                self.full_image = IMAGES_DICT[temp_image_key]
                
                self.image_key = image_key
            if subsurface_rect != None:
                self.subsurface_rect = subsurface_rect
                self.surf = self.full_image.subsurface(subsurface_rect)
            else:
                self.surf = self.full_image
        self.rect = self.surf.get_rect()
        self.start_pos_type = start_pos[0]
        if self.start_pos_type == 'tr':
            self.rect.topright = start_pos[1]
        elif self.start_pos_type == 'tl':
            self.rect.topleft = start_pos[1]
        elif self.start_pos_type == 'bl':
            self.rect.bottomleft = start_pos[1]
        if uses_alpha:
            self.surf.set_alpha(0)
            self.surf.get_alpha()
            self.faded_in = False
            self.faded_out = False
        if dirt:
            self.dirt = dirt
            self.has_plant = False
            self.plant = None
            self.specific_plant_object = None
        if tile_number is not None:
            self.tile_number = tile_number
        if player:
            self.moving_time_limit = 0
            self.moving = False
            self.direction = 'Forward'
            self.new_direction = None
            self.moving_frame = 0
            self.tile_row = tile_row
            self.tile_column = tile_column
            self.interacting = False
            self.intereaction_tile = None
            self.entry_delay = 0
            self.interaction_tile_row = None
            self.interaction_tile_column = None
        if opponent_sprite:
            self.taking_damage_frame = 0
            self.taking_damage = False
            self.fainting = False
            self.player = False
        if player_sprite:
            self.image_key = image_key
            self.original_image = IMAGES_DICT[image_key]
            self.spawned = False
            self.scale_factor = 1.05
            self.small_scale_factor_list = [.4, .5, .6, .7, .8, .9, 1]
            self.curr_small_scale_factor_list_position = 0
            self.full_size = False
            self.fade_duration = 60  # Adjust the duration of the fade (in frames)
            self.fade_counter = 0
            self.fading = False
            self.original_colors = None  # Will store the original colors of each pixel
            self.recolor_key = self.get_recolor_key()
            self.waiting_down = False
            self.waiting_down_frame = 0
            self.taking_damage_frame = 0
            self.taking_damage = False
            self.entered_battle = False
            self.fainting = False
            self.player = True
        if plant_species:
            self.plant_species = plant_species
            self.curr_frame = 0
            self.grown = False
            global species_objects
            global attack_objects
            if plant_species == 'Rose':
                self.plant_species_object = species_objects['rose_species']
                self.starting_attack = attack_objects['romantic_power']
            if plant_species == 'Blue Tulip':
                self.plant_species_object = species_objects['blue_tulip_species']
                self.starting_attack = attack_objects['mysterious_power']
            if plant_species == 'Sunflower':
                self.plant_species_object = species_objects['sunflower_species']
                self.starting_attack = attack_objects['solar_power']
            else:
                print('invalid species')

    def move_horizontal(self, move_speed, stopping_point):
        if self.rect.topright != stopping_point:
            self.rect.move_ip(move_speed, 0)

    def take_damage(self):
        if self.taking_damage:
            if self.taking_damage_frame <= 60:
                blink_ranges = [(8, 15), (23, 30), (38, 45), (53, 60)]
                if any(start <= self.taking_damage_frame < end for start, end in blink_ranges):
                    self.rect.topright = (500, 500)
                else:
                    if self.player:
                        self.rect.topright = (106, 56)
                    else:
                        self.rect.topright = (208, 12)
                self.taking_damage_frame += 1
            else:
                self.taking_damage_frame = 0
                self.taking_damage = False

    def faint(self):
        if self.fainting:
            if self.player:
                if self.rect.topright != (106, 144):
                    self.move_vertical(move_speed=2, stopping_point=(106, 144))
                else:
                    self.fainting = False
            else:
                if self.rect.topright != (208, 100):
                    self.move_vertical(move_speed=2, stopping_point=(208, 100))
                else:
                    self.fainting = False

    def move_vertical(self, move_speed, stopping_point):
        if self.rect.topright != stopping_point:
            self.rect.move_ip(0, move_speed)

    def change_position(self, new_top_left):
        self.rect.topleft = new_top_left

    def fade_in(self, fade_fast=False):
        curr_alpha = self.surf.get_alpha()
        if curr_alpha == None:
            curr_alpha = 255
        if curr_alpha != 255:
            if fade_fast:
                curr_alpha += 2
            curr_alpha += 3
            self.surf.set_alpha(curr_alpha)
        else:
            self.faded_in = True

    def fade_out(self):
        curr_alpha = self.surf.get_alpha()
        if curr_alpha == None:
            curr_alpha = 255
        if curr_alpha != 0:
            curr_alpha -= 5
            self.surf.set_alpha(curr_alpha)
        else:
            self.faded_out = True

    def handle_screen_fades(self, fade_fast=False):
        if self.faded_in == False:
            self.fade_in(fade_fast)
        else:
            if self.faded_out == False:
                self.fade_out()

    def change_level(self, new_level):
        self.level = new_level
        temp_image_key = self.image_key + f"{self.level}.png"
        self.full_image = IMAGES_DICT[temp_image_key]
        self.surf = self.full_image.subsurface(self.subsurface_rect)

    def change_dirt(self, new_dirt):
        self.dirt = new_dirt.replace(" Dirt", "")
        self.full_image = IMAGES_DICT[f"Objects_Planter_{self.dirt}.png"]
        self.surf = self.full_image.subsurface((0,0,16,24))

    def change_tile(self, new_tile_number):
        self.tile_number = new_tile_number
        self.full_image = IMAGES_DICT[f"Tiles_{new_tile_number}.png"]
        self.surf = self.full_image.subsurface((0,0,16,16))

    def player_moving_animation(self):
        if self.moving:
            if self.moving_frame == 0:
                self.full_image = IMAGES_DICT[f"Player_{self.new_direction}1.png"]
                self.surf = self.full_image.subsurface((0,0,16,24))
            if self.moving_frame == 8:
                self.full_image = IMAGES_DICT[f"Player_{self.new_direction}2.png"]
                self.surf = self.full_image.subsurface((0,0,16,24))
            if self.moving_frame == 15:
                self.moving = False
                self.direction = self.new_direction
                self.new_direction = None
                self.full_image = IMAGES_DICT[f"Player_{self.direction}.png"]
                self.surf = self.full_image.subsurface((0,0,16,24))
            else:
                self.moving_frame += 1

    def player_move(self, pressed_keys):
        if self.moving == False and self.interacting == False:
            if pressed_keys != None:
                if pressed_keys[K_UP]:
                    self.new_direction = 'Backward'
                    next_row = self.tile_row - 1
                    next_column = self.tile_column
                elif pressed_keys[K_DOWN]:
                    self.new_direction = 'Forward'
                    next_row = self.tile_row + 1
                    next_column = self.tile_column
                elif pressed_keys[K_LEFT]:
                    self.new_direction = 'Left'
                    next_row = self.tile_row
                    next_column = self.tile_column -1
                elif pressed_keys[K_RIGHT]:
                    self.new_direction = 'Right'
                    next_row = self.tile_row
                    next_column = self.tile_column + 1
                elif pressed_keys[K_RETURN] and self.entry_delay == 0:
                    if self.direction == 'Backward':
                        next_row = self.tile_row - 1
                        next_column = self.tile_column
                    elif self.direction == 'Forward':
                        next_row = self.tile_row + 1
                        next_column = self.tile_column
                    elif self.direction == 'Left':
                        next_row = self.tile_row
                        next_column = self.tile_column -1
                    elif self.direction == 'Right':
                        next_row = self.tile_row
                        next_column = self.tile_column +1
                    next_row_str = f'row{next_row}'
                    next_tile = collison_map[next_row_str][next_column]
                    if next_tile in [8, 80, 13, 14]:
                        self.interacting = True
                        self.intereaction_tile = next_tile
                        self.interaction_tile_row = next_row
                        self.interaction_tile_column = next_column
                if self.new_direction != None:
                    next_row_str = f'row{next_row}'
                    next_tile = collison_map[next_row_str][next_column]
                    if next_tile == 0 or next_tile == 2:
                        self.moving = True
                        self.moving_frame = 0
                        self.tile_row = next_row
                        self.tile_column = next_column
                    else:
                        if self.direction != self.new_direction:
                            self.full_image = IMAGES_DICT[f"Player_{self.new_direction}.png"]
                            self.surf = self.full_image.subsurface((0,0,16,24))
                            self.direction = self.new_direction
                        self.new_direction = None
        if self.entry_delay != 0:
            self.entry_delay -= 1
    
    def get_recolor_key(self):
        # Convert surface to a 3D NumPy array (RGB only)
        arr = np.array(pygame.surfarray.pixels3d(self.surf))
        flat_pixels = arr.reshape(-1, 3)
        most_common = Counter(map(tuple, flat_pixels)).most_common(1)
        return most_common[0][0] if most_common else None

    def recolor_all_to_one(self, new_color):
        arr = pygame.surfarray.pixels_alpha(self.surf)
        rgb_arr = pygame.surfarray.pixels3d(self.surf)
        # Create a mask where color ≠ recolor_key (excluding alpha)
        key_rgb = np.array(self.recolor_key[:3])
        mask = ~(np.all(rgb_arr == key_rgb, axis=2))
        # Create a new surface and fill with transparent pixels
        new_surf = pygame.Surface(self.surf.get_size(), pygame.SRCALPHA)
        new_arr = pygame.surfarray.pixels3d(new_surf)
        new_alpha = pygame.surfarray.pixels_alpha(new_surf)
        # Apply new color to non-key pixels
        for i in range(3):
            new_arr[:, :, i][mask] = new_color[i]
        new_alpha[:, :][mask] = arr[mask]
        # Release surface locks
        del arr, rgb_arr, new_arr, new_alpha
        self.surf = new_surf

    def recolor(self, new_colors):
        new_surf = pygame.Surface((self.surf.get_width(), self.surf.get_height()), pygame.SRCALPHA)

        for x in range(self.surf.get_width()):
            for y in range(self.surf.get_height()):
                pixel_color = self.surf.get_at((x, y))
                if pixel_color != (57, 164, 164, 255):  # Check if pixel is not transparent
                    new_color = new_colors[x][y] + (pixel_color[3],)
                    new_surf.set_at((x, y), new_color)

        self.surf = new_surf

    def recolor(self, new_colors):
        width, height = self.surf.get_size()
        # Access pixel data
        orig_rgb = pygame.surfarray.pixels3d(self.surf)
        orig_alpha = pygame.surfarray.pixels_alpha(self.surf)
        # Convert new_colors (list of RGB tuples) to NumPy array
        new_rgb = np.array(new_colors, dtype=np.uint8)
        # Create new surface
        new_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        target_rgb = pygame.surfarray.pixels3d(new_surf)
        target_alpha = pygame.surfarray.pixels_alpha(new_surf)
        # Mask to exclude the transparent key color
        key_color = np.array([57, 164, 164])
        mask = ~(np.all(orig_rgb == key_color, axis=2))
        # Apply new RGB and preserve original alpha
        target_rgb[mask] = new_rgb[mask]
        target_alpha[mask] = orig_alpha[mask]
        # Release surface locks
        del orig_rgb, orig_alpha, target_rgb, target_alpha
        self.surf = new_surf
    
    def fade_to_original(self):
        if self.original_colors is None:
            # Store original colors as a 2D list [x][y] like your original code
            self.original_colors = [
                [self.original_image.get_at((x, y))[:3] for y in range(self.original_image.get_height())]
                for x in range(self.original_image.get_width())
            ]
        ratio = self.fade_counter / self.fade_duration
        width = self.original_image.get_width()
        height = self.original_image.get_height()
        # Blend each pixel, preserving [x][y] layout
        blended_colors = [
            [
                tuple(
                    int((1 - ratio) * base + ratio * orig)
                    for base, orig in zip((255, 180, 255), self.original_colors[x][y])
                )
                for y in range(height)
            ]
            for x in range(width)
        ]
        self.recolor(blended_colors)
        self.fade_counter += 1
        if self.fade_counter >= self.fade_duration:
            self.fading = False
            self.fade_counter = 0
            self.original_colors = None

    def spawn(self):
        # Set initial position
        self.rect.topright = (106, 56)
        # Scale the surface using the small scale factor
        scale_factor = self.small_scale_factor_list[0]
        new_size = (
            int(self.rect.width * scale_factor),
            int(self.rect.height * scale_factor)
        )
        self.surf = pygame.transform.scale(self.surf, new_size)
        # Update rect to match new surface size, preserving previous center
        self.rect = self.surf.get_rect(center=self.rect.center)
        # Mark as spawned and recolor
        self.spawned = True
        self.recolor_all_to_one((255, 180, 255))
        # Adjust final position: bottomleft aligned horizontally to center 64px area
        new_x = 44 + ((64 - self.rect.width) / 2)
        self.rect.bottomleft = (new_x, 120)

    def grow_to_full_size(self):
        self.curr_small_scale_factor_list_position += 1
        # Clamp index to avoid IndexError
        if self.curr_small_scale_factor_list_position >= len(self.small_scale_factor_list):
            self.curr_small_scale_factor_list_position = len(self.small_scale_factor_list) - 1
        scale = self.small_scale_factor_list[self.curr_small_scale_factor_list_position]
        # Start with base subsurface
        base_surf = self.full_image.subsurface((0, 0, 64, 64))
        scaled_size = (int(base_surf.get_width() * scale), int(base_surf.get_height() * scale))
        self.surf = pygame.transform.scale(base_surf, scaled_size)
        # Re-align the rect to keep bottom center consistent
        self.rect = self.surf.get_rect()
        new_x = 44 + ((64 - self.rect.width) / 2)
        self.rect.bottomleft = (new_x, 120)
        # Check if scaling is complete
        if scale == 1:
            self.full_size = True
            self.fading = True
            self.rect.topright = (106, 56)
        self.recolor_all_to_one((255, 180, 255))

    def battle_entrance_animation(self):
        if self.spawned == False:
            self.spawn()
        elif self.full_size == False:
            self.grow_to_full_size()
        if self.fading:
            self.fade_to_original()
        if self.full_size and not self.fading and not self.entered_battle:
            temp_surf = IMAGES_DICT[self.image_key]
            self.surf = temp_surf.subsurface((0,0,64,64))
            self.entered_battle = True

    def waiting(self):
        if self.waiting_down_frame == 10:
            self.waiting_down = not self.waiting_down
            self.rect.topright = (106, 57 if self.waiting_down else 56)
            self.waiting_down_frame = 0
        else:
            self.waiting_down_frame += 1

    def grow_plant(self):
        if self.curr_frame in (9, 19):
            temp_bottom_left = self.rect.bottomleft
            stage = 1 if self.curr_frame == 9 else 2
            self.full_image = IMAGES_DICT[f"Plants_{self.plant_species}{stage}.png"]
            self.surf = self.full_image
            self.rect = self.surf.get_rect()
            self.rect.bottomleft = temp_bottom_left
            if self.curr_frame == 19:
                self.grown = True

        if self.curr_frame < 19:
            self.curr_frame += 1

    def set_hp_update_params(self, new_hp):
        temp_difference = self.curr_hp - new_hp
        ratio = temp_difference / self.curr_hp if self.curr_hp else 1

        if ratio < 0.25:
            self.hp_frames_left = 24
        elif ratio < 0.5:
            self.hp_frames_left = 36
        elif ratio < 0.75:
            self.hp_frames_left = 48
        else:
            self.hp_frames_left = 60

        self.hp_to_lose_each_frame = round(temp_difference / self.hp_frames_left, 2)

    def new_update_hp_bar(self, new_hp):
        self.surf = pygame.Surface((100, self.hero_or_opponent_width))
        self.surf.blit(self.temp_surf, (0, 0))

        self.curr_hp = max(int(self.curr_hp - self.hp_to_lose_each_frame), new_hp)
        self._update_hp_bar()

        self.hp_frames_left -= 1
        if self.hp_frames_left == 0 or self.curr_hp <= new_hp:
            self.curr_hp = new_hp
            self.hp_frames_left = None
            self.updating_hp = False

    def _update_hp_bar(self):
        hp_48ths = (self.curr_hp * 48) // self.full_hp
        color = (0, 255, 0) if hp_48ths >= 24 else (255, 255, 0) if hp_48ths >= 12 else (255, 0, 0)
        hp_color = pygame.Surface((1, 2))
        hp_color.fill(color)
        hp_color = hp_color.convert()

        for x in range(39, 39 + hp_48ths):
            self.surf.blit(hp_color, (x, 17))

    def _render_hp_text(self):
        hp_text = f"{self.curr_hp}/{self.full_hp}"
        self._render_text(hp_text, 60, 19, self.surf)

    def _render_text(self, text, x_start, y_start, target_surf):
        x = x_start
        for char in text:
            char_sprite = Regular_Font_Letter(char, (x, y_start))
            target_surf.blit(char_sprite.surface_to_return, (x, y_start))
            x += char_sprite.surface_to_return.get_width()

    def change_hp(self, new_hp=None):
        if self.updating_hp:
            if new_hp != self.curr_hp:
                if self.hp_frames_left is None:
                    self.set_hp_update_params(new_hp)
            if self.hp_frames_left is not None:
                self.new_update_hp_bar(new_hp)
            if self.hero_or_opponent == "Hero":
                self._render_hp_text()

#---------INDIVIDUAL SPRITES
class Opponent_Status_Bar(Individual_Sprite):
    def __init__(self, plant_name, level, full_hp, curr_hp):
        super().__init__(
            image_key=None,
            start_pos=['tr', (-64, 16)],
            subsurface_rect=None,
            status_bar=[full_hp, curr_hp, plant_name, level, "Opponent"]
        )

class Hero_Status_Bar(Individual_Sprite):
    def __init__(self, plant_name, level, full_hp, curr_hp):
        super().__init__(
            image_key=None,
            start_pos=['tl', (304, 82)],
            subsurface_rect=None,
            status_bar=[full_hp, curr_hp, plant_name, level, "Hero"]
        )

class Plant_Overworld_Sprite(Individual_Sprite):
    def __init__(self, bottom_left, plant_species):
        super().__init__(
            image_key=f"Plants_{plant_species}.png",
            start_pos=['bl', bottom_left],
            subsurface_rect=None,
            plant_species=plant_species
        )
    
class Opponent_Sprite(Individual_Sprite):
    def __init__(self, sprite_name):
        super().__init__(
            image_key=f"FullSprites_{sprite_name}_front.png",
            subsurface_rect=(0,0,64,64),
            start_pos=['tr', (-96, 12)],
            opponent_sprite=True
        )

class Player_Plant_Sprite(Individual_Sprite):
    def __init__(self, sprite_name):
        super().__init__(
            image_key=f"FullSprites_{sprite_name}_back.png",
            subsurface_rect=(0,0,64,64),
            start_pos=['tr', (400, 400)],
            player_sprite=True
        )  

class Player_Overworld_Sprite(Individual_Sprite):
    def __init__(self, bottom_left, tile_row, tile_column):
        super().__init__(
            image_key="Player_Forward.png",
            subsurface_rect=(0,0,16,24),
            start_pos=['bl', bottom_left],
            player=True,
            tile_row=tile_row,
            tile_column=tile_column
        )

class Hero_Platform(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="BattleTerrain_Hero_Platform.png",
            subsurface_rect=(0, 0, 128, 13),
            start_pos=['tr', (432, 104)]
        )

class Enemy_Platform(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="BattleTerrain_Enemy_Platform.png",
            subsurface_rect=(0, 0, 128, 32),
            start_pos=['tr', (-64, 52)]
        )

class Select_Move_Box(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="UI_SelectMoveBox.png",
            subsurface_rect=(0,0,240,43),
            start_pos=['tl', (0, 117)]
        )

class Overworld_Main_Text_box(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="UI_Textbox.png",
            subsurface_rect=(0,0,240,43),
            start_pos=['tl', (0, 117)]
        )

class Overworld_Three_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_ThreeOptionBox.png",
            subsurface_rect=(0,0,56,56),
            start_pos=['tl', top_left]
        )

class Overworld_Four_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_FourOptionBox.png",
            subsurface_rect=(0,0,56,72),
            start_pos=['tl', top_left]
        )

class Front_Sprite(Individual_Sprite):
    def __init__(self, top_left, plant_species):
        super().__init__(
            image_key=f"FullSprites_{plant_species}_front.png",
            subsurface_rect=(0,0,64,64),
            start_pos=['tl', top_left]
        )

class Battle_Background(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"BattleTerrain_BattleBackground.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)]
        )

class Faint_Fixer(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"BattleTerrain_FaintFixer.png",
            subsurface_rect=(0,0,113,3),
            start_pos=['tl', (127,114)]
        )

class Move_Bar_Highlight(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"UI_Selection_Highlight.png",
            subsurface_rect=(0,0,166,28),
            start_pos=['tl', top_left]
        )

class Dusk_Background(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"UI_DuskBG.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)]
        )

class Dusk_Transition_Screen(Individual_Sprite):
    def __init__(self):
        global day
        super().__init__(
            image_key=f"UI_Dusk{day}.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)],
            uses_alpha=True
        )
        
class Night_Transition_Screen(Individual_Sprite):
     def __init__(self):
        global day
        super().__init__(
            image_key=f"UI_Night{day}.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)],
            uses_alpha=True
        )

class Day_Transition_Screen(Individual_Sprite):
    def __init__(self):
        global day
        super().__init__(
            image_key=f"UI_Day{day + 1}.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)],
            uses_alpha=True
        )

class Game_Over_Screen(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"UI_GameOver.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)],
            uses_alpha=True
        )

class Title_Screen(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"UI_TitleScreen.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0,0)]
        )

class Black_Rectangle(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=None,
            subsurface_rect=None,
            start_pos=['tl', (0,0)],
            uses_alpha=True,
            gen_image=True
        )

class Computer(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"Objects_Computer.png",
            subsurface_rect=(0,0,16,16),
            start_pos=['tl', top_left]
        )

class Irrigation_Top(Individual_Sprite):
    def __init__(self, top_left, level):
        super().__init__(
            image_key=f"Objects_Irrigation_Top_",
            subsurface_rect=(0,0,144,32),
            start_pos=['tl', top_left],
            level=level
        )

class Irrigation_Bottom(Individual_Sprite):
    def __init__(self, top_left, level):
        super().__init__(
            image_key=f"Objects_Irrigation_Bottom_",
            subsurface_rect=(0,0,144,16),
            start_pos=['tl', top_left],
            level=level
        )

class Generator_Left(Individual_Sprite):
    def __init__(self, top_left, level):
        super().__init__(
            image_key=f"Objects_Generator_Left_",
            subsurface_rect=(0,0,16,16),
            start_pos=['tl', top_left],
            level=level
        )

class Generator_Right(Individual_Sprite):
    def __init__(self, top_left, level):
        super().__init__(
            image_key=f"Objects_Generator_Right_",
            subsurface_rect=(0,0,16,16),
            start_pos=['tl', top_left],
            level=level
        )

class Generator_Bottom(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"Objects_Generator_Bottom.png",
            subsurface_rect=(0,0,112,16),
            start_pos=['tl', top_left]
        )


class Planter(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"Objects_Planter.png",
            subsurface_rect=(0,0,16,24),
            start_pos=['tl', top_left],
            dirt = 'regular'
        )

class Overworld_Wide_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_WideOptionBox.png",
            subsurface_rect=(0,0,104,117),
            start_pos=['tl', top_left]
        )

class Overworld_Two_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_TwoOptionBox.png",
            subsurface_rect=(0,0,56,40),
            start_pos=['tl', top_left]
        )

class Overworld_One_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_OneOptionBox.png",
            subsurface_rect=(0,0,56,28),
            start_pos=['tl', top_left]
        )

class Battle_Time_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_TimeBox.png",
            subsurface_rect=(0,0,60,16),
            start_pos=['tl', top_left]
        )

class Overworld_Status_Screen_Box(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="UI_Status.png",
            subsurface_rect=(0,0,240,160),
            start_pos=['tl', (0, 0)]
        )

class Tile(Individual_Sprite):
    def __init__(self, top_left, tile_number):
        super().__init__(
            image_key=f"Tiles_{tile_number}.png",
            subsurface_rect=(0,0,16,16),
            start_pos=['tl', top_left],
            tile_number = tile_number
        )

#---------SPRITE GROUPS
#All menus consist of:
#Option box of some size
#Big text bog at bottom
#Bottom text
#Sometimes additional option boxes


class Overworld_Menu(pygame.sprite.Group):
    def __init__(self, input_string, text_type, options=None, use_buy_sound=False, money_box=False, store_box=False, quantity_box=False):
        super(Overworld_Menu, self).__init__()
        if options:
            self.option_box = Overworld_Option_Box(top_left=(0,0), options=options, use_buy_sound=use_buy_sound)
            self.add(self.option_box)
        else:
            self.option_box = None
        self.main_text_box = Overworld_Main_Text_box()
        self.curr_text = Regular_Font_Line(input_string=input_string, text_type=text_type)
        self.add(self.main_text_box)
        self.add(self.curr_text)
        if money_box:
            self.create_money_box()
        if store_box:
            self.create_store_box()
        if quantity_box:
            self.create_quantity_box()

    def update_curr_text(self, pressed_keys=None):
        self.curr_text.update(pressed_keys)
    
    def update_option_box(self, pressed_keys=None):
        self.option_box.update(pressed_keys)

    def remove_option_box(self, option_box):
        for s in option_box:
            s.kill()
            del s

    def create_quantity_box(self):
        global inventory
        seeds_list = [key for key, curr_list in inventory.items() if curr_list[3] == 'plant']
        if self.option_box.curr_selection - 1 == len(seeds_list):
            quantity_options = [' ']
        else:
            curr_key = seeds_list[self.option_box.curr_selection - 1]
            quantity_str = f'Held {inventory[curr_key][1]}'
            quantity_options = [quantity_str]
        self.quantity_box = Overworld_Option_Box(top_left=(184,90), options=quantity_options, use_arrow=False)
        self.add(self.quantity_box)

    def create_money_box(self):
        global money
        money_options = [f'$$$ {money}']
        self.money_box = Overworld_Option_Box(top_left=(184,0), options=money_options, use_arrow=False)
        self.add(self.money_box)

    def create_store_box(self):
        global purchase_list
        global inventory
        if self.option_box.curr_selection - 1 == len(list(purchase_list)):
            store_box_options = [' ', ' ', ' ']
        else:
            curr_key = list(purchase_list)[self.option_box.curr_selection - 1]
            store_box_options = [f"Price {purchase_list[curr_key][0]}", f"Stock {purchase_list[curr_key][1]}"]
            if curr_key in list(inventory.keys()):
                store_box_options.append(f"Held {inventory[curr_key][1]}")
            else:
                store_box_options.append("Held 0")
        self.store_box = Overworld_Option_Box(top_left=(184,61), options=store_box_options, use_arrow=False)
        self.add(self.store_box)

    def update_money_box(self):
        self.remove_option_box(self.money_box)
        self.create_money_box()

    def update_store_box(self):
        self.remove_option_box(self.store_box)
        self.create_store_box()

    def update_quantity_box(self):
        self.remove_option_box(self.quantity_box)
        self.create_quantity_box()

    def update_buy_options(self, pressed_keys=None):
        global purchase_list
        temp_position = self.option_box.curr_selection
        self.update_option_box(pressed_keys=pressed_keys)
        if self.option_box.final_selection == None:
            if self.option_box.curr_selection != temp_position: #Change store info, nothing has been bought
                if self.option_box.curr_selection - 1 ==  len(list(purchase_list)):
                    self.curr_text.set_letters(' ', text_type='immediate')
                else:
                    curr_key = list(purchase_list)[self.option_box.curr_selection - 1]
                    self.curr_text.set_letters(purchase_list[curr_key][2], text_type='immediate')
                self.curr_text.update()
                self.add(self.curr_text)
                self.update_store_box() #Update price/quantity/held box
        else:
            if self.option_box.final_selection_text != 'Cancel': #Something is attempted to be bought
                global money
                global inventory
                curr_key = list(purchase_list)[self.option_box.curr_selection - 1]
                if purchase_list[curr_key][1] != 0 and money >= purchase_list[curr_key][0]: #Buy successfully
                    money -= purchase_list[curr_key][0]
                    purchase_list[curr_key][1] -= 1
                    if self.option_box.final_selection_text in list(inventory.keys()):
                        inventory[curr_key][1] += 1
                    else:
                        inventory[curr_key] = copy.deepcopy(purchase_list[curr_key])
                        inventory[curr_key][1] = 1
                    self.update_money_box()
                    self.update_store_box()
                else: #Do not buy
                    cancel_sound()
                self.option_box.final_selection = None #Clear the final selection
                self.option_box.final_selection_text = None

    def update_planting_options(self, pressed_keys=None):
        global inventory
        temp_position = self.option_box.curr_selection
        self.update_option_box(pressed_keys=pressed_keys)
        
        if self.option_box.final_selection == None:
            if self.option_box.curr_selection != temp_position: #Change planting info, nothing has been selected
                seeds_list = [key for key, curr_list in inventory.items() if curr_list[3] == 'plant']
                if self.option_box.curr_selection - 1 ==  len(seeds_list): #Cancel option, blank description
                    self.curr_text.set_letters(' ', text_type='immediate')
                else:   #Get description
                    curr_key = seeds_list[self.option_box.curr_selection - 1]
                    self.curr_text.set_letters(inventory[curr_key][2], text_type='immediate')
                self.curr_text.update()
                self.add(self.curr_text)
                self.update_quantity_box() #Update quantity_box
        else: 
            if self.option_box.final_selection_text != 'Cancel':
                seeds_list = [key for key, curr_list in inventory.items() if curr_list[3] == 'plant']
                self.final_seed = seeds_list[self.option_box.curr_selection - 1]
                inventory[self.final_seed][1] -= 1 # Update inventory

class Overworld_Option_Box(pygame.sprite.Group):
    def __init__(self, top_left, options, use_buy_sound=False, use_arrow=True):
        super(Overworld_Option_Box, self).__init__()
        force_wide = False
        for option in options:
            if len(option) > 9:
                force_wide = True
        if force_wide or len(options) > 4:
            menu_box_sprite = Overworld_Wide_Option_Box(top_left)
        elif len(options) == 1:
            menu_box_sprite = Overworld_One_Option_Box(top_left)
        elif len(options) == 2:
            menu_box_sprite = Overworld_Two_Option_Box(top_left)
        elif len(options) == 3:
            menu_box_sprite = Overworld_Three_Option_Box(top_left)
        else:
            menu_box_sprite = Overworld_Four_Option_Box(top_left)
            
        self.use_buy_sound = use_buy_sound
        self.options = options
        
        self.add(menu_box_sprite)
        self.curr_selection = 1
        self.final_selection = None
        self.final_selection_text = None

        self.build_options(top_left, options, use_arrow)

    def build_options(self, top_left, options, use_arrow):
        self.option_characters_list = []
        start_x, start_y = top_left

        for i, (option_text) in enumerate(options):
            char_list = self.create_text_label(option_text, start_x + 8, start_y + 8 + (12*i), arrow=use_arrow, recolor=False)
            self.option_characters_list.append(char_list)

        # Hide all selections first
        if use_arrow:
            for i, char_list in enumerate(self.option_characters_list):
                char_list[0].hide()  # Hide the first character of each move (this assumes your move_char_lists structure is consistent)

            # Show the selected move
            if 1 <= self.curr_selection <= len(self.option_characters_list):
                self.option_characters_list[self.curr_selection - 1][0].reveal()  # Reveal the first character of the selected move
        


    def create_text_label(self, text, x, y, arrow=False, visible=True, recolor=False):
        char_list = []
        curr_width = x
        if arrow:
            temp_char = Regular_Font_Letter('selection', (curr_width, y), recolor=recolor)
            curr_width += 1
            char_list.append(temp_char)
        for char in text:
            temp_char = Regular_Font_Letter(char, (curr_width, y), recolor=recolor)
            curr_width += temp_char.width
            char_list.append(Regular_Font_Letter(char, (curr_width, y), recolor=recolor))
        for item in char_list:
            self.add(item)
            if visible:
                item.reveal()
            else:
                item.hide()
        return char_list
    
    def update(self, pressed_keys=None):
        self.get_selection_input(pressed_keys=pressed_keys)

    def clear_all_text(self):
        for char_list in self.option_characters_list:
            for char in char_list:
                char.kill()
                self.remove(char)

    def update_money(self):
        #Money box
        global money
        money_str = f'$$$ {money}'
        self.create_text_label(money_str, 188, 8)

    def get_selection_input(self, pressed_keys=None):
        new_selection = None
        if pressed_keys != None:
            if pressed_keys[K_RETURN]:
                if not self.use_buy_sound:
                    select_sound()
                self.final_selection = self.curr_selection
                self.final_selection_text = self.options[self.final_selection - 1]
                print(self.final_selection)
                print(self.final_selection_text)
            else:
                if pressed_keys[K_UP]:
                    if self.curr_selection > 1:
                        new_selection = self.curr_selection - 1
                if pressed_keys[K_DOWN]:
                    if self.curr_selection < len(self.option_characters_list):
                        new_selection = self.curr_selection + 1
        if new_selection != None and new_selection != self.curr_selection and self.final_selection == None:
            self.option_characters_list[self.curr_selection - 1][0].hide()
            self.curr_selection = new_selection
            self.option_characters_list[self.curr_selection - 1][0].reveal()

class Regular_Font_Line(pygame.sprite.Group):
    def __init__(self, input_string, text_type):
        super(Regular_Font_Line, self).__init__()
        self.text_type = text_type
        self.set_letters(input_string, self.text_type)

    def update(self, pressed_keys=None):
        if not self.all_letters_set:
            revealed_count = 0
            for item in self.char_list:
                if item.rect.topright != item.topright_input:
                    item.reveal()
                    if item is self.arrow:
                        self.is_arrow_on_screen = True
                    if self.text_type != 'immediate':
                        break
                else:
                    revealed_count += 1

            if revealed_count >= self.expected_length:
                self.all_letters_set = True

        if self.is_arrow_on_screen and self.arrow:
            self.arrow.animate_arrow()

        if pressed_keys and pressed_keys[K_RETURN]:
            select_sound()
            if self.text_type == 'arrow' and self.is_arrow_on_screen:
                for sprite in self:
                    sprite.kill()
                self.ready_for_removal = True

        if self.text_type in ('not_arrow', 'immediate') and self.ready_for_removal:
            for sprite in self:
                sprite.kill()
            self.empty()  # Clear group explicitly

    def create_text_label(self, text, x, y, arrow=False, visible=True, recolor=False):
        char_list = []
        curr_width = x
        if arrow:
            temp_char = Regular_Font_Letter('selection', (curr_width, y), recolor=recolor)
            curr_width += 1
            char_list.append(temp_char)
        for char in text:
            temp_char = Regular_Font_Letter(char, (curr_width, y), recolor=recolor)
            curr_width += temp_char.width
            char_list.append(Regular_Font_Letter(char, (curr_width, y), recolor=recolor))
        for item in char_list:
            self.add(item)
            if visible:
                item.reveal()
            else:
                item.hide()
        return char_list

    def set_letters(self, input_string, text_type):
        if len(input_string) > 36:
            split_index = input_string.rfind(' ', 0, 36)
            if split_index == -1:
                split_index = 36  # no space found, hard split
            input_string_top = input_string[:split_index].strip()
            input_string_bottom = input_string[split_index:].strip()
            self.expected_length = len(input_string_top) + len(input_string_bottom)
        else:
            input_string_top = input_string
            self.expected_length = len(input_string_top)
            input_string_bottom = None
        
        # Clear existing sprites efficiently
        for sprite in self.sprites():
            sprite.kill()
        self.empty()
        self.input_string_top = input_string_top
        self.input_string_bottom = input_string_bottom
        # Update internal state
        self.text_type = text_type
        self.arrow = None
        self.ready_for_removal = False
        self.is_arrow_on_screen = False
        self.all_letters_set = False
        # Starting positions
        starting_height_top = 124
        starting_height_bottom = 140
        starting_width = 15 #if text_type == 'immediate' else 24

        self.char_list = self.create_text_label(input_string_top, starting_width, starting_height_top)

        # Bottom line (if exists)
        if input_string_bottom:
            char_list_bottom = self.create_text_label(input_string_bottom, starting_width, starting_height_bottom)
            self.char_list.extend(char_list_bottom)
            self.input_string_bottom_len = len(input_string_bottom)
        else:
            self.input_string_bottom_len = 0

        # Add arrow if required
        if text_type == 'arrow':
            arrow_x = self.char_list[-1].rect.x + 14
            self.arrow = Regular_Font_Letter('DownArrow', (arrow_x, 138))
            self.char_list.append(self.arrow)
            self.add(self.char_list)

class Overworld_Filling_Option_BoxGroup(pygame.sprite.Group):
    def __init__(self):
        super(Overworld_Filling_Option_BoxGroup, self).__init__()
        global inventory
        self.seeds_list = []
        for key in inventory:
            curr_list = inventory[key]
            if curr_list[4] == 'dirt':
                self.seeds_list.append(key)
        self.plants_list = []
        for seed in self.seeds_list:
            self.plants_list.append(inventory[seed][4])
        self.big_option_box = Overworld_Option_Box((0,0), self.seeds_list, 'plant')
        self.final_selection = self.big_option_box.final_selection
        self.current_position = 1
        self.add(self.big_option_box)

        self.curr_text_box = Overworld_Main_Text_box()
        self.add(self.curr_text_box)
        self.curr_text = Regular_Font_Line(input_string=inventory[self.seeds_list[self.current_position - 1]][2], text_type='immediate')
        self.add(self.curr_text)


        self.quantity_box = Overworld_One_Option_Box((184,90))
        self.add(self.quantity_box)
        self.update_quantity()

    def update(self, pressed_keys=None):
        global inventory
        self.big_option_box.update(pressed_keys)
        if self.big_option_box.final_selection == None:
            self.curr_text.update()
            if self.current_position != self.big_option_box.curr_selection:
                self.current_position = self.big_option_box.curr_selection
                self.curr_text.set_letters(inventory[self.seeds_list[self.current_position - 1]][2], text_type='immediate')
                #print(self.curr_text.input_string_bottom)
                self.curr_text.update()
                self.add(self.curr_text)
                for item in self.quantity_char_list:
                    item.kill()
                    self.remove(item)
                    del item
                self.update_quantity()
        else: 
            # Before modification
            self.final_seed = self.seeds_list[self.current_position - 1]
            #print("Before inventory update:", inventory[self.final_seed][1])
            # Update inventory
            inventory[self.final_seed][1] -= 1
            # After modification
            #print("After inventory update:", inventory[self.final_seed][1])
            self.final_selection = self.plants_list[self.current_position - 1]

    def update_quantity(self):
        #Money box
        global inventory
        self.quantity_str = f'Held {inventory[self.seeds_list[self.current_position - 1]][1]}'
        self.quantity_char_list = []
        starting_width = 188 
        starting_height = 95 
        curr_width = starting_width + 1
        for char in self.quantity_str:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.quantity_char_list.append(curr_char)
        for item in self.quantity_char_list:
            self.add(item)
            item.reveal()

class Select_Move_Group(pygame.sprite.Group):
    def __init__(self, move1, move1_currpp, move1type, move2, move2_currpp, move2type, move3, move3_currpp, move3type, move4, move4_currpp, move4type, curr_selection=1):
        super(Select_Move_Group, self).__init__()
        select_move_text_box = Select_Move_Box()
        self.add(select_move_text_box)

        if move2 == None:
            self.number_of_moves = 1
        elif move3 == None:
            self.number_of_moves = 2
        else:
            self.number_of_moves = 3

        all_moves = [
            (move1, move1_currpp, move1type),
            (move2 or "Status", move2_currpp or 0, move2type or "STATUS"),
            (move3 if move3 is not None else ("--" if move2 is None else "Status"), move3_currpp or 0, move3type or "--"),
            (move4 if move3 is not None else "--", move4_currpp or 0, move4type or "--"),
        ]
        
        self.move_char_lists = []
        x_offsets = [8, 86, 8, 86]
        y_offsets = [124, 124, 139, 139]

        for i, (move_text, _, _) in enumerate(all_moves):
            char_list = self.create_text_label(move_text, x_offsets[i], y_offsets[i], arrow=True)
            self.move_char_lists.append(char_list)

        #CREATE POWER
        self.char_list_power = self.create_text_label("POWER", 165, 124)

        self.char_list_type_1, self.char_list_pp_1 = self.populate_pp_and_type(move1_currpp, move1type)
        self.char_list_type_2, self.char_list_pp_2 = self.populate_pp_and_type(move2_currpp, move2type)
        self.char_list_type_3, self.char_list_pp_3 = self.populate_pp_and_type(move3_currpp, move3type)
        self.char_list_type_4, self.char_list_pp_4 = self.populate_pp_and_type(move4_currpp, move4type)

        self.curr_selection = curr_selection

        # Hide all selections first
        for i, char_list in enumerate(self.move_char_lists):
            char_list[0].hide()  # Hide the first character of each move (this assumes your move_char_lists structure is consistent)

        # Show the selected move
        if 1 <= self.curr_selection <= len(self.move_char_lists):
            self.move_char_lists[self.curr_selection - 1][0].reveal()  # Update the first character of the selected move

        self.final_selection = None

        # Assuming self.char_list_type_1, self.char_list_pp_1, etc. are already handled similarly, or part of your updated design
        for item in self.char_list_type_1 + self.char_list_pp_1:
            item.reveal()
            self.add(item)

    def create_text_label(self, text, x, y, arrow=False, visible=True):
        char_list = []
        curr_width = x
        if arrow:
            temp_char = Regular_Font_Letter('selection', (curr_width, y), recolor=False)
            curr_width += 1
            char_list.append(temp_char)
        for char in text:
            temp_char = Regular_Font_Letter(char, (curr_width, y), recolor=False)
            curr_width += temp_char.width
            char_list.append(Regular_Font_Letter(char, (curr_width, y), recolor=False))
        for item in char_list:
            self.add(item)
            if visible:
                item.reveal()
            else:
                item.hide()
        return char_list
    
    def change_pp_and_type(self, curr_type_list, curr_pp_list, new_type_list, new_pp_list):
        for item in curr_type_list:
            item.hide()
        for item in curr_pp_list:
            item.hide()
        for item in new_type_list:
            item.reveal()
        for item in new_pp_list:
            item.reveal()
        select_sound()

    def populate_pp_and_type(self, curr_pp, curr_type):
        # Create PP label
        char_list_pp = self.create_text_label(str(curr_pp), 202, 124, visible=False)
        # Create type label
        if curr_type == 'STATUS':
            type_text = 'CHECK STATUS'
            x_pos = 163
        else:
            type_text = str(curr_type)
            x_pos = 168
        char_list_type = self.create_text_label(type_text, x_pos, 139, visible=False)
        return char_list_type, char_list_pp
    
    def update(self, pressed_keys=None):
        new_selection = None
        if pressed_keys != None:
            if pressed_keys[K_RETURN]:
                #self.final_selection = self.curr_selection
                #print('not doing anything yet')
                select_sound()
                self.final_selection = self.curr_selection
            else:
                if pressed_keys[K_UP]:
                    if self.curr_selection > 2:
                        new_selection = self.curr_selection - 2
                if pressed_keys[K_DOWN]:
                    if self.curr_selection < 3:
                        new_selection = self.curr_selection + 2
                if pressed_keys[K_RIGHT]:
                    if self.curr_selection % 2 != 0:
                        new_selection = self.curr_selection + 1
                if pressed_keys[K_LEFT]:
                    if self.curr_selection % 2 == 0:
                        new_selection = self.curr_selection - 1
        if new_selection != None and new_selection != self.curr_selection and self.final_selection == None and new_selection <= (self.number_of_moves + 1):
            prev_selection = self.curr_selection
            # Predefined mapping for type and pp lists
            type_lists = [self.char_list_type_1, self.char_list_type_2, self.char_list_type_3, self.char_list_type_4]
            pp_lists = [self.char_list_pp_1, self.char_list_pp_2, self.char_list_pp_3, self.char_list_pp_4]
            # Use prev_selection - 1 to index into the lists
            index = prev_selection - 1
            self.move_char_lists[index][0].hide()
            curr_type_list = type_lists[index]
            curr_pp_list = pp_lists[index]
            # Update to new selection
            self.curr_selection = new_selection
            curr_index = self.curr_selection - 1
            self.move_char_lists[curr_index][0].reveal()
            self.change_pp_and_type(curr_type_list, curr_pp_list, type_lists[curr_index], pp_lists[curr_index])

class In_Battle_Money_Box(pygame.sprite.Group):
    def __init__(self):
        super(In_Battle_Money_Box, self).__init__()
        self.money_box = Overworld_One_Option_Box((0,90))
        self.add(self.money_box)
        self.update_money()

    def update_money(self):
        #Money box
        global money
        self.money_str = f'$$$ {money}'
        self.money_char_list = []
        starting_width = 3 
        starting_height = 98 
        curr_width = starting_width + 1
        for char in self.money_str:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.money_char_list.append(curr_char)
        for item in self.money_char_list:
            self.add(item)
            item.reveal()

    def change_money(self):
        for item in self.money_char_list:
            item.kill()
            self.remove(item)
            del item
        self.update_money()

class In_Battle_Time_Box(pygame.sprite.Group):
    def __init__(self):
        super(In_Battle_Time_Box, self).__init__()
        self.money_box = Battle_Time_Box((0,0))
        self.add(self.money_box)
        self.time = 9
        self.update_time()

    def update_time(self):
        #Money box
        if self.time < 12:
            self.time_str = f'{self.time}:00 PM'
        else:
            temp_time = self.time - 12
            if temp_time == 0:
                temp_time = 12
            self.time_str = f'{temp_time}:00 AM'
        self.time_char_list = []
        starting_width = 6 
        starting_height = 3 
        curr_width = starting_width + 1
        for char in self.time_str:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.time_char_list.append(curr_char)
        for item in self.time_char_list:
            self.add(item)
            item.reveal()

    def change_time(self):
        for item in self.time_char_list:
            item.kill()
            self.remove(item)
            del item
        self.update_time()

class Tileset_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super(Tileset_Group, self).__init__()
        self.tiles_list = []
        height = -80
        for row in tile_map:
            width = -96
            for column in tile_map[row]:
                curr_tile = Tile((width, height), column)
                self.tiles_list.append(curr_tile)
                width += 16
            height += 16

        for tile_sprite in self.tiles_list:
            self.add(tile_sprite)

    def move(self, direction):
        for tile_sprite in self.tiles_list:
            if direction == 'Forward':
                tile_sprite.rect.y -= 1
            elif direction == 'Backward':
                tile_sprite.rect.y += 1
            elif direction == 'Left':
                tile_sprite.rect.x += 1
            elif direction == 'Right':
                tile_sprite.rect.x -= 1

class Overworld_Status_Screen_Group(pygame.sprite.Group):
    def __init__(self, plant):
        super(Overworld_Status_Screen_Group, self).__init__()
        self.ready_for_removal = False
        self.plant = plant
        self.background_image = Overworld_Status_Screen_Box()
        self.add(self.background_image)
        self.update_status()
        self.sprite_image = Front_Sprite((5, 33), self.plant.species_name)
        self.add(self.sprite_image)
        self.update_moves()
        self.curr_text = Regular_Font_Line(input_string=self.plant.attacks[0].desc, text_type='immediate')
        self.add(self.curr_text)

        self.move_bar_highlight = Move_Bar_Highlight((74, 28))
        self.add(self.move_bar_highlight)
        self.curr_selection = 1

        self.number_of_moves = len(self.plant.attacks)

    def update_moves(self):
        #Move names
        self.move1_list = []
        self.move2_list = []
        self.move3_list = []
        self.move1_desclist = []
        self.move2_desclist = []
        self.move3_desclist = []
        starting_width = 80 
        starting_height = 35 
        curr_width = starting_width + 1
        for char in self.plant.attacks[0].name:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.move1_list.append(curr_char)
        for item in self.move1_list:
            self.add(item)
            item.reveal()
        if len(self.plant.attacks) >= 2:
            
            starting_width = 80 
            starting_height = 65 
            curr_width = starting_width + 1
            for char in self.plant.attacks[1].name:
                temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                curr_width = curr_width + temp_char.width
                curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                self.move2_list.append(curr_char)
            for item in self.move2_list:
                self.add(item)
                item.reveal()
        if len(self.plant.attacks) == 3:
            
            starting_width = 80 
            starting_height = 95 
            curr_width = starting_width + 1
            for char in self.plant.attacks[2].name:
                temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                curr_width = curr_width + temp_char.width
                curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                self.move3_list.append(curr_char)
            for item in self.move3_list:
                self.add(item)
                item.reveal()
        #Move details
        
        self.move1_desc = f"{self.plant.attacks[0].power} {self.plant.attacks[0].type}"
        starting_width = 168 
        starting_height = 35 
        curr_width = starting_width + 1
        for char in self.move1_desc:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.move1_desclist.append(curr_char)
        for item in self.move1_desclist:
            self.add(item)
            item.reveal()
        if len(self.plant.attacks) >= 2:
            
            self.move2_desc = f"{self.plant.attacks[1].power} {self.plant.attacks[1].type}"
            starting_width = 168 
            starting_height = 65 
            curr_width = starting_width + 1
            for char in self.move2_desc:
                temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                curr_width = curr_width + temp_char.width
                curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                self.move2_desclist.append(curr_char)
            for item in self.move2_desclist:
                self.add(item)
                item.reveal()
        if len(self.plant.attacks) == 3:
            
            self.move3_desc = f"{self.plant.attacks[2].power} {self.plant.attacks[2].type}"
            starting_width = 168 
            starting_height = 95 
            curr_width = starting_width + 1
            for char in self.move3_desc:
                temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                curr_width = curr_width + temp_char.width
                curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
                self.move3_desclist.append(curr_char)
            for item in self.move3_desclist:
                self.add(item)
                item.reveal()



    def update_status(self):
        #Money box
        #global money
        self.plant_species_list = []
        starting_width = 6 
        starting_height = 8 
        curr_width = starting_width + 1
        for char in self.plant.species_name:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.plant_species_list.append(curr_char)
        for item in self.plant_species_list:
            self.add(item)
            item.reveal()


        self.stats_str_1 = f'HP {self.plant.current_hp}  S.Atk {self.plant.special_attack} S.Def {self.plant.special_defense}'
        self.stats_str_list_1 = []
        starting_width = 88 
        starting_height = 0 
        curr_width = starting_width + 1
        for char in self.stats_str_1:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.stats_str_list_1.append(curr_char)
        for item in self.stats_str_list_1:
            self.add(item)
            item.reveal()
        self.stats_str2 = f'Atk {self.plant.attack} Def {self.plant.defense} Spd {self.plant.speed}'
        self.stats_str_list_2 = []
        starting_width = 88 
        starting_height = 13
        curr_width = starting_width + 1
        for char in self.stats_str2:
            temp_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            curr_width = curr_width + temp_char.width
            curr_char = Regular_Font_Letter(char, (curr_width, starting_height), recolor=False)
            self.stats_str_list_2.append(curr_char)
        for item in self.stats_str_list_2:
            self.add(item)
            item.reveal()


    def update(self, pressed_keys=None):
        self.curr_text.update()
        new_selection = None
        if pressed_keys != None:
            if pressed_keys[K_TAB]:
                #rint('return')
                #self.final_selection = self.curr_selection
                #print('not doing anything yet')
                cancel_sound()
                self.ready_for_removal = True
            else:
                if pressed_keys[K_UP]:
                    #print('up')
                    if self.curr_selection != 1:
                        new_selection = self.curr_selection -1
                if pressed_keys[K_DOWN]:
                    #print('down')
                    if self.curr_selection != self.number_of_moves:
                        new_selection = self.curr_selection + 1
                if new_selection != self.curr_selection and new_selection != None:
                    #print()
                    self.curr_selection = new_selection
                    if self.curr_selection == 1:
                        self.move_bar_highlight.change_position((74, 28))
                        self.curr_text.set_letters(self.plant.attacks[0].desc, 'immediate')
                        self.curr_text.update()
                        self.add(self.curr_text)
                    elif self.curr_selection == 2:
                        self.move_bar_highlight.change_position((74, 56))
                        self.curr_text.set_letters(self.plant.attacks[1].desc, 'immediate')
                        self.curr_text.update()
                        self.add(self.curr_text)
                    elif self.curr_selection == 3:
                        self.move_bar_highlight.change_position((74, 84))
                        self.curr_text.set_letters(self.plant.attacks[2].desc, 'immediate')
                        self.curr_text.update()
                        self.add(self.curr_text)

    def change_status(self):
        for item in self.plant_species_list:
            item.kill()
            self.remove(item)
            del item
        for item in self.stats_str_list_1:
            item.kill()
            self.remove(item)
            del item
        for item in self.stats_str_list_2:
            item.kill()
            self.remove(item)
            del item
        self.update_status()

    def change_moves(self):
        for item in self.move1_list:
            item.kill()
            self.remove(item)
            del item
        for item in self.move1_desclist:
            item.kill()
            self.remove(item)
            del item
        for item in self.move2_list:
            item.kill()
            self.remove(item)
            del item
        for item in self.move2_desclist:
            item.kill()
            self.remove(item)
            del item
        for item in self.move3_list:
            item.kill()
            self.remove(item)
            del item
        for item in self.move3_desclist:
            item.kill()
            self.remove(item)
            del item
        self.update_moves()

def clear_text():
    global curr_text_added, curr_text
    curr_text_added = False
    curr_text = None
    print('text cleared')

def kill_menu_and_clear():
    global curr_menu
    curr_menu.update_curr_text()
    for s in curr_menu:
        s.kill()
        del s
    clear_text()
    curr_menu = None

def initialize_overworld():
    global tileset_current
    global overworld_sprites
    global overworld_player_sprite
    global tileset_group
    global collison_map
    global planters
    if tileset_current == False:
        print('started tileset_test')
        for sprite in tileset_group:
            overworld_sprites.add(sprite, layer=1)
        overworld_player_sprite = Player_Overworld_Sprite((112,80), tile_row=10, tile_column=13)
        overworld_sprites.add(overworld_player_sprite, layer = 3)
    
        computer_sprite = Computer((208,128))
        overworld_sprites.add(computer_sprite, layer=2)
        tileset_group.add(computer_sprite)
        tileset_group.tiles_list.append(computer_sprite)
        collison_map['row14'][19] = 8

        planter_sprite6 = Planter((160,64))
        overworld_sprites.add(planter_sprite6, layer=2)
        tileset_group.add(planter_sprite6)
        tileset_group.tiles_list.append(planter_sprite6)
        collison_map['row10'][16] = 80
        planters['row10'][16]  = planter_sprite6

        planter_sprite5 = Planter((144,64))
        overworld_sprites.add(planter_sprite5, layer=2)
        tileset_group.add(planter_sprite5)
        tileset_group.tiles_list.append(planter_sprite5)
        collison_map['row10'][15] = 80
        planters['row10'][15]  = planter_sprite5

        planter_sprite4 = Planter((128,64))
        overworld_sprites.add(planter_sprite4, layer=2)
        tileset_group.add(planter_sprite4)
        tileset_group.tiles_list.append(planter_sprite4)
        collison_map['row10'][14] = 80
        planters['row10'][14]  = planter_sprite4

        planter_sprite3 = Planter((96,64))
        overworld_sprites.add(planter_sprite3, layer=2)
        tileset_group.add(planter_sprite3)
        tileset_group.tiles_list.append(planter_sprite3)
        collison_map['row10'][12] = 80
        planters['row10'][12]  = planter_sprite3

        planter_sprite = Planter((80,64))
        overworld_sprites.add(planter_sprite, layer=2)
        tileset_group.add(planter_sprite)
        tileset_group.tiles_list.append(planter_sprite)
        collison_map['row10'][11] = 80
        planters['row10'][11]  = planter_sprite

        planter_sprite2 = Planter((64,64))
        overworld_sprites.add(planter_sprite2, layer=2)
        tileset_group.add(planter_sprite2)
        tileset_group.tiles_list.append(planter_sprite2)
        collison_map['row10'][10] = 80
        planters['row10'][10]  = planter_sprite2

        tileset_current = True


#---------GAME PHASES
def titlescreen_phase(pressed_keys):
    global overworld_sprites, exit_title_screen_phase, title_screen
    if title_screen == None:
        title_screen = Title_Screen()
        overworld_sprites.add(title_screen, layer=9)
    elif pressed_keys and pressed_keys[K_RETURN]:
        exit_title_screen_phase = True
        title_screen.kill()
        del title_screen

def tileset_test(pressed_keys):
    global overworld_sprites
    global tileset_current
    global overworld_player_sprite
    global curr_menu
    global in_menu
    def create_menu(input_str, options=None, text_type='not_arrow'):
        return Overworld_Menu(input_string=input_str, text_type=text_type, options=options)
    if tileset_current == False:
        initialize_overworld()
    else:
        overworld_player_sprite.player_move(pressed_keys)
        if overworld_player_sprite.moving:
            tileset_group.move(overworld_player_sprite.new_direction)
            overworld_player_sprite.player_moving_animation()
        if overworld_player_sprite.interacting:
            if not curr_menu:
                if overworld_player_sprite.intereaction_tile == 8:  # Computer
                    curr_menu = create_menu('What would you like to do?', ['BUY', 'QUIT'])
                elif overworld_player_sprite.intereaction_tile == 80:  # Planter
                    row, col = overworld_player_sprite.interaction_tile_row, overworld_player_sprite.interaction_tile_column
                    row_str = f"row{row}"
                    global planters
                    planter = planters[row_str][col]
                    plants = any(i[3] == 'plant' for i in inventory.values())
                    dirt = any(i[3] == 'dirt' for i in inventory.values())
                    if not planter.has_plant and plants:
                        options = ['PLANT', 'CHECK', 'FILL', 'QUIT'] if dirt else ['PLANT', 'CHECK', 'QUIT']
                        curr_menu = create_menu('What would you like to do with the planter?', options)
                    elif not planter.has_plant:
                        options = ['CHECK', 'FILL', 'QUIT'] if dirt else ['CHECK', 'QUIT']
                        curr_menu = create_menu('What would you like to do with the dirt?', options)
                    else:
                        plant_name = planter.plant.plant_species
                        options = ['CHECK', 'FILL', 'QUIT'] if dirt else ['CHECK', 'QUIT']
                        curr_menu = create_menu(f"What would you like to do with the {plant_name}?", options)
                elif overworld_player_sprite.intereaction_tile in (13, 14):  # Door
                    if plant_sprites:
                        curr_menu = create_menu('Would you like to head out for the day?', ['YES', 'NO'])
                    else:
                        curr_menu = create_menu('You must plant something before heading out for the day.', text_type='arrow')
                overworld_sprites.add(curr_menu.main_text_box, layer=4)
                overworld_sprites.add(*curr_menu.curr_text, layer=9)
                if curr_menu.option_box:
                    overworld_sprites.add(*curr_menu.option_box, layer=9)
                in_menu = True
                pressed_keys = None
            if curr_menu.option_box:
                curr_menu.update_option_box(pressed_keys)
            if overworld_player_sprite.intereaction_tile in (13, 14):
                if curr_menu.curr_text.all_letters_set == False or curr_menu.curr_text.is_arrow_on_screen == True:
                    curr_menu.update_curr_text(pressed_keys)
                else:
                    curr_menu.update_curr_text()
            if curr_menu.option_box == None and curr_menu.curr_text.ready_for_removal:
                kill_menu_and_clear()
                in_menu = False
                overworld_player_sprite.interacting = False
                overworld_player_sprite.entry_delay = 15
            elif curr_menu and curr_menu.option_box:
                if curr_menu.option_box.final_selection_text:
                    print()
                    curr_menu.curr_text.ready_for_removal = True
                    if curr_menu.option_box.final_selection_text in ['QUIT', 'NO']:
                        in_menu = False
                        overworld_player_sprite.interacting = False
                        overworld_player_sprite.entry_delay = 15
                    elif curr_menu.option_box.final_selection_text == 'CHECK':
                        global enter_check_phase
                        enter_check_phase = True
                    elif curr_menu.option_box.final_selection_text == 'YES':
                        global enter_day_to_dusk_transition_phase
                        enter_day_to_dusk_transition_phase = True
                    elif curr_menu.option_box.final_selection_text == 'PLANT':
                        global enter_plant_phase
                        enter_plant_phase = True
                    elif curr_menu.option_box.final_selection_text == 'FILL':
                        global enter_fill_phase
                        enter_fill_phase = True
                    elif curr_menu.option_box.final_selection_text == 'BUY':
                        global enter_buy_phase
                        enter_buy_phase = True
                    kill_menu_and_clear()

def plant_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global in_menu
    global plant_growing
    global plant_sprites
    global inventory
    global curr_menu
    global enter_plant_phase
    if not plant_growing:
        if curr_menu == None:
            options_list = [key for key, curr_list in inventory.items() if curr_list[3] == 'plant']
            options_list.append('Cancel')
            first_key = options_list[0]
            first_text = inventory[first_key][2]
            curr_menu = Overworld_Menu(first_text, options=options_list, text_type='immediate', quantity_box=True)
            for sprite in curr_menu:
                overworld_sprites.add(sprite, layer=9)
            overworld_sprites.add(curr_menu.main_text_box, layer=4)
            overworld_sprites.add(*curr_menu.curr_text, layer=9)
            overworld_sprites.add(*curr_menu.option_box, layer=9)
            overworld_sprites.add(*curr_menu.quantity_box, layer=9)
        curr_menu.update_planting_options(pressed_keys)
        if curr_menu.option_box.final_selection_text == None:
            for sprite in curr_menu:
                    if sprite not in overworld_sprites:
                        #print('adding')
                        overworld_sprites.add(sprite, layer = 9)
        else:
            if curr_menu.option_box.final_selection_text != 'Cancel':
                print(overworld_player_sprite.direction)
                direction_positions = {
                    'Backward': (116, 58),
                    'Forward':  (116, 90),
                    'Left':     (100, 74),
                    'Right':    (132, 74),
                }
                plant_sprite = Plant_Overworld_Sprite(direction_positions[overworld_player_sprite.direction], inventory[curr_menu.option_box.final_selection_text][4])
                overworld_sprites.add(plant_sprite, layer=4)
                tileset_group.add(plant_sprite)
                tileset_group.tiles_list.append(plant_sprite)
                plant_sprites.append(plant_sprite)
                plant_to_append = Specific_Plant(species=plant_sprite.plant_species_object,hp_ev=0, attack_ev=0, 
                                                defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[plant_sprite.starting_attack])
                global plants
                plants.append(plant_to_append)
                kill_menu_and_clear()
                plant_growing = True
                curr_row = overworld_player_sprite.interaction_tile_row
                curr_row_str = f"row{curr_row}"
                curr_column = overworld_player_sprite.interaction_tile_column
                global planters
                planters[curr_row_str][curr_column].has_plant = True
                planters[curr_row_str][curr_column].plant = plant_sprite
                planters[curr_row_str][curr_column].specific_plant_object = plant_to_append
                keys_to_remove = [key for key in inventory if inventory[key][1] == 0]
                for key in keys_to_remove:
                    del inventory[key]
            else: #Exit without planting
                print()
                kill_menu_and_clear()
                in_menu = False
                overworld_player_sprite.interacting = False
                overworld_player_sprite.entry_delay = 15
                enter_plant_phase = False
    else:
        plant_sprites[len(plant_sprites)-1].grow_plant()
        in_menu = False
        overworld_player_sprite.interacting = False
        overworld_player_sprite.entry_delay = 15
        print(plant_sprites[len(plant_sprites)-1].curr_frame)
        if plant_sprites[len(plant_sprites)-1].grown == True:
            plant_growing = False
            enter_plant_phase = False


def fill_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global curr_option_box
    global in_menu
    global enter_plant_phase
    global plant_growing
    global plant_sprites
    global planters
    global inventory
    global enter_fill_phase
    if curr_option_box == None:
        curr_option_box = Overworld_Filling_Option_BoxGroup()
        for sprite in curr_option_box:
            overworld_sprites.add(sprite, layer=9)
    curr_option_box.update(pressed_keys)
    for sprite in curr_option_box:
        if sprite not in overworld_sprites:
            overworld_sprites.add(sprite, layer = 9)
    if curr_option_box.final_selection != None:
        print()
        curr_row = overworld_player_sprite.interaction_tile_row
        curr_row_str = f"row{curr_row}"
        curr_column = overworld_player_sprite.interaction_tile_column
        #Update planter sprite and dirt
        tileset_group.tiles_list.remove(planters[curr_row_str][curr_column])
        planters[curr_row_str][curr_column].change_dirt(curr_option_box.final_selection)
        tileset_group.tiles_list.append(planters[curr_row_str][curr_column])
        overworld_sprites.add(planters[curr_row_str][curr_column], layer =2)
        keys_to_remove = [key for key in inventory if inventory[key][1] == 0]
        for key in keys_to_remove:
            del inventory[key]
        in_menu = False
        overworld_player_sprite.interacting = False
        overworld_player_sprite.entry_delay = 15
        enter_fill_phase = False
        for sprite in curr_option_box:
            sprite.kill()
            del sprite
        del curr_option_box
        curr_option_box = None
            
def buy_phase(pressed_keys):
    global overworld_sprites
    global inventory
    global tileset_current
    global curr_menu
    global purchase_list
    if curr_menu == None:
        options_list = list(purchase_list)
        options_list.append('Cancel')
        first_key = next(iter(purchase_list))
        first_text = purchase_list[first_key][2]
        curr_menu = Overworld_Menu(first_text, options=options_list, text_type='immediate', money_box=True, store_box=True)
        for sprite in curr_menu:
            overworld_sprites.add(sprite, layer=9)
        overworld_sprites.add(curr_menu.main_text_box, layer=4)
        overworld_sprites.add(*curr_menu.curr_text, layer=9)
        overworld_sprites.add(*curr_menu.option_box, layer=9)
        overworld_sprites.add(*curr_menu.money_box, layer=9)
        overworld_sprites.add(*curr_menu.store_box, layer=9)
    curr_menu.update_buy_options(pressed_keys)
    if curr_menu.option_box.final_selection_text != 'Cancel':
        for sprite in curr_menu:
            if sprite not in overworld_sprites:
                overworld_sprites.add(sprite, layer = 9)
        for key in inventory:
            if key == 'Windows Lv. 2' or key == 'Windows Lv. 3':
                print('go to windows update phase')
                tileset_current = False
                global enter_bought_windows_phase
                enter_bought_windows_phase = True
            elif key == 'Irrigation Lv.1' or key == 'Irrigation Lv.2' or key == 'Irrigation Lv.3':
                print('go to Irrigation update phase')
                tileset_current = False
                global enter_bought_irrigation_phase
                enter_bought_irrigation_phase = True
            elif key == 'Generator Lv.1' or key == 'Generator Lv.2' or key == 'Generator Lv.3':
                print('go to Generator update phase')
                tileset_current = False
                global enter_bought_generator_phase
                enter_bought_generator_phase = True
    else:
        kill_menu_and_clear()
        keys_to_remove = [key for key in purchase_list if purchase_list[key][1] == 0]
        for key in keys_to_remove:
            del purchase_list[key]
        global in_menu
        in_menu = False
        global overworld_player_sprite
        overworld_player_sprite.interacting = False
        overworld_player_sprite.entry_delay = 15
        global enter_buy_phase
        enter_buy_phase = False


def bought_generator_phase(pressed_keys):
    global overworld_sprites
    global background
    global inventory
    global tile_map
    global tileset_group
    global tileset_current
    global generator_level
    global enter_bought_generator_phase
    if background == None:
        background = Black_Rectangle()
        overworld_sprites.add(background, layer = 12)
    else:
        if background.faded_in == False:
            background.handle_screen_fades(fade_fast=True)
        elif background.faded_in == True:
            if tileset_current == False:
                level_changing_to = 1
                for key in inventory:
                    if key == 'Generator Lv.1':
                        print('change to Generator level 1')
                        level_changing_to = 1
                        key_to_remove = key
                    elif key == 'Generator Lv.2':
                        print('change to Irrigation level 2')
                        level_changing_to = 2
                        key_to_remove = key
                    elif key == 'Generator Lv.3':
                        print('change to Irrigation level 3')
                        level_changing_to = 3
                        key_to_remove = key
                del inventory[key_to_remove]
                print('got to here')
                if level_changing_to == 1:
                    generator_left = Generator_Left((-32,16), 1)
                    overworld_sprites.add(generator_left, layer=2)
                    tileset_group.add(generator_left)
                    tileset_group.tiles_list.append(generator_left)
                    generator_bottom = Generator_Bottom((-16,16))
                    overworld_sprites.add(generator_bottom, layer=2)
                    tileset_group.add(generator_bottom)
                    tileset_group.tiles_list.append(generator_bottom)
                    generator_right = Generator_Right((96,16), 1)
                    overworld_sprites.add(generator_right, layer=2)
                    tileset_group.add(generator_right)
                    tileset_group.tiles_list.append(generator_right)
                    collison_map['row11'][9] = 4
                    collison_map['row11'][17] = 4
                    #collison_map['row14'][19] = 8
                else:
                    for item in tileset_group.tiles_list:
                        if isinstance(item, Generator_Left):
                            #print('instance')
                            #Change the sprite
                            item.change_level(level_changing_to)
                            overworld_sprites.add(item, layer = 2)
                        if isinstance(item, Generator_Right):
                            #print('instance')
                            #Change the sprite
                            item.change_level(level_changing_to)
                            overworld_sprites.add(item, layer = 2)
                generator_level = level_changing_to
                tileset_current = True
                
            if background.faded_out == False:
                background.handle_screen_fades(fade_fast=True)
            else:
                print('leave phase')
                background.kill()
                del background
                background = None
                enter_bought_generator_phase = False

def bought_irrigation_phase(pressed_keys):
    global overworld_sprites
    global background
    global inventory
    global tile_map
    global tileset_group
    global tileset_current
    global irrigation_level
    global enter_bought_irrigation_phase
    if background == None:
        background = Black_Rectangle()
        overworld_sprites.add(background, layer = 12)
    else:
        if background.faded_in == False:
            background.handle_screen_fades(fade_fast=True)
        elif background.faded_in == True:
            if tileset_current == False:
                level_changing_to = 1
                for key in inventory:
                    if key == 'Irrigation Lv.1':
                        print('change to Irrigation level 1')
                        level_changing_to = 1
                        key_to_remove = key
                    elif key == 'Irrigation Lv.2':
                        print('change to Irrigation level 2')
                        level_changing_to = 2
                        key_to_remove = key
                    elif key == 'Irrigation Lv.3':
                        print('change to Irrigation level 3')
                        level_changing_to = 3
                        key_to_remove = key
                del inventory[key_to_remove]
                print('got to here')
                if level_changing_to == 1:
                    irrigation_sprite_bottom = Irrigation_Bottom((-32,0), 1)
                    overworld_sprites.add(irrigation_sprite_bottom, layer=2)
                    tileset_group.add(irrigation_sprite_bottom)
                    tileset_group.tiles_list.append(irrigation_sprite_bottom)
                    irrigation_sprite_top = Irrigation_Top((-32,-32), 1)
                    overworld_sprites.add(irrigation_sprite_top, layer=5)
                    tileset_group.add(irrigation_sprite_top)
                    tileset_group.tiles_list.append(irrigation_sprite_top)
                    collison_map['row10'][9] = 4
                    collison_map['row10'][17] = 4
                    #collison_map['row14'][19] = 8
                else:
                    for item in tileset_group.tiles_list:
                        if isinstance(item, Irrigation_Bottom):
                            #print('instance')
                            #Change the sprite
                            item.change_level(level_changing_to)
                            overworld_sprites.add(item, layer = 2)
                        if isinstance(item, Irrigation_Top):
                            #print('instance')
                            #Change the sprite
                            item.change_level(level_changing_to)
                            overworld_sprites.add(item, layer = 5)
                irrigation_level = level_changing_to
                tileset_current = True
                
            if background.faded_out == False:
                background.handle_screen_fades(fade_fast=True)
            else:
                print('leave phase')
                background.kill()
                del background
                background = None
                enter_bought_irrigation_phase = False


def bought_windows_phase(pressed_keys):
    global overworld_sprites
    global background
    global inventory
    global tile_map
    global tileset_group
    global tileset_current
    global window_level
    global enter_bought_windows_phase
    if background == None:
        background = Black_Rectangle()
        overworld_sprites.add(background, layer = 12)
    else:
        if background.faded_in == False:
            background.handle_screen_fades(fade_fast=True)
        elif background.faded_in == True:
            if tileset_current == False:
                level_changing_to = 1
                for key in inventory:
                    if key == 'Windows Lv. 2':
                        print('change to windows level 2')
                        level_changing_to = 2
                        key_to_remove = key
                    elif key == 'Windows Lv. 3':
                        print('change to windows level 3')
                        level_changing_to = 3
                        key_to_remove = key
                del inventory[key_to_remove]
                print('got to here')
                if level_changing_to == 2:
                    for tile in tileset_group.tiles_list:
                        if isinstance(tile, Tile):
                            if tile.tile_number == 4:
                                #print('found 4')
                                tile.change_tile(412)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 0:
                                print(tile.rect)
                                if tile.rect.x == 112 or tile.rect.x == -48 or tile.rect.y == -48:
                                    tile.change_tile(10)
                                    overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 12:
                                tile.change_tile(1212)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 13:
                                tile.change_tile(1312)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 14:
                                tile.change_tile(1412)
                                overworld_sprites.add(tile, layer =1)
                elif level_changing_to == 3:
                    for tile in tileset_group.tiles_list:
                        if isinstance(tile, Tile):
                            #print('instance')
                            if tile.tile_number == 412:
                                #print('found 4')
                                tile.change_tile(413)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 0:
                                tile.change_tile(10)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 1212:
                                tile.change_tile(1213)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 1312:
                                tile.change_tile(1313)
                                overworld_sprites.add(tile, layer =1)
                            elif tile.tile_number == 1412:
                                tile.change_tile(1413)
                                overworld_sprites.add(tile, layer =1)
                window_level = level_changing_to
                tileset_current = True
                
            if background.faded_out == False:
                background.handle_screen_fades(fade_fast=True)
            else:
                print('leave phase')
                background.kill()
                del background
                background = None
                enter_bought_windows_phase = False

def check_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global curr_text_added
    global curr_text
    global curr_option_box
    global curr_text_box
    global in_menu
    global enter_check_phase
    global planters
    global enter_status_phase
    print('in check phase')
    curr_row = overworld_player_sprite.interaction_tile_row
    curr_row_str = f"row{curr_row}"
    curr_column = overworld_player_sprite.interaction_tile_column
    if planters[curr_row_str][curr_column].has_plant == False:
        if curr_text_added == False:
            curr_text_box = Overworld_Main_Text_box()
            overworld_sprites.add(curr_text_box, layer=9)
            if planters[curr_row_str][curr_column].dirt == 'regular':
                curr_text = Regular_Font_Line(input_string=f'Ordinary dirt waiting patiently for a plant.', text_type='arrow')
            elif planters[curr_row_str][curr_column].dirt == 'Cosmic':
                curr_text = Regular_Font_Line(input_string=f'Cosmic dirt pulling in otherworldy power.', text_type='arrow')
            elif planters[curr_row_str][curr_column].dirt == 'Diamond':
                curr_text = Regular_Font_Line(input_string=f"Diamond dirt. It won't scatter your sorrow to the heartless sea.", text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text_added = True
        if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
            curr_text.update(pressed_keys)
        if curr_text.ready_for_removal:
            curr_text.update()
            for sprite in curr_text:
                sprite.kill()
                del sprite
            del curr_text
            curr_text = None
            clear_text()
            curr_text_box.kill()
            del curr_text_box
            curr_text_box = None
            curr_option_box = None
            enter_check_phase = False
            in_menu = False
            overworld_player_sprite.interacting = False
            overworld_player_sprite.entry_delay = 15
    else:
        print('plant - go to status screen')
        enter_check_phase = False
        enter_status_phase = True

def status_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global curr_option_box
    global in_menu
    global planters
    global enter_status_phase
    print('in status phase')
    if curr_option_box == None:
        curr_row = overworld_player_sprite.interaction_tile_row
        curr_row_str = f"row{curr_row}"
        curr_column = overworld_player_sprite.interaction_tile_column
        curr_option_box = Overworld_Status_Screen_Group(planters[curr_row_str][curr_column].specific_plant_object)
        overworld_sprites.add(curr_option_box, layer=9)
    curr_option_box.update(pressed_keys)
    if curr_option_box.ready_for_removal == False:
        for sprite in curr_option_box:
            if sprite not in overworld_sprites:
                overworld_sprites.add(sprite, layer = 9)
    else:
        for sprite in curr_option_box:
            sprite.kill()
            del sprite
        del curr_option_box
        curr_option_box = None
        in_menu = False
        overworld_player_sprite.interacting = False
        overworld_player_sprite.entry_delay = 15
        enter_status_phase = False

def day_to_dusk_transition_phase(pressed_keys):
    global overworld_sprites
    global curr_option_box
    global enter_day_to_dusk_transition_phase
    global background
    global enter_dusk_stat_increase_phase
    #print('in day to night transition phase')
    if background == None:
        background = Dusk_Transition_Screen()
        overworld_sprites.add(background, layer=7)
    #if not (curr_option_box.faded_in == True and curr_option_box.faded_out == True):
    if not background.faded_in == True:
        background.handle_screen_fades()
        
    else:
        enter_day_to_dusk_transition_phase = False
        enter_dusk_stat_increase_phase = True
        print('go to next phase')

def dusk_stat_increase_phase(pressed_keys):
    global overworld_sprites
    global plants
    global curr_option_box
    global curr_text_box
    global curr_text_added
    global curr_text
    global window_level
    global irrigation_level
    global generator_level
    global enter_dusk_stat_increase_phase
    global enter_day_to_night_transition_phase
    global background
    global current_plant_stat_changing
    global planters
    global dirt_move_dict
    global move_to_learn
    global dirt_enabling_new_move
    if curr_text_added == False:
        music_channel.play(clock_music_sound, loops=-1)
        background.kill()
        del background
        background = None
        background = Dusk_Background()
        overworld_sprites.add(background, layer=7)
        curr_option_box = Overworld_Status_Screen_Group(plants[current_plant_stat_changing])
        overworld_sprites.add(curr_option_box, layer=8)
        curr_text_box = Overworld_Main_Text_box()
        overworld_sprites.add(curr_text_box, layer=9)
        curr_text = Regular_Font_Line(input_string=f'The {plants[current_plant_stat_changing].species_name} grew throughout the day!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
        if len(plants[current_plant_stat_changing].attacks) != 3:
            print('space for attacks')
            for planter_row in planters:
                for planter in planters[planter_row]:
                    if planter != None:
                        #print(planter)
                        if planter.has_plant:
                            print(planter.specific_plant_object)
                            if planter.specific_plant_object == plants[current_plant_stat_changing]:
                                print('found the right plant')
                                if planter.dirt != 'regular':
                                    print(dirt_move_dict)
                                    possible_new_move = dirt_move_dict[planter.dirt]
                                    name_list = []
                                    for attack in plants[current_plant_stat_changing].attacks:
                                        name_list.append(attack.name)
                                    print(name_list)
                                    print(possible_new_move.name)
                                    if possible_new_move.name not in name_list:
                                        print('gonna learn it')
                                        #move_to_learn = copy.deepcopy(possible_new_move)
                                        #dirt_enabling_new_move = copy.deepcopy(planter.dirt)
                                        move_to_learn = possible_new_move
                                        dirt_enabling_new_move = planter.dirt
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True:
        #First, increase the current plant's current hp by 5 if the plant's HP is less than the max hp
        #Then, increase the plant's max hp and max defense by 5 at windows level 1, 10 at windows level 2, and 20 at windows level 3
        #Then, increase the plant's max speed and max attack by 5 at irrigation level 1, 10 at irrigation level 2, and 20 at irrigation level 3
        #Then, increase the plant's max special attack and max special defense by 5 at battery level 1, 10 at battery level 2, and 20 at battery level 3
        #Then, learn a new move if the dirt allows it
        #Then move onto the next plant
        
        if curr_text.input_string_top == f'The {plants[current_plant_stat_changing].species_name} grew ' and plants[current_plant_stat_changing].current_hp != plants[current_plant_stat_changing].max_hp:
            plants[current_plant_stat_changing].current_hp += 5
            if plants[current_plant_stat_changing].current_hp > plants[current_plant_stat_changing].max_hp:
                plants[current_plant_stat_changing].current_hp = plants[current_plant_stat_changing].max_hp
            curr_text.set_letters(f'The {plants[current_plant_stat_changing].species_name} recovered some HP!', text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
            curr_option_box.change_status()
            for sprite in curr_option_box:
                if sprite not in overworld_sprites:
                    overworld_sprites.add(sprite, layer = 9)
        elif curr_text.input_string_top == f'The {plants[current_plant_stat_changing].species_name} grew ' or curr_text.input_string_top == f'The {plants[current_plant_stat_changing].species_name} recovered':
            plants[current_plant_stat_changing].max_hp += (5 * window_level)
            plants[current_plant_stat_changing].current_hp += (5 * window_level)
            plants[current_plant_stat_changing].defense += (5 * window_level)
            curr_text.set_letters(f"The sunlight grew the {plants[current_plant_stat_changing].species_name}'s HP and DEF!", text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
            curr_option_box.change_status()
            for sprite in curr_option_box:
                if sprite not in overworld_sprites:
                    overworld_sprites.add(sprite, layer = 9)
        elif curr_text.input_string_top == 'The sunlight grew the ' and irrigation_level != 0:
            plants[current_plant_stat_changing].speed += (5 * window_level)
            plants[current_plant_stat_changing].attack += (5 * window_level)
            curr_text.set_letters(f"The water grew the {plants[current_plant_stat_changing].species_name}'s ATK and SPD!", text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
            curr_option_box.change_status()
            for sprite in curr_option_box:
                if sprite not in overworld_sprites:
                    overworld_sprites.add(sprite, layer = 9)
        elif (curr_text.input_string_top == 'The sunlight grew the ' or curr_text.input_string_top == 'The water grew the ') and generator_level != 0:
            plants[current_plant_stat_changing].special_attack += (5 * window_level)
            plants[current_plant_stat_changing].special_defense += (5 * window_level)
            curr_text.set_letters(f"The electricity grew the {plants[current_plant_stat_changing].species_name}'s Special Stats!", text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
            curr_option_box.change_status()
            for sprite in curr_option_box:
                if sprite not in overworld_sprites:
                    overworld_sprites.add(sprite, layer = 9)
        elif move_to_learn != None:
            plants[current_plant_stat_changing].attacks.append(move_to_learn)
            curr_text.set_letters(f"The {dirt_enabling_new_move} Dirt gave the {plants[current_plant_stat_changing].species_name} power!", text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
            curr_option_box.change_moves()
            for sprite in curr_option_box:
                if sprite not in overworld_sprites:
                    overworld_sprites.add(sprite, layer = 9)
            move_to_learn = None
            dirt_enabling_new_move = None
        else:
            current_plant_stat_changing += 1
            for sprite in curr_text:
                sprite.kill()
                del sprite
            del curr_text
            curr_text = None
            

            for sprite in curr_option_box:
                sprite.kill()
                del sprite
            del curr_option_box
            curr_option_box = None
            curr_text_box.kill()
            del curr_text_box
            curr_text_box = None
            clear_text()
            if current_plant_stat_changing != len(plants):
                curr_option_box = Overworld_Status_Screen_Group(plants[current_plant_stat_changing])
                overworld_sprites.add(curr_option_box, layer=8)
                curr_text_box = Overworld_Main_Text_box()
                overworld_sprites.add(curr_text_box, layer=9)
                curr_text = Regular_Font_Line(input_string=f'The {plants[current_plant_stat_changing].species_name} grew throughout the day!', text_type='arrow')
                for sprite in curr_text:
                    overworld_sprites.add(sprite, layer=9)
                curr_text_added = True
                if len(plants[current_plant_stat_changing].attacks) != 3:
                    print('space for attacks')
                    for planter_row in planters:
                        for planter in planters[planter_row]:
                            if planter != None:
                                #print(planter)
                                if planter.has_plant:
                                    print(planter.specific_plant_object)
                                    if planter.specific_plant_object == plants[current_plant_stat_changing]:
                                        print('found the right plant')
                                        if planter.dirt != 'regular':
                                            print(dirt_move_dict)
                                            possible_new_move = dirt_move_dict[planter.dirt]
                                            name_list = []
                                            for attack in plants[current_plant_stat_changing].attacks:
                                                name_list.append(attack.name)
                                            print(name_list)
                                            print(possible_new_move.name)
                                            if possible_new_move.name not in name_list:
                                                print('gonna learn it')
                                                move_to_learn = copy.deepcopy(possible_new_move)
                                                dirt_enabling_new_move = copy.deepcopy(planter.dirt)
            else:
                print('go to night transition phase phase')
                current_plant_stat_changing = 0
                enter_dusk_stat_increase_phase = False
                enter_day_to_night_transition_phase = True

#Clean up resumes here
def day_to_night_transition_phase(pressed_keys):
    global overworld_sprites
    global curr_option_box
    global enter_day_to_night_transition_phase
    global enter_enemies_approaching_phase
    global background
    #print('in day to night transition phase')
    if curr_option_box == None:
        curr_option_box = Night_Transition_Screen()
        overworld_sprites.add(curr_option_box, layer=7)
    #if not (curr_option_box.faded_in == True and curr_option_box.faded_out == True):
    if not curr_option_box.faded_in == True:
        curr_option_box.handle_screen_fades()
        
    else:
        background.kill()
        del background
        background = None
        enter_day_to_night_transition_phase = False
        enter_enemies_approaching_phase = True
        print('go to next phase')

def enemies_approaching_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global curr_text_added
    global curr_text
    global curr_option_box
    global curr_text_box
    global in_menu
    global enter_check_phase
    global enter_enemies_approaching_phase
    global battle_background
    global curr_opponent_sprite
    global curr_enemy_platform
    global curr_hero_platform
    global enter_enemy_and_enemies_left_phase
    global enemies_list
    global in_battle_time_box
    if curr_text_added == False:
        # Play the sound in the channel with loops=-1 for infinite looping
        music_channel.play(battle_music_sound, loops=-1)
        curr_text_box = Overworld_Main_Text_box()
        overworld_sprites.add(curr_text_box, layer=8)
        curr_text = Regular_Font_Line(input_string=f'Animals snuck into the greenhouse! They attack the plants!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
        battle_background = Battle_Background()
        overworld_sprites.add(battle_background, layer=6)
        curr_opponent_sprite = Opponent_Sprite(enemies_list[0].species_name)
        curr_enemy_platform = Enemy_Platform()
        curr_hero_platform = Hero_Platform()
        overworld_sprites.add(curr_enemy_platform, layer=7)
        overworld_sprites.add(curr_hero_platform, layer=7)
        overworld_sprites.add(curr_opponent_sprite, layer=8)
    if curr_option_box != None:
        curr_option_box.handle_screen_fades()
    if curr_enemy_platform.rect.topright != (240, 52):
        curr_enemy_platform.move_horizontal(move_speed=4, stopping_point=(240, 52))
    if curr_hero_platform.rect.topright != (128, 104):
        curr_hero_platform.move_horizontal(move_speed=-4, stopping_point=(128, 104))
    if curr_opponent_sprite.rect.topright != (208, 12):
        curr_opponent_sprite.move_horizontal(move_speed=4, stopping_point=(208, 12))
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True and curr_enemy_platform.rect.topright == (240, 52):
        print('go to enter enemy and enemies left phase')
        enter_enemies_approaching_phase = False
        enter_enemy_and_enemies_left_phase = True
        in_battle_time_box = In_Battle_Time_Box()
        for sprite in in_battle_time_box:
            overworld_sprites.add(sprite, layer=9)
        curr_option_box.kill()
        del curr_option_box
        curr_option_box = None
        for sprite in curr_text:
            sprite.kill()
            del sprite
        del curr_text
        curr_text = None
        clear_text()

def refresh_enemies_phase(pressed_keys):
    global enter_enemy_and_enemies_left_phase
    global enemies_list
    global enter_refresh_enemies_phase
    global curr_opponent_sprite
    global overworld_sprites
    if curr_opponent_sprite == None:
        curr_opponent_sprite = Opponent_Sprite(enemies_list[0].species_name)
        overworld_sprites.add(curr_opponent_sprite, layer=7)
    if curr_opponent_sprite.rect.topright != (208, 12):
        curr_opponent_sprite.move_horizontal(move_speed=4, stopping_point=(208, 12))
    else:
        enter_refresh_enemies_phase = False
        enter_enemy_and_enemies_left_phase = True

def enemy_and_enemies_left_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global enter_enemy_and_enemies_left_phase
    global enter_plant_send_out_phase
    global curr_enemy_status_bar
    global enemies_list
    global curr_option_box
    global first_enemy
    global plant_already_added
    global enter_select_move_phase
    #print('enemy and enemies left phase')
    if curr_text_added == False:
        curr_option_box = None
        if first_enemy == True:
            curr_text = Regular_Font_Line(input_string=f'The first enemy is a {enemies_list[0].species_name}!', text_type='arrow')
            first_enemy = False
        else:
            curr_text = Regular_Font_Line(input_string=f'The next enemy is a {enemies_list[0].species_name}!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
        curr_enemy_status_bar = Opponent_Status_Bar(f'{enemies_list[0].species_name}', level=5, curr_hp=enemies_list[0].current_hp, full_hp=enemies_list[0].max_hp)
        overworld_sprites.add(curr_enemy_status_bar, layer = 9)
    if curr_enemy_status_bar.rect.topright != (112, 16):
        curr_enemy_status_bar.move_horizontal(move_speed=4, stopping_point=(112, 16))
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True:
        if curr_text.input_string_top == 'The first enemy is a' or curr_text.input_string_top == 'The next enemy is a':
            if len(enemies_list) == 1:
                curr_text.set_letters('This is the final enemy! Defeat it to be safe for the night!', text_type='arrow')
            elif len(enemies_list) == 2:
                curr_text.set_letters('There seems to be another enemy waiting in the dark.', text_type='arrow')
            else:
                curr_text.set_letters('There seems to be more enemies readying up to approach.', text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
        else:
            if curr_enemy_status_bar.rect.topright == (112, 16):
                print('go to enter plant phase')
                enter_enemy_and_enemies_left_phase = False
                for sprite in curr_text:
                    sprite.kill()
                    del sprite
                del curr_text
                curr_text = None
                clear_text()
                if plant_already_added == True:
                    enter_select_move_phase = True
                else:
                    enter_plant_send_out_phase = True

def plant_send_out_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global plant_sprites
    global plants
    global enter_plant_send_out_phase
    global curr_player_plant_sprite
    global curr_hero_status_bar
    global enter_select_move_phase
    global faint_fixer
    global plant_already_added
    global first_plant
    global faint_fixer_placed
    if curr_text_added == False:
        if first_plant:
            curr_text = Regular_Font_Line(input_string=f'{plants[0].species_name} defends first!', text_type='not_arrow')
            first_plant = False
        else:
            curr_text = Regular_Font_Line(input_string=f'{plants[0].species_name} defends next!', text_type='not_arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
        curr_player_plant_sprite = Player_Plant_Sprite(plants[0].species_name)
        overworld_sprites.add(curr_player_plant_sprite, layer=8)
        curr_hero_status_bar = Hero_Status_Bar(plants[0].species_name, level=5, curr_hp=plants[0].current_hp, full_hp=plants[0].max_hp)
        overworld_sprites.add(curr_hero_status_bar, layer = 9)
        if not faint_fixer_placed:
            faint_fixer = Faint_Fixer()
            overworld_sprites.add(faint_fixer, layer = 9)
            faint_fixer_placed = True
    
    curr_text.update()
    
    if curr_text.all_letters_set == True:
        curr_player_plant_sprite.battle_entrance_animation()
        if curr_hero_status_bar.rect.topright != (228, 82):
            curr_hero_status_bar.move_horizontal(move_speed=-4, stopping_point=(228, 82))
        else:
            curr_text.ready_for_removal = True
            curr_text.update()
            print('go to select move phase')
            enter_plant_send_out_phase = False
            enter_select_move_phase = True
            for sprite in curr_text:
                sprite.kill()
                del sprite
            del curr_text
            curr_text = None
            clear_text()
            plant_already_added = True

def select_move_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global plant_sprites
    global curr_player_plant_sprite
    global curr_hero_status_bar
    global enter_select_move_phase
    global select_move_group
    global move_selected
    global enemies_list
    global current_battle_steps
    global enter_animate_moves_phase
    global sfx_channel
    global enter_midbattle_status_phase
    #print('in select move phase')
    if not curr_player_plant_sprite.entered_battle:
        curr_player_plant_sprite.battle_entrance_animation()
    if select_move_group == None:
        if curr_text_box != None:
            curr_text_box.kill()
            del curr_text_box
            curr_text_box = None
        # Set default values for moves if there are fewer than 4 attacks
        move1 = plants[0].attacks[0].short_name 
        move1_currpp = plants[0].attacks[0].power
        move1type = plants[0].attacks[0].type

        move2 = plants[0].attacks[1].short_name if len(plants[0].attacks) > 1 else None
        move2_currpp = plants[0].attacks[1].power if len(plants[0].attacks) > 1 else None
        move2type = plants[0].attacks[1].type if len(plants[0].attacks) > 1 else None

        move3 = plants[0].attacks[2].short_name if len(plants[0].attacks) > 2 else None
        move3_currpp = plants[0].attacks[2].power if len(plants[0].attacks) > 2 else None
        move3type = plants[0].attacks[2].type if len(plants[0].attacks) > 2 else None

        # If there are fewer than 4 moves, we use 'Status' as move4
        move4 = 'Status'
        move4_currpp = 0
        move4type = 'STATUS'

        # Now use these variables in the Select_Move_Group constructor
        select_move_group = Select_Move_Group(
            move1=move1, move1_currpp=move1_currpp, move1type=move1type,
            move2=move2, move2_currpp=move2_currpp, move2type=move2type,
            move3=move3, move3_currpp=move3_currpp, move3type=move3type,
            move4=move4, move4_currpp=move4_currpp, move4type=move4type
        )      
        print(f"player current hp: {plants[0].current_hp}")
        print(f"opponent current hp: {enemies_list[0].current_hp}")
        for sprite in select_move_group:
            overworld_sprites.add(sprite, layer=9)
    else:
        curr_player_plant_sprite.waiting()
        if select_move_group.final_selection == None:
            select_move_group.update(pressed_keys)
        else:
            for item in select_move_group:
                item.kill()
                del item
            clear_text()
            move_selected = select_move_group.final_selection
            print('move selected is')
            print(move_selected)
            if move_selected > len(plants[0].attacks):
                print('status selected')
                enter_select_move_phase = False
                enter_midbattle_status_phase = True
                select_move_group = None
            else:
                print(f"{plants[0].species_name} current hp: {plants[0].current_hp}")
                print(f"{enemies_list[0].species_name} current hp: {enemies_list[0].current_hp}")
                battle_steps = movePhase(plants[0], enemies_list[0], enemies_list[0].attacks[0], plants[0].attacks[int(move_selected) - 1])#opponent attack is hardcoded, pokemon are hardcoded, needs to change
                print(battle_steps)
                print(f'len of battle_steps: {len(battle_steps)}')
                print(f"player current hp: {plants[0].current_hp}")
                print(f"opponent current hp: {enemies_list[0].current_hp}")
                current_battle_steps = battle_steps
                enter_select_move_phase = False
                enter_animate_moves_phase = True
                select_move_group = None


def midbattle_status_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global curr_text_added
    global curr_text
    global curr_option_box
    global curr_text_box
    global in_menu
    global enter_check_phase
    global enter_midbattle_status_phase
    global enter_select_move_phase
    global plants
    print('in midbattle status phase')
    if curr_option_box == None:
        curr_option_box = Overworld_Status_Screen_Group(plants[0])
        overworld_sprites.add(curr_option_box, layer=10)
    curr_option_box.update(pressed_keys)
    if curr_option_box.ready_for_removal == False:
        for sprite in curr_option_box:
            if sprite not in overworld_sprites:
                overworld_sprites.add(sprite, layer = 10)
    else:
        for sprite in curr_option_box:
            sprite.kill()
            del sprite
        del curr_option_box
        curr_option_box = None
        enter_midbattle_status_phase = False
        enter_select_move_phase = True


def animate_move_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global plant_sprites
    global curr_player_plant_sprite
    global curr_hero_status_bar
    global enter_select_move_phase
    global select_move_group
    global move_selected
    global enemies_list
    global current_battle_steps
    global enter_animate_moves_phase
    global ending_turn
    global sfx_channel
    global waiting_to_read
    global faint_played
    global is_player
    global enter_opponent_fainted_phase
    global enter_player_fainted_phase
    global in_battle_time_box
    global enter_all_turns_done_phase
    global curr_enemy_status_bar
    #print('in animate move phase')
    if current_battle_steps[0][0] != 'FINAL':
        if curr_text_added == False:
            if curr_text_box != None:
                curr_text_box.kill()
                del curr_text_box
                curr_text_box = None
            curr_text_box = Overworld_Main_Text_box()
            overworld_sprites.add(curr_text_box, layer=8)
            print(current_battle_steps[0])
            curr_print_name = current_battle_steps[0][0].species_name
            curr_attack_name = current_battle_steps[0][2].name
            curr_damage = current_battle_steps[0][3]
            if current_battle_steps[0][0] == plants[0]:
                print('yes player')
                is_player = True
                if curr_damage != 0:
                    curr_opponent_sprite.taking_damage = True
                    curr_text = Regular_Font_Line(input_string=f'{curr_print_name} used {curr_attack_name}!', text_type='not_arrow')
                    damage_sound()
                    curr_enemy_status_bar.updating_hp = True
                else:
                    curr_text = Regular_Font_Line(input_string=f"{curr_print_name}'s attack missed!", text_type='not_arrow')
            else:
                print('no player')
                is_player = False
                if curr_damage != 0:
                    curr_player_plant_sprite.taking_damage = True
                    curr_text = Regular_Font_Line(input_string=f'Foe {curr_print_name} used {curr_attack_name}!', text_type='not_arrow')
                    damage_sound()
                    curr_hero_status_bar.updating_hp = True
                else:
                    curr_text = Regular_Font_Line(input_string=f"Foe {curr_print_name}'s attack missed!", text_type='not_arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text_added = True
        curr_text.update()
        if curr_player_plant_sprite.taking_damage == True:
            curr_player_plant_sprite.take_damage()
        if curr_opponent_sprite.taking_damage == True:
            curr_opponent_sprite.take_damage()
        if curr_hero_status_bar.updating_hp == True:
            curr_hero_status_bar.change_hp(plants[0].current_hp)
        if curr_enemy_status_bar.updating_hp == True:
            curr_enemy_status_bar.change_hp(enemies_list[0].current_hp)
        if curr_text.all_letters_set == True and curr_player_plant_sprite.taking_damage == False and curr_opponent_sprite.taking_damage == False and curr_hero_status_bar.updating_hp == False and curr_enemy_status_bar.updating_hp == False and ending_turn == False:
            if   plants[0].is_fainted() and not is_player:
                print('hero fainted')
                curr_player_plant_sprite.fainting = True
            elif enemies_list[0].is_fainted() and is_player:
                print('opponent fainted')
                curr_opponent_sprite.fainting = True
            ending_turn = True

        if ending_turn:
            if faint_played == False:
                if curr_opponent_sprite.fainting == True or curr_player_plant_sprite.fainting == True:
                    #if not sfx_channel.get_busy():
                    print('got to faint sound here')
                    faint_sound()
                    faint_played = True
                else:
                    faint_played = True
            elif faint_played == True:
                if curr_opponent_sprite.fainting == True:
                    curr_opponent_sprite.faint()
                elif curr_player_plant_sprite.fainting == True:
                    curr_player_plant_sprite.faint()
                else:     
                    if waiting_to_read == 29:
                        print('in this loop')
                        curr_text.ready_for_removal = True
                        curr_text.update()
                        for sprite in curr_text:
                            sprite.kill()
                            del sprite
                        del curr_text
                        curr_text = None
                        clear_text()
                        current_battle_steps = current_battle_steps[1:]
                        waiting_to_read = 0
                        ending_turn = False
                        faint_played = False
                        if enemies_list[0].is_fainted() and is_player:
                            print('what the heck')
                            curr_enemy_status_bar.kill()
                            del curr_enemy_status_bar
                            curr_enemy_status_bar = None
                        elif plants[0].is_fainted() and not is_player:
                            print('what the heck')
                            curr_hero_status_bar.kill()
                            del curr_hero_status_bar
                            curr_hero_status_bar = None
                    else:
                        print('not in loop')
                        waiting_to_read += 1
    else:
        in_battle_time_box.time += 1
        print('done with battle steps')
        move_selected = None
        clear_text()
        current_battle_steps = None
        faint_played = False
        if enemies_list[0].is_fainted():
            print('enter opponent fainted phase')
            enter_animate_moves_phase = False
            enter_opponent_fainted_phase = True
        elif plants[0].is_fainted():
            enter_animate_moves_phase = False
            enter_player_fainted_phase = True
        else:
            if in_battle_time_box.time != 17:
                in_battle_time_box.change_time()
                for sprite in in_battle_time_box:
                    if sprite not in overworld_sprites:
                        overworld_sprites.add(sprite, layer = 9)
                enter_animate_moves_phase = False
                enter_select_move_phase = True
            else:
                enter_animate_moves_phase = False
                enter_all_turns_done_phase = True

def opponent_fainted_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global enemies_list
    global enter_opponent_fainted_phase
    global enter_gain_money_phase
    if curr_text_added == False:
        curr_text = Regular_Font_Line(input_string=f'{enemies_list[0].species_name} has been defeated!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True:
        for sprite in curr_text:
            sprite.kill()
            del sprite
        del curr_text
        curr_text = None
        clear_text()
        print('Ready for next phase')
        enter_opponent_fainted_phase = False
        enter_gain_money_phase = True

def player_fainted_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global plants
    global enter_player_fainted_phase
    global curr_player_plant_sprite
    global enter_plant_send_out_phase
    global planters
    global enter_game_over_phase
    global in_battle_time_box
    global enter_all_turns_done_phase
    if curr_text_added == False:
        curr_player_plant_sprite.kill()
        del curr_player_plant_sprite
        curr_player_plant_sprite = None
        curr_text = Regular_Font_Line(input_string=f'{plants[0].species_name} has been defeated!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
        curr_plant = plants[0]
        for planter_row in planters:
            for planter in planters[planter_row]:
                if planter != None:
                    print(planter)
                    if planter.has_plant:
                        if planter.specific_plant_object == curr_plant:
                            print('match')
                            planter.plant.kill()
                            del planter.plant
                            planter.plant = None
                            planter.specific_plant_object = None
                            planter.has_plant = False
        plants = plants[1:]
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True:
        for sprite in curr_text:
            sprite.kill()
            del sprite
        del curr_text
        curr_text = None
        clear_text()
        print('Ready for next phase')
        enter_player_fainted_phase = False
        if plants == []:
            print('go to gameover')
            enter_game_over_phase = True
        else:
            #Check time
            if in_battle_time_box.time != 17:
                in_battle_time_box.change_time()
                for sprite in in_battle_time_box:
                    if sprite not in overworld_sprites:
                        overworld_sprites.add(sprite, layer = 9)
                print('go to next plant')
                enter_plant_send_out_phase = True
            else:
                enter_all_turns_done_phase = True


def game_over_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_option_box
    global initialized
    global enter_game_over_phase
    if curr_text_added == False:
        curr_text = Regular_Font_Line(input_string='All your plants are dead! You have failed as a farmer!', text_type='not_arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
    
    curr_text.update()
    
    if curr_text.all_letters_set == True:
        print('game over screen fade in')
        if curr_option_box == None:
            print('got to night to day phase')
            curr_option_box = Game_Over_Screen()
            overworld_sprites.add(curr_option_box, layer=10)
        else:
            if not curr_option_box.faded_in == True:
                curr_option_box.handle_screen_fades()
            else:
                if pressed_keys != None:
                    if pressed_keys[K_RETURN]:
                        for sprite in overworld_sprites:
                            sprite.kill()
                            del sprite
                        enter_game_over_phase = False
                        initialized = False


def gain_money_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global enemies_list
    global enter_gain_money_phase
    global enter_all_enemies_defeated_phase
    global money
    global in_battle_money_box
    global in_battle_time_box
    global money_changed
    global enter_refresh_enemies_phase
    global curr_opponent_sprite
    global enter_all_turns_done_phase
    if curr_text_added == False:
        curr_opponent_sprite.kill()
        del curr_opponent_sprite
        curr_opponent_sprite = None
        in_battle_money_box = In_Battle_Money_Box()
        for sprite in in_battle_money_box:
            overworld_sprites.add(sprite, layer=9)
        print(f"{money} before additon")
        money += enemies_list[0].money_dropped
        print(f"{money} after additon")
        curr_text = Regular_Font_Line(input_string=f'You gained ${enemies_list[0].money_dropped} for defeating the {enemies_list[0].species_name}!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.is_arrow_on_screen == True and money_changed == False:
        print('update the money')
        in_battle_money_box.change_money()
        for sprite in in_battle_money_box:
            if sprite not in overworld_sprites:
                overworld_sprites.add(sprite, layer = 9)
        money_changed = True
    if curr_text.ready_for_removal == True:
        #Do exp moving step then clear text
        enemies_list = enemies_list[1:]
        for sprite in curr_text:
            sprite.kill()
            del sprite
        del curr_text
        curr_text = None
        clear_text()
        if enemies_list == []:
            print('go to all enemies defeated step')
            enter_all_enemies_defeated_phase = True
        else:
            #Check time
            if in_battle_time_box.time != 17:
                in_battle_time_box.change_time()
                for sprite in in_battle_time_box:
                    if sprite not in overworld_sprites:
                        overworld_sprites.add(sprite, layer = 9)
                print('go to refresh enemy step')
                
                enter_refresh_enemies_phase = True
            else:
                enter_all_turns_done_phase = True
        enter_gain_money_phase = False
        for sprite in in_battle_money_box:
            sprite.kill()
            del sprite
        del in_battle_money_box
        in_battle_money_box = None
        money_changed = False


def all_enemies_defeated_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global enemies_list
    global enter_all_enemies_defeated_phase
    global enter_night_to_day_transition_phase
    global all_battle_sprites_killed
    global first_enemy
    global plant_already_added
    global faint_fixer_placed
    global first_plant
    if curr_text_added == False:
        all_battle_sprites_killed = False
        print('got in all enemies defeated phase')
        curr_text = Regular_Font_Line(input_string=f'All enemies defeated! You survived the night!', text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True:
        for sprite in curr_text:
            sprite.kill()
            del sprite
        del curr_text
        curr_text = None
        clear_text()
        print('Ready for next phase')
        faint_fixer_placed = False
        enter_all_enemies_defeated_phase = False
        enter_night_to_day_transition_phase = True
        first_enemy = True
        first_plant = True
        plant_already_added = False

def all_turns_done_phase(pressed_keys):
    global overworld_sprites
    global curr_text_added
    global curr_text
    global curr_text_box
    global enemies_list
    global enter_all_turns_done_phase
    global enter_night_to_day_transition_phase
    global all_battle_sprites_killed
    global first_enemy
    global plant_already_added
    global faint_fixer_placed
    global first_plant
    global in_battle_time_box
    if curr_text_added == False:
        in_battle_time_box.change_time()
        for sprite in in_battle_time_box:
            if sprite not in overworld_sprites:
                overworld_sprites.add(sprite, layer = 9)
        all_battle_sprites_killed = False
        print('got in all enemies defeated phase')
        curr_text = Regular_Font_Line(input_string="It's 5 AM! You survived the night!", text_type='arrow')
        for sprite in curr_text:
            overworld_sprites.add(sprite, layer=9)
        curr_text_added = True
    if curr_text.all_letters_set == False or curr_text.is_arrow_on_screen == True:
        curr_text.update(pressed_keys)
    if curr_text.ready_for_removal == True:
        if curr_text.input_string_top == "It's 5 AM! You survived":
            curr_text.set_letters('The enemies retreated!', text_type='arrow')
            for sprite in curr_text:
                overworld_sprites.add(sprite, layer=9)
            curr_text.update(pressed_keys)
        else:
            for sprite in curr_text:
                sprite.kill()
                del sprite
            del curr_text
            curr_text = None
            clear_text()
            print('Ready for next phase')
            faint_fixer_placed = False
            enter_all_turns_done_phase = False
            enter_night_to_day_transition_phase = True
            first_enemy = True
            first_plant = True
            plant_already_added = False
    
        
def refresh_for_next_day():
    global day
    global enemies_list
    global purchase_list
    global irrigation_level
    global generator_level
    global window_level
    global diamond_dirt_bought_once
    global species_objects
    global attack_objects
    day += 1
    for enemy in enemies_list:
        del enemy
    enemies_list = []
    #DAY 1
    
    if day == 1:
        #Three base flowers, three of each but only enough money for 3 flowers
        purchase_list = {'Sunflower Seed': [3, 3, 'Fast growing flower that uses solar power in battle.', 'plant', 'Sunflower'],
                    'Rose Seed': [3, 3, 'Fast growing flower that uses beauty power in battle.', 'plant', 'Rose'],
                    'Blue Tulip Seed': [3, 3, 'Fast growing flower that uses enchanted power in battle.', 'plant', 'Blue Tulip']}
        #Two basic bunny enemies, regular and brown
        rabbit1 = Specific_Plant(species=species_objects['rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
        rabbit2 = Specific_Plant(species=species_objects['brown_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
        enemies_list = [rabbit1, rabbit2]
    
    #DAY 2
    if day == 2:
        #Irrigation and batteries unlock, cost 10
        print()
        purchase_list['Irrigation Lv.1'] = [10, 1, 'Waters the plants, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        purchase_list['Generator Lv.1'] = [10, 1, 'Supplies the plants with power, raising Special Attack and Defense.', 'generator', 'Generator Lv.1']
        #Three bunny enemies, one is high level-gray, beige, blue
        rabbit1 = Specific_Plant(species=species_objects['gray_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
        rabbit2 = Specific_Plant(species=species_objects['dark_gray_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
        rabbit3 = Specific_Plant(species=species_objects['blue_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                       defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['mysterious_nibble']])
        enemies_list = [rabbit1, rabbit2, rabbit3]
    #DAY 3
    if day == 3:
        #Windows Level 2 unlocks, first dirt unlocks
        print()
        purchase_list['Windows Lv. 2'] = [20, 1, 'Catches more sunlight, growing HP and Defense more.', 'windows', 'Windows Lv. 2']
        purchase_list['Cosmic Dirt'] = [6, 1, 'Space-faring dirt that provides Cosmic Power to plants.', 'dirt', 'Cosmic Dirt']
        #Three bunny enemies, light brown, dark blue, tiny
        rabbit1 = Specific_Plant(species=species_objects['light_brown_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
        rabbit2 = Specific_Plant(species=species_objects['dark_blue_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['mysterious_nibble']])
        rabbit3 = Specific_Plant(species=species_objects['tiny_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                       defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['critical_nibble']])
        enemies_list = [rabbit1, rabbit2, rabbit3]

    if day == 4:
        #Irrigation and batteries level 2 unlock if there's space
        if len(purchase_list.keys()) < 7:
            purchase_list['Irrigation Lv.2'] = [20, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        if len(purchase_list.keys()) < 7:
            purchase_list['Generator Lv.2'] = [20, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.2']
        #Three bunny enemies, light brown, dark blue, tiny
        rabbit1 = Specific_Plant(species=species_objects['mirror_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
        rabbit2 = Specific_Plant(species=species_objects['tiny_brown_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['critical_nibble']])
        rabbit3 = Specific_Plant(species=species_objects['waifu_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                       defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble_impact']])
        enemies_list = [rabbit1, rabbit2, rabbit3]

    if day == 5:
        #Add irrigation and batteries level 2 if there's spaces and they aren't unlocked
        if len(purchase_list.keys()) < 7 and irrigation_level < 2:
            purchase_list['Irrigation Lv.2'] = [20, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        if len(purchase_list.keys()) < 7 and generator_level < 2:
            purchase_list['Generator Lv.2'] = [20, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.2']
        #Diamond Dirt unlocks
        if len(purchase_list.keys()) < 7:
            purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
            diamond_dirt_bought_once = True
        #Three bunny enemies, light brown, dark blue, tiny
        rabbit1 = Specific_Plant(species=species_objects['missing_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['glitched_nibble']])
        rabbit2 = Specific_Plant(species=species_objects['punished_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['venom_nibble']])
        enemies_list = [rabbit1, rabbit2]

    
    #Five bunny enemies, all are high level
    if day == 6:
        #Add irrigation and batteries level 2 if there's spaces and they aren't unlocked
        if len(purchase_list.keys()) < 7 and irrigation_level < 2:
            purchase_list['Irrigation Lv.2'] = [20, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        if len(purchase_list.keys()) < 7 and generator_level < 2:
            purchase_list['Generator Lv.2'] = [20, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.2']
        #Diamond Dirt unlocks if not yet unlocked
        if len(purchase_list.keys()) < 7 and diamond_dirt_bought_once == False:
            purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
            diamond_dirt_bought_once = True
        if len(purchase_list.keys()) < 7:
            purchase_list['Windows Lv. 3'] = [40, 1, 'Catches even more sunlight, growing HP and DEF more.', 'windows', 'Windows Lv. 2']
        #Three bunny enemies, light brown, dark blue, tiny
        rabbit1 = Specific_Plant(species=species_objects['stolen_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['volt_nibble']])
        rabbit2 = Specific_Plant(species=species_objects['abstract_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['pretentious_nibble']])
        rabbit3 = Specific_Plant(species=species_objects['noided_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble_goes']])
        enemies_list = [rabbit1, rabbit2, rabbit3]


    #Day 7
    if day == 7:
        #Eras and filthy bunny
        #Add irrigation and batteries level 3 if not unlocked
        if len(purchase_list.keys()) < 7 and irrigation_level < 2:
            purchase_list['Irrigation Lv.2'] = [20, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        if len(purchase_list.keys()) < 7 and generator_level < 2:
            purchase_list['Generator Lv.2'] = [20, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.2']
        #Diamond Dirt unlocks if not yet unlocked
        if len(purchase_list.keys()) < 7 and diamond_dirt_bought_once == False:
            purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
            diamond_dirt_bought_once = True
        if len(purchase_list.keys()) < 7 and window_level < 3:
            purchase_list['Windows Lv. 3'] = [40, 1, 'Catches even more sunlight, growing HP and DEF more.', 'windows', 'Windows Lv. 2']
        if len(purchase_list.keys()) < 7:
            purchase_list['Irrigation Lv.3'] = [40, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.3']
        if len(purchase_list.keys()) < 7:
            purchase_list['Generator Lv.3'] = [40, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.3']
        rabbit1 = Specific_Plant(species=species_objects['eras_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['lavender_nibble']])
        rabbit2 = Specific_Plant(species=species_objects['filthy_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['hot_nibble_ball']])
        enemies_list = [rabbit1, rabbit2]

    #Day 8
    if day == 8:
    #Only things not unlocked unlock
    #Add irrigation and batteries level 3 if not unlocked
        if len(purchase_list.keys()) < 7 and irrigation_level < 2:
            purchase_list['Irrigation Lv.2'] = [20, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        if len(purchase_list.keys()) < 7 and generator_level < 2:
            purchase_list['Generator Lv.2'] = [20, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.2']
        #Diamond Dirt unlocks if not yet unlocked
        if len(purchase_list.keys()) < 7 and diamond_dirt_bought_once == False:
            purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
            diamond_dirt_bought_once = True
        if len(purchase_list.keys()) < 7 and window_level < 3:
            purchase_list['Windows Lv. 3'] = [40, 1, 'Catches even more sunlight, growing HP and DEF more.', 'windows', 'Windows Lv. 2']
        if len(purchase_list.keys()) < 7:
            purchase_list['Irrigation Lv.3'] = [40, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.3']
        if len(purchase_list.keys()) < 7:
            purchase_list['Generator Lv.3'] = [40, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.3']
        if 'Diamond Dirt' in purchase_list.keys():
            purchase_list['Diamond Dirt'][1] += 1
        else:
            if len(purchase_list.keys()) < 7:
                purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
        if 'Cosmic Dirt' in purchase_list.keys():
            purchase_list['Cosmic Dirt'][1] += 1
        else:
            if len(purchase_list.keys()) < 7:
                purchase_list['Cosmic Dirt'] = [6, 1, 'Space-faring dirt that provides Cosmic Power to plants.', 'dirt', 'Cosmic Dirt']
        rabbit1 = Specific_Plant(species=species_objects['waifu_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                       defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble_impact']])
        rabbit2 = Specific_Plant(species=species_objects['missing_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['glitched_nibble']])
        rabbit3 = Specific_Plant(species=species_objects['punished_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['venom_nibble']])
        rabbit4 = Specific_Plant(species=species_objects['stolen_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['volt_nibble']])
        rabbit5 = Specific_Plant(species=species_objects['abstract_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['pretentious_nibble']])
        rabbit6 = Specific_Plant(species=species_objects['noided_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble_goes']])
        rabbit7 = Specific_Plant(species=species_objects['eras_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['lavender_nibble']])
        rabbit8 = Specific_Plant(species=species_objects['filthy_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                        defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['hot_nibble_ball']])
        enemies_list = [rabbit1, rabbit2, rabbit3, rabbit4, rabbit5, rabbit6, rabbit7, rabbit8]


    #Day 9
    if day == 9:
    #Only things not unlocked unlock
    #Add irrigation and batteries level 3 if not unlocked
        if len(purchase_list.keys()) < 7 and irrigation_level < 2:
            purchase_list['Irrigation Lv.2'] = [20, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.2']
        if len(purchase_list.keys()) < 7 and generator_level < 2:
            purchase_list['Generator Lv.2'] = [20, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.2']
        #Diamond Dirt unlocks if not yet unlocked
        if len(purchase_list.keys()) < 7 and diamond_dirt_bought_once == False:
            purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
            diamond_dirt_bought_once = True
        if len(purchase_list.keys()) < 7 and window_level < 3:
            purchase_list['Windows Lv. 3'] = [40, 1, 'Catches even more sunlight, growing HP and DEF more.', 'windows', 'Windows Lv. 2']
        if len(purchase_list.keys()) < 7:
            purchase_list['Irrigation Lv.3'] = [40, 1, 'Waters the plants faster, growing Speed and Attack more.', 'irrigation', 'Irrigation Lv.3']
        if len(purchase_list.keys()) < 7:
            purchase_list['Generator Lv.3'] = [40, 1, 'Supplies more power, further raising Special Attack and Defense.', 'generator', 'Generator Lv.3']
        if 'Diamond Dirt' in purchase_list.keys():
            purchase_list['Diamond Dirt'][1] += 1
        else:
            if len(purchase_list.keys()) < 7:
                purchase_list['Diamond Dirt'] = [12, 1, 'Tough, hard dirt that provides Diamond Power to plants.', 'dirt', 'Diamond Dirt']
        if 'Cosmic Dirt' in purchase_list.keys():
            purchase_list['Cosmic Dirt'][1] += 1
        else:
            if len(purchase_list.keys()) < 7:
                purchase_list['Cosmic Dirt'] = [6, 1, 'Space-faring dirt that provides Cosmic Power to plants.', 'dirt', 'Cosmic Dirt']
        rabbit1 = Specific_Plant(species=species_objects['god_rabbit_species'], hp_ev=0, attack_ev=0, 
                                                            defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['gun_nibble']])
        enemies_list = [rabbit1]
    #Dirt restocks
    #One ultra tough enemy
    
    
    print()


def night_to_day_transition_phase(pressed_keys):
    global overworld_sprites
    global overworld_player_sprite
    global curr_text_added
    global curr_text
    global curr_option_box
    global curr_text_box
    global in_menu
    global enter_check_phase
    global planters
    global enter_night_to_day_transition_phase
    global enter_enemies_approaching_phase
    global all_battle_sprites_killed
    global battle_background
    global curr_enemy_platform
    global curr_hero_platform
    global curr_enemy_status_bar
    global curr_opponent_sprite
    global curr_player_plant_sprite
    global curr_hero_status_bar
    global faint_fixer
    global in_battle_time_box
    #print('in day to night transition phase')
    if curr_option_box == None:
        print('got to night to day phase')
        curr_option_box = Day_Transition_Screen()
        overworld_sprites.add(curr_option_box, layer=10)
    #if not (curr_option_box.faded_in == True and curr_option_box.faded_out == True):
    if not curr_option_box.faded_in == True:
        curr_option_box.handle_screen_fades()
    else:
        if day == 10:
            print('end screen phase, never leave')
        else:
            if all_battle_sprites_killed == False:
                if curr_enemy_status_bar != None:
                    curr_enemy_status_bar.kill()
                    curr_opponent_sprite.kill()
                    del curr_enemy_status_bar
                    del curr_opponent_sprite
                    curr_opponent_sprite = None
                    curr_enemy_status_bar = None
                battle_background.kill()
                del battle_background
                battle_background = None
                curr_enemy_platform.kill()
                del curr_enemy_platform
                curr_enemy_platform = None
                curr_hero_platform.kill()
                del curr_hero_platform
                curr_hero_platform = None
                if curr_player_plant_sprite != None:
                    curr_player_plant_sprite.kill()
                    del curr_player_plant_sprite
                    curr_player_plant_sprite = None
                if curr_hero_status_bar != None:
                    curr_hero_status_bar.kill()
                    del curr_hero_status_bar
                    curr_hero_status_bar = None
                faint_fixer.kill()
                del faint_fixer
                faint_fixer = None
                curr_text_box.kill()
                del curr_text_box
                curr_text_box = None
                for sprite in in_battle_time_box:
                    sprite.kill()
                    del sprite
                in_battle_time_box = None
                all_battle_sprites_killed = True
                # Play the sound in the channel with loops=-1 for infinite looping
                music_channel.play(overworld_music_sound, loops=-1)
                refresh_for_next_day()
            if not curr_option_box.faded_out == True:
                curr_option_box.handle_screen_fades()
                #for sprite in overworld_sprites:
                #    print(f"ID: {id(sprite)}, Sprite: {sprite},")
                #    print(f"Layer: {overworld_sprites.get_layer_of_sprite(sprite)}")
                #    print(f"Groups: {sprite.groups()}")

            else:
                del curr_option_box
                curr_option_box = None
                enter_night_to_day_transition_phase = False
                overworld_player_sprite.interacting = False
                in_menu = False
                overworld_player_sprite.entry_delay = 15


#Inititate attacks
files_path = os.path.join(PATH_START, 'Files')
attacks_path = os.path.join(files_path, 'Attacks.txt')
attack_df = pd.read_csv(attacks_path, sep='\t')
attack_objects = {}
# Iterate through each row and create Power instances
for index, row in attack_df.iterrows():
    object_name = row['Object Name']
    name = row['Name']
    short_name = row['Short Name']
    type_ = row['Type']
    desc = row['Description'] if pd.notnull(row['Description']) else None
    power = int(row['Power']) if pd.notnull(row['Power']) else 0
    accuracy = int(row['Accuracy']) if pd.notnull(row['Accuracy']) else 100  # Default to 100 if missing

    power_obj = Power(
        name=name,
        short_name=short_name,
        type=type_,
        desc=desc,
        power=power,
        accuracy=accuracy
    )

    # Store by name or index or a custom key
    attack_objects[object_name] = power_obj

dirt_move_dict = {'Cosmic': attack_objects['cosmic_power'],
                  'Diamond': attack_objects['diamond_power']}
#Initiate species
species_path = os.path.join(files_path, 'Species.txt')
species_df = pd.read_csv(species_path, sep='\t')
species_objects = {}

for index, row in species_df.iterrows():
    object_name = row['Object Name']
    name = row['Name']
    base_hp = row['Base HP']
    base_attack = row['Base Attack']
    base_defense = row['Base Defense']
    base_special_attack = row['Base Special Attack']
    base_special_defense = row['Base Special Defense']
    base_speed = row['Base Speed']
    money_dropped = row['Money Dropped'] if pd.notnull(row['Money Dropped']) else None

    species_obj = Plant_Species(name=name, base_hp=base_hp, base_attack=base_attack, base_defense=base_defense, base_special_attack=base_special_attack, 
                                base_special_defense=base_special_defense, base_speed=base_speed, money_dropped=money_dropped)

    # Store by name or index or a custom key
    species_objects[object_name] = species_obj

clock = pygame.time.Clock()
running = True
# Main game loop

tile_map = {
            'row1': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row2': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row3': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row4': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row5': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row6': [11,11,11,11,11,11,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,11,11,11,11,11,11],
            'row7': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row8': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row9': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row10': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row11': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row12': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row13': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row14': [11,11,11,11,11,11,12,10,10,10,10,10,10,10,10,10,10,10,10,10,12,11,11,11,11,11,11],
            'row15': [11,11,11,11,11,11,4,4,4,4,4,4,4,13,14,4,4,4,4,4,4,11,11,11,11,11,11],
            'row16': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row17': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row18': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row19': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row20': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11]
        }
collison_map = {
            'row1': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row2': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row3': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row4': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row5': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row6': [11,11,11,11,11,11,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,11,11,11,11,11,11],
            'row7': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row8': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row9': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row10': [11,11,11,11,11,11,10,0,0,0,1,1,1,0,1,1,1,0,0,0,10,11,11,11,11,11,11],
            'row11': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row12': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row13': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row14': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
            'row15': [11,11,11,11,11,11,4,4,4,4,4,4,4,13,14,4,4,4,4,4,4,11,11,11,11,11,11],
            'row16': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row17': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row18': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row19': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row20': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11]
        }
tileset_group = Tileset_Group(tile_map)
curr_text_added = False
curr_text = None
curr_menu = None
key_pressed = False
waiting_to_read = 0
tileset_testing = True
tileset_current = False
overworld_sprites = pygame.sprite.LayeredUpdates()
overworld_player_sprite = None
curr_option_box = None
in_menu = False
curr_text_box = None
enter_plant_phase = False
enter_buy_phase = False
enter_check_phase = False
enter_status_phase = False
enter_day_to_night_transition_phase = False
enter_enemies_approaching_phase = False
plant_growing = False
battle_background = None
curr_opponent_sprite = None
curr_enemy_platform = None
curr_hero_platform = None
enter_enemy_and_enemies_left_phase = False
enter_plant_send_out_phase = False
curr_enemy_status_bar = None
curr_hero_status_bar = None
enter_select_move_phase = False
select_move_group = None
current_battle_steps = None
enter_animate_moves_phase = False
ending_turn = False
faint_played = False
is_player = False
enter_opponent_fainted_phase = False
enter_gain_money_phase = False
enter_all_enemies_defeated_phase = False
enter_night_to_day_transition_phase = False
all_battle_sprites_killed = False
faint_fixer = None
enter_midbattle_status_phase = False
in_battle_money_box = None
enter_refresh_enemies_phase = False
first_enemy = True
first_plant = True
money_changed = False
plant_already_added = False
enter_player_fainted_phase = False
faint_fixer_placed = False
enter_game_over_phase = False
in_battle_time_box = None
enter_all_turns_done_phase = False
window_level = 1
irrigation_level = 0
generator_level = 0
enter_dusk_stat_increase_phase = False
enter_day_to_dusk_transition_phase = False
current_plant_stat_changing =0
background = None
enter_bought_windows_phase = False
enter_fill_phase = False
move_to_learn = None
dirt_enabling_new_move = None
enter_bought_irrigation_phase = False
enter_bought_generator_phase = False
diamond_dirt_bought_once = False
exit_title_screen_phase = False
title_screen = None
day = 0
plant_sprites = []
plants = []
planters = {
    f'row{i}': [None] * 27
    for i in range(1, 21)
}
inventory = {}
money = 10
purchase_list = {}
enemies_list = []


#Initiate Music
# Initialize Pygame mixer
pygame.mixer.init()

sfx_path = os.path.join(PATH_START, "SFX")
sound_effect_faint_path = os.path.join(sfx_path, "faint 02.wav")
sound_effect_faint = pygame.mixer.Sound(sound_effect_faint_path)
sound_effect_select_path = os.path.join(sfx_path, "selection 02.wav")
sound_effect_select = pygame.mixer.Sound(sound_effect_select_path)
sound_effect_hit_path = os.path.join(sfx_path, "high damage_faint 02.wav")
sound_effect_hit = pygame.mixer.Sound(sound_effect_hit_path)
sound_effect_buy_path = os.path.join(sfx_path, "shop sound 03.wav")
sound_effect_buy = pygame.mixer.Sound(sound_effect_buy_path)
sound_effect_cancel_path = os.path.join(sfx_path, "selection 05.wav")
sound_effect_cancel = pygame.mixer.Sound(sound_effect_cancel_path)



music_folder_path = os.path.join(PATH_START, "Music")
battle_music_path = os.path.join(music_folder_path, "BATTLE THEME MAIN.wav")
battle_music_sound = pygame.mixer.Sound(battle_music_path)
overworld_music_path = os.path.join(music_folder_path, "Daytime Theme - Draft 2.wav")
overworld_music_sound = pygame.mixer.Sound(overworld_music_path)
clock_music_path = os.path.join(music_folder_path, "Clock Music.wav")
clock_music_sound = pygame.mixer.Sound(clock_music_path)

# Set up channels
music_channel = pygame.mixer.Channel(0)

sfx_channel = pygame.mixer.Channel(1)  # Find an available channel
music_channel.play(overworld_music_sound, loops=-1)


initialized = True

refresh_for_next_day()


def initialize():
    global tile_map
    global collison_map
    global tileset_group
    global curr_text_added
    global curr_text
    global key_pressed
    global waiting_to_read
    global tileset_testing
    global tileset_current
    global overworld_sprites
    global overworld_player_sprite
    global curr_option_box
    global in_menu
    global curr_text_box
    global enter_plant_phase
    global enter_buy_phase
    global enter_check_phase
    global enter_status_phase
    global enter_day_to_night_transition_phase
    global enter_enemies_approaching_phase
    global plant_growing
    global battle_background
    global curr_opponent_sprite
    global curr_enemy_platform
    global curr_hero_platform
    global enter_enemy_and_enemies_left_phase
    global enter_plant_send_out_phase
    global curr_enemy_status_bar
    global curr_hero_status_bar
    global enter_select_move_phase
    global select_move_group
    global current_battle_steps
    global enter_animate_moves_phase
    global ending_turn
    global faint_played
    global is_player
    global enter_opponent_fainted_phase
    global enter_gain_money_phase
    global enter_all_enemies_defeated_phase
    global enter_night_to_day_transition_phase
    global all_battle_sprites_killed
    global faint_fixer
    global enter_midbattle_status_phase
    global in_battle_money_box
    global enter_refresh_enemies_phase
    global first_enemy
    global first_plant
    global money_changed
    global plant_already_added
    global enter_player_fainted_phase
    global faint_fixer_placed
    global plant_sprites
    global plants
    global planters
    global inventory
    global money
    global purchase_list
    global rabbit1
    global rabbit2
    global rabbit3
    global enemies_list
    global initialized
    global music_channel
    global enter_game_over_phase
    global in_battle_time_box
    global enter_all_turns_done_phase
    global window_level
    global irrigation_level
    global generator_level
    global enter_dusk_stat_increase_phase
    global enter_day_to_dusk_transition_phase
    global background
    global current_plant_stat_changing
    global enter_bought_windows_phase
    global enter_fill_phase
    global move_to_learn
    global dirt_enabling_new_move
    global enter_bought_irrigation_phase
    global enter_bought_generator_phase
    global diamond_dirt_bought_once
    global day
    tile_map = {
            'row1': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row2': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row3': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row4': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row5': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row6': [11,11,11,11,11,11,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,11,11,11,11,11,11],
            'row7': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row8': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row9': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row10': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row11': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row12': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row13': [11,11,11,11,11,11,12,10,0,0,0,0,0,0,0,0,0,0,0,10,12,11,11,11,11,11,11],
            'row14': [11,11,11,11,11,11,12,10,10,10,10,10,10,10,10,10,10,10,10,10,12,11,11,11,11,11,11],
            'row15': [11,11,11,11,11,11,4,4,4,4,4,4,4,13,14,4,4,4,4,4,4,11,11,11,11,11,11],
            'row16': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row17': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row18': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row19': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
            'row20': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11]
        }
    collison_map = {
                'row1': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row2': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row3': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row4': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row5': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row6': [11,11,11,11,11,11,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,11,11,11,11,11,11],
                'row7': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row8': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row9': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row10': [11,11,11,11,11,11,10,0,0,0,1,1,1,0,1,1,1,0,0,0,10,11,11,11,11,11,11],
                'row11': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row12': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row13': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row14': [11,11,11,11,11,11,10,0,0,0,0,0,0,0,0,0,0,0,0,0,10,11,11,11,11,11,11],
                'row15': [11,11,11,11,11,11,4,4,4,4,4,4,4,13,14,4,4,4,4,4,4,11,11,11,11,11,11],
                'row16': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row17': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row18': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row19': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11],
                'row20': [11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11,11]
            }
    tileset_group = Tileset_Group(tile_map)
    curr_text_added = False
    curr_text = None
    key_pressed = False
    waiting_to_read = 0
    tileset_testing = True
    tileset_current = False
    overworld_sprites = pygame.sprite.LayeredUpdates()
    overworld_player_sprite = None
    curr_option_box = None
    in_menu = False
    curr_text_box = None
    enter_plant_phase = False
    enter_buy_phase = False
    enter_check_phase = False
    enter_status_phase = False
    enter_day_to_night_transition_phase = False
    enter_enemies_approaching_phase = False
    plant_growing = False
    battle_background = None
    curr_opponent_sprite = None
    curr_enemy_platform = None
    curr_hero_platform = None
    enter_enemy_and_enemies_left_phase = False
    enter_plant_send_out_phase = False
    curr_enemy_status_bar = None
    curr_hero_status_bar = None
    enter_select_move_phase = False
    select_move_group = None
    current_battle_steps = None
    enter_animate_moves_phase = False
    ending_turn = False
    faint_played = False
    is_player = False
    enter_opponent_fainted_phase = False
    enter_gain_money_phase = False
    enter_all_enemies_defeated_phase = False
    enter_night_to_day_transition_phase = False
    all_battle_sprites_killed = False
    faint_fixer = None
    enter_midbattle_status_phase = False
    in_battle_money_box = None
    enter_refresh_enemies_phase = False
    first_enemy = True
    first_plant = True
    money_changed = False
    plant_already_added = False
    enter_player_fainted_phase = False
    faint_fixer_placed = False
    enter_game_over_phase = False
    in_battle_time_box = None
    enter_all_turns_done_phase = False
    window_level = 1
    irrigation_level = 0
    generator_level = 0
    enter_dusk_stat_increase_phase = False
    enter_day_to_dusk_transition_phase = False
    background = None
    current_plant_stat_changing = 0
    enter_bought_windows_phase = False
    enter_fill_phase = False
    move_to_learn = None
    dirt_enabling_new_move = None
    enter_bought_irrigation_phase = False
    enter_bought_generator_phase = False
    diamond_dirt_bought_once = False
    plant_sprites = []
    plants = []
    planters = {
                'row1': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row2': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row3': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row4': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row5': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row6': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row7': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row8': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row9': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row10': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row11': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row12': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row13': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row14': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row15': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row16': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row17': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row18': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row19': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None],
                'row20': [None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None]
            }
    inventory = {}
    day = 0
    money = 10
    purchase_list = {'Sunflower Seed': [3, 3, 'Fast growing flower that uses solar power in battle.', 'plant', 'Sunflower'],
                    'Rose Seed': [3, 3, 'Fast growing flower that uses beauty power in battle.', 'plant', 'Rose'],
                    'Blue Tulip Seed': [3, 3, 'Fast growing flower that uses enchanted power in battle.', 'plant', 'Blue Tulip']}
    rabbit1 = Specific_Plant(species=species_objects['rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
    rabbit2 = Specific_Plant(species=species_objects['rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
    rabbit3 = Specific_Plant(species=species_objects['rabbit_species'], hp_ev=0, attack_ev=0, 
                                                    defense_ev=0, special_attack_ev=0, special_defense_ev=0, speed_ev=0, attacks=[attack_objects['nibble']])
    enemies_list = [rabbit1, rabbit2, rabbit3]

    # Play the sound in the channel with loops=-1 for infinite looping
    music_channel.play(overworld_music_sound, loops=-1)

    initialized = True

async def main():
    global running
    last_frame_time = time.time()
    screen.set_alpha(None)
    while running == True:
        frame_start = time.time()
        # Detect frame freezes
        delta_time = frame_start - last_frame_time
        last_frame_time = frame_start

        #if delta_time > 0.5:  # If frame takes longer than 0.5s, log warning
            #print(f"WARNING: Frame took {delta_time:.2f} seconds!")
        #print('hello')
        #pressed_keys = None
        #pressed_keys = pygame.key.get_pressed()

        #if not pygame.get_init():  # Detect if Pygame was unexpectedly shut down
            #print("ERROR: Pygame unexpectedly quit!")
            #sys.exit()

        event_start = time.time()
        if in_menu == True:
            pressed_keys = None
            for event in pygame.event.get():
                #print(event)
                if event.type == KEYDOWN:
                    # If the Escape key is pressed, stop the loop
                    # Detect any key press (only print if no other key is being held)
                    if not key_pressed:
                        #print("Key pressed:", event.key)
                        key_pressed = True
                        pressed_keys = pygame.key.get_pressed()
                elif event.type == KEYUP:
                    # Reset the key_pressed flag when the key is released
                    key_pressed = False

                # Handle the quit event
                elif event.type == pygame.QUIT:
                    #print("Quit event triggered")
                    running = False

                elif event.type == pygame.WINDOWFOCUSLOST:
                    print("Window lost focus! Pausing unnecessary updates.")
        else:
            # Get pressed keys
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    #print("Quit event 2 triggered")
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                    pressed_keys = pygame.key.get_pressed()
                elif event.type == pygame.WINDOWFOCUSLOST:
                    print("Window lost focus! Pausing unnecessary updates.")
                else:
                    pressed_keys = None
        event_time = time.time() - event_start

        update_start = time.time()
        if initialized == False:
            initialize()
        if exit_title_screen_phase == False:
            titlescreen_phase(pressed_keys)
        else:
            if tileset_testing == True:
                if enter_plant_phase == True:
                    #print('go to the plant phase')
                    #print('in phase 1')
                    plant_phase(pressed_keys)
                elif enter_fill_phase == True:
                    fill_phase(pressed_keys)
                elif enter_bought_windows_phase == True:
                    bought_windows_phase(pressed_keys)
                elif enter_bought_irrigation_phase == True:
                    bought_irrigation_phase(pressed_keys)
                elif enter_bought_generator_phase == True:
                    bought_generator_phase(pressed_keys)
                elif enter_buy_phase == True:
                    #print('go to the buy phase')
                    #plant_phase(pressed_keys)
                    #print('in phase 2')
                    buy_phase(pressed_keys)
                elif enter_check_phase == True:
                    #print('in phase 3')
                    check_phase(pressed_keys)
                elif enter_status_phase == True:
                    #print('in phase 4')
                    status_phase(pressed_keys)
                elif enter_day_to_dusk_transition_phase == True:
                    day_to_dusk_transition_phase(pressed_keys)
                elif enter_dusk_stat_increase_phase == True:
                    dusk_stat_increase_phase(pressed_keys)
                elif enter_day_to_night_transition_phase == True:
                    #print('in phase 5')
                    day_to_night_transition_phase(pressed_keys)
                elif enter_enemies_approaching_phase == True:
                    #print('in phase 6')
                    enemies_approaching_phase(pressed_keys)
                elif enter_refresh_enemies_phase == True:
                    refresh_enemies_phase(pressed_keys)
                elif enter_enemy_and_enemies_left_phase == True:
                    #print('in phase 7')
                    enemy_and_enemies_left_phase(pressed_keys)
                elif enter_plant_send_out_phase == True:
                    #print('in phase 8')
                    plant_send_out_phase(pressed_keys)
                elif enter_select_move_phase == True:
                    #print('in phase 9')
                    select_move_phase(pressed_keys)
                elif enter_midbattle_status_phase == True:
                    midbattle_status_phase(pressed_keys)
                elif enter_animate_moves_phase == True:
                    #print('in phase 10')
                    animate_move_phase(pressed_keys)
                elif enter_opponent_fainted_phase == True:
                    #print('in phase 11')
                    opponent_fainted_phase(pressed_keys)
                elif enter_player_fainted_phase == True:
                    player_fainted_phase(pressed_keys)
                elif enter_gain_money_phase == True:
                    #print('in phase 12')
                    gain_money_phase(pressed_keys)
                elif enter_all_enemies_defeated_phase == True:
                    #print('in phase 13')
                    all_enemies_defeated_phase(pressed_keys)
                elif enter_all_turns_done_phase == True:
                    all_turns_done_phase(pressed_keys)
                elif enter_night_to_day_transition_phase == True:
                    #print('in phase 14')
                    night_to_day_transition_phase(pressed_keys)
                elif enter_game_over_phase == True:
                    game_over_phase(pressed_keys)
                else:
                    #print('in phase 15')
                    tileset_test(pressed_keys)
            
        update_time = time.time() - update_start

        # Get the set of keys pressed and check for user input
        
        # Clear the screen
        render_start = time.time()
        if tileset_testing == True:
            #print('testing tilesets')
            for entity in overworld_sprites:
                scaled_surf = pygame.transform.scale(entity.surf, (int(entity.rect.width * scale_factor), int(entity.rect.height * scale_factor)))
                scaled_rect = scaled_surf.get_rect(topleft=(int(entity.rect.x * scale_factor), int(entity.rect.y * scale_factor)))
                screen.blit(scaled_surf, scaled_rect)
            #print(f'number of sprites is {i}')

            #screen.blit(pygame.transform.scale(entity.surf, (SCREEN_WIDTH * entity.rect.width, SCREEN_HEIGHT * entity.rect.height)), (0, 0))
        render_time = time.time() - render_start

        pygame.display.flip()
        fps = clock.get_fps()
        #print(f"FPS: {fps}")
        #get_memory_usage()
        frame_time = time.time() - frame_start
        #print(f"Event: {event_time:.4f}s | Update: {update_time:.4f}s | Render: {render_time:.4f}s | Total Frame: {frame_time:.4f}s")
        clock.tick(60)
        await asyncio.sleep(0)  # Very important, and keep it 0
    pygame.quit()
    sys.exit()


asyncio.run(main())