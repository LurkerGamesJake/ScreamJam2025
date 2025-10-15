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
#import gc
import random
import math
import asyncio
import numpy as np
import pandas as pd
from collections import deque
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

#gc.set_debug(gc.DEBUG_STATS)

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
pygame.joystick.init()

# Set up display
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 360
info = pygame.display.Info()
print("Monitor resolution:", info.current_w, "x", info.current_h)
monitor_width = info.current_w
monitor_height = info.current_h

target_ratio = 16 / 9
tolerance = 0.01  # allow small floating-point error

if abs((monitor_width / monitor_height) - target_ratio) < tolerance:
    print("This is a 16:9 monitor")
    TARGET_FPS = 300
else:
    print("This is not 16:9 (ratio:", (monitor_width / monitor_height), ")")
    SCREEN_WIDTH = 640
    SCREEN_HEIGHT = 400
    TARGET_FPS = 60
scale_factor = monitor_width / SCREEN_WIDTH
print(scale_factor)

#Actual Resolution Mode
#TARGET_FPS = 60
scale_factor = 2
screen = pygame.display.set_mode([SCREEN_WIDTH * scale_factor, SCREEN_HEIGHT * scale_factor])


#screen = pygame.display.set_mode([SCREEN_WIDTH * scale_factor, SCREEN_HEIGHT * scale_factor], pygame.FULLSCREEN)
pygame.display.set_caption("ScreamJam")

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
folders_to_load = ["UI", "Tiles", "Fonts", "Buildings", "Characters"]

load_images_from_folder(PATH_START, folders_to_load, IMAGES_DICT)

#---------INDIVIDUAL SPRITE SET UP
class Individual_Sprite(pygame.sprite.Sprite):
    def __init__(self, image_key, subsurface_rect, start_pos, tile_number=None, uses_alpha=False):
        super().__init__()
        self.full_image = IMAGES_DICT[image_key]
        #if tile_number is not None:
        #    self.tile_number = tile_number

        # Get the base surface (subsurface if specified)
        if subsurface_rect is not None:
            base_surf = self.full_image.subsurface(subsurface_rect)
        else:
            base_surf = self.full_image

        # Scale the surface according to scale_factor
        self.surf = pygame.transform.scale(
            base_surf,
            (round(base_surf.get_width() * scale_factor),
             round(base_surf.get_height() * scale_factor))
        )

        # Set rect from the scaled surface
        self.rect = self.surf.get_rect()

        # Scale starting position
        start_x = int(start_pos[1][0] * scale_factor)
        start_y = int(start_pos[1][1] * scale_factor)

        # Position the sprite
        self.start_pos_type = start_pos[0]
        if self.start_pos_type == 'tr':
            self.rect.topright = (start_x, start_y)
        elif self.start_pos_type == 'tl':
            self.rect.topleft = (start_x, start_y)
        elif self.start_pos_type == 'bl':
            self.rect.bottomleft = (start_x, start_y)

        # Store float positions
        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)

        if uses_alpha:
            self.surf.set_alpha(0)
            self.surf.get_alpha()
            self.increase_alpha = True

    def fade_in_and_out(self, fade_fast=False):
        curr_alpha = self.surf.get_alpha()
        if self.increase_alpha:
            curr_alpha += 1
            self.surf.set_alpha(curr_alpha)
        else:
            curr_alpha -= 1
            self.surf.set_alpha(curr_alpha)
        if curr_alpha == 122:
            self.increase_alpha = False
        if curr_alpha == 0:
            self.increase_alpha = True

    def get_sprites_below(self, mode=None):
        """Return list of sprites whose rect intersects the cursor rect.
        Order: largest overlap -> smallest overlap."""
        global GAME_STATE
        cursor_rect = self.rect
        colliding = []

        for sprite in GAME_STATE["tileset_group"].sprites():
            if sprite.rect.colliderect(cursor_rect):
                inter = cursor_rect.clip(sprite.rect)        # intersection rect
                area = inter.width * inter.height
                colliding.append((sprite, area))

        # sort by descending overlap area, then by top-left preference (x, y)
        if mode == 'bl':
            colliding.sort(key=lambda sa: (-sa[1], sa[0].rect.x, -sa[0].rect.y))
        else:
            colliding.sort(key=lambda sa: (-sa[1], sa[0].rect.x, sa[0].rect.y))

        # For debugging: print every colliding tile and its overlap area
        #for s, area in colliding:
        #    print(f"Colliding tile: {s.df_pos} at {s.pos_x}, {s.pos_y} overlap={area}")

        return [s for s, area in colliding]

    def get_best_sprite_below(self, mode=None):
        """Return the single sprite that the cursor overlaps the most,
        or None if none overlap."""
        colliding = self.get_sprites_below(mode=mode)
        return colliding[0] if colliding else None


#---------INDIVIDUAL SPRITES
class Regular_Font_Letter(pygame.sprite.Sprite):
    def __init__(self, letter, topright_input, recolor=True):
        super().__init__()
        self.letter = letter
        # Scale starting position
        start_x = int(topright_input[0] * scale_factor)
        start_y = int(topright_input[1] * scale_factor)
        self.topright_input = (start_x, start_y)
        if letter == 'DownArrow':
            full_image = IMAGES_DICT["Fonts_down_arrow.png"]
            self.curr_frame = 0
            self.animate_buffer = 0
            
            self.frame_1 = full_image.subsurface((0, 0, 8, 16))
            self.frame_2 = full_image.subsurface((0, 16, 8, 16))
            self.frame_3 = full_image.subsurface((0, 32, 8, 16))
            self.frames = [self.frame_1, self.frame_2, self.frame_3, self.frame_2]

            base_surf = pygame.Surface((8, 16), pygame.SRCALPHA)
            base_surf.blit(self.frame_3, (0, 0))

        else:
            full_image = IMAGES_DICT["Fonts_monogram-bitmap_white.png"] if recolor else IMAGES_DICT["Fonts_monogram-bitmap.png"]
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

            base_surf = full_image.subsurface(pygame.Rect(x, y, 6, 11))


        # Scale the surface according to scale_factor
        self.surf = pygame.transform.scale(
            base_surf,
            (round(base_surf.get_width() * scale_factor),
             round(base_surf.get_height() * scale_factor))
        )

        # Set rect from the scaled surface
        self.rect = self.surf.get_rect()

        self.rect = self.surf.get_rect()
        self.rect.topright = (-400, -400)  # initial placeholder position
        self.width = self.rect.width
        self.height = self.rect.height
        self.surface_to_return = self.surf

    def reveal(self):
        self.rect.topright = self.topright_input

    def hide(self):
        self.rect.topright = (-400, -400) 
        


class Title_Screen(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"UI_TitleScreen.png",
            subsurface_rect=(0,0,640,360),
            start_pos=['tl', (0,0)]
        )

class Cursor(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="UI_Cursor.png",
            subsurface_rect=(0,0,4,4),
            start_pos=['tl', (((SCREEN_WIDTH/2) - 2), ((SCREEN_HEIGHT/2) - 2))]
        )

    

class SelectedTile(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key=f"UI_SelectedTile.png",
            subsurface_rect=(0,0,16,16),
            start_pos=['tl', (((SCREEN_WIDTH/2) - 8),((SCREEN_HEIGHT/2) - 8))]
        )
        self.tile = None
        self.previous_tile = None

    def update_tile(self, new_tile):
        self.previous_tile = self.tile
        self.tile = new_tile
        self.pos_x = int(new_tile.pos_x)
        self.pos_y = int(new_tile.pos_y)
        # Update the actual rect position so it moves on screen
        self.rect.topleft = (self.pos_x, self.pos_y)

class Tile(Individual_Sprite):
    def __init__(self, top_left, tile_number, df_pos=None):
        super().__init__(
            image_key=f"Tiles_{tile_number}.png",
            subsurface_rect=(0,0,16,16),
            start_pos=['tl', top_left],
        )
        self.df_pos = df_pos
        if tile_number not in [4, 1, 3]:
            self.tile_number = 3
        else:
            self.tile_number = tile_number
        self.displayed_tile = str(tile_number)

    def change_tile(self, new_tile):
        self.full_image = IMAGES_DICT[f"Tiles_{new_tile}.png"]
        base_surf = self.full_image
        self.surf = pygame.transform.scale(
            base_surf,
            (round(base_surf.get_width() * scale_factor),
            round(base_surf.get_height() * scale_factor))
        )
        self.displayed_tile = new_tile

    def set_corner_borders(self, overlays):
        self.change_tile(self.displayed_tile)
        for overlay in overlays:
            if overlay == "top_left_overlay":
                self.set_pixel_color(0, 0, (76, 83, 80))
                self.set_pixel_color(0, 1, (107, 114, 117))
                self.set_pixel_color(1, 0, (103, 110, 114))
            elif overlay == "top_right_overlay":
                self.set_pixel_color(15, 0, (76, 83, 80))
                self.set_pixel_color(15, 1, (110, 117, 121))
                self.set_pixel_color(14, 0, (103, 110, 114))
            elif overlay == "bottom_left_overlay":
                self.set_pixel_color(0, 15, (76, 83, 80))
                self.set_pixel_color(0, 14, (110, 117, 121))
                self.set_pixel_color(1, 15, (103, 110, 114))
            elif overlay == "bottom_right_overlay":
                self.set_pixel_color(15, 15, (76, 83, 80))
                self.set_pixel_color(15, 14, (110, 117, 121))
                self.set_pixel_color(14, 15, (103, 110, 114))
        

    def set_pixel_color(self, x, y, color):
        # Ensure we modify the base image (not the scaled one)
        surf = self.full_image.copy()  # avoid mutating shared IMAGES_DICT surfaces
        surf.lock()
        surf.set_at((x, y), color)
        surf.unlock()

        # Update both the full_image and the scaled display surface
        self.full_image = surf
        self.surf = pygame.transform.scale(
            surf,
            (
                round(surf.get_width() * scale_factor),
                round(surf.get_height() * scale_factor)
            )
        )


class Hover_Building(Individual_Sprite):
    def __init__(self, top_left, building):
        if building == "Nothing":
            self.building = "Nothing"
        else:
            super().__init__(
                image_key=f"Buildings_{building}.png",
                subsurface_rect=None,
                start_pos=['tl', top_left],
                uses_alpha=True
            )
            self.building = building

class Generic_Building(Individual_Sprite):
    def __init__(self, top_left, building, df_pos=None):
        super().__init__(
            image_key=f"Buildings_{building}.png",
            subsurface_rect=None,
            start_pos=['tl', top_left]
        )
        self.df_pos = df_pos
        self.building = building
        self.door_open = False
        self.tourists = []
        self.villagers = []
        self.tourist_capacity = 5
    
    def open_door(self):
        self.full_image = IMAGES_DICT[f"Buildings_{self.building}_DoorOpen.png"]
        base_surf = self.full_image
        self.surf = pygame.transform.scale(
            base_surf,
            (round(base_surf.get_width() * scale_factor),
            round(base_surf.get_height() * scale_factor))
        )
        self.door_open = True
        self.last_check_update = pygame.time.get_ticks()

    def close_door(self):
        self.full_image = IMAGES_DICT[f"Buildings_{self.building}.png"]
        base_surf = self.full_image
        self.surf = pygame.transform.scale(
            base_surf,
            (round(base_surf.get_width() * scale_factor),
            round(base_surf.get_height() * scale_factor))
        )
        self.door_open = False


class Overworld_Main_Text_box(Individual_Sprite):
    def __init__(self, top_left=(0,317)):
        super().__init__(
            image_key="UI_Textbox.png",
            subsurface_rect=(0,0,640,43),
            start_pos=['tl', top_left]
        )

class Overworld_Wide_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_WideOptionBox.png",
            subsurface_rect=(0,0,208,43),
            start_pos=['tl', top_left]
        )

class Overworld_Wide_Option_Box_3(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"UI_WideOptionBox_3.png",
            subsurface_rect=None,
            start_pos=['tl', top_left]
        )

class Overworld_Wide_Option_Box_4(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"UI_WideOptionBox_4.png",
            subsurface_rect=None,
            start_pos=['tl', top_left]
        )


class Overworld_Wide_Option_Box_5(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key=f"UI_WideOptionBox_5.png",
            subsurface_rect=None,
            start_pos=['tl', top_left]
        )

class Character_Sprite(Individual_Sprite):
    def __init__(self, bottom_left, unique_id=None, df_pos=None, goal_destinations=['store_entrance', 'diner_entrance', 'apartment_entrance', "Exit"], grass_touched=False):
        super().__init__(
            image_key="Characters_Forward.png",
            subsurface_rect=(0,0,16,24),
            start_pos=['bl', bottom_left]
        )
        self.df_pos=df_pos
        self.target=None
        self.check_buffer=0
        self.pixels_moved=0
        self.direction = 'Forward'
        self.moving = False
        self.at_destination = False
        self.character_type = 'Tourist'
        self.last_pixel_checkin = 0
        self.curr_frame = 0
        self.unique_id = unique_id
        self.goal_destinations = goal_destinations
        self.last_check_update = 0
        self.has_touched_grass = grass_touched

    def character_moving_animation(self):
        if self.moving:
            previous_frame = self.curr_frame
            tile_half = 8 * scale_factor
            tile_full = 16 * scale_factor
            if self.pixels_moved < tile_half:
                self.full_image = IMAGES_DICT[f"Characters_{self.direction}1.png"]
                base_surf = self.full_image.subsurface((0,0,16,24))
                self.surf = pygame.transform.scale(
                    base_surf,
                    (round(base_surf.get_width() * scale_factor),
                    round(base_surf.get_height() * scale_factor))
                )
                self.curr_frame = 1
            elif self.pixels_moved < tile_full:
                self.full_image = IMAGES_DICT[f"Characters_{self.direction}2.png"]
                base_surf = self.full_image.subsurface((0,0,16,24))
                self.surf = pygame.transform.scale(
                    base_surf,
                    (round(base_surf.get_width() * scale_factor),
                    round(base_surf.get_height() * scale_factor))
                )
                self.curr_frame = 2
            else:
                self.full_image = IMAGES_DICT[f"Characters_{self.direction}1.png"]
                base_surf = self.full_image.subsurface((0,0,16,24))
                self.surf = pygame.transform.scale(
                    base_surf,
                    (round(base_surf.get_width() * scale_factor),
                    round(base_surf.get_height() * scale_factor))
                )
                self.curr_frame = 1
            if self.curr_frame != previous_frame:
                walking_sound()
        
    def character_stop_moving(self):
        self.full_image = IMAGES_DICT[f"Characters_{self.direction}.png"]
        base_surf = self.full_image.subsurface((0,0,16,24))
        self.surf = pygame.transform.scale(
            base_surf,
            (round(base_surf.get_width() * scale_factor),
            round(base_surf.get_height() * scale_factor))
        )


#---------SPRITE GROUPS
class Regular_Font_Line(pygame.sprite.Group):
    def __init__(self, input_string, text_type, special_top_left=False):
        super(Regular_Font_Line, self).__init__()
        self.text_type = text_type
        self.special_top_left = special_top_left
        self.set_letters(input_string, self.text_type)
        self.reveal_speed = 20  # ms per letter (~25 letters/sec)
        self.last_reveal_time = pygame.time.get_ticks()
        

    def update(self):
        global GAME_STATE
        if not self.all_letters_set:

            now = pygame.time.get_ticks()
            elapsed = now - self.last_reveal_time

            # Only reveal a letter every X milliseconds
            if elapsed >= self.reveal_speed:
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

                self.last_reveal_time = now  # reset timer

                if revealed_count >= self.expected_length:
                    self.all_letters_set = True

        if self.is_arrow_on_screen and self.arrow:
            self.arrow.animate_arrow()

        if GAME_STATE["just_pressed"] and GAME_STATE["just_pressed"]["action"]:
            #select_sound()
            if self.text_type == 'arrow' and self.is_arrow_on_screen:
                for sprite in self:
                    sprite.kill()
                self.ready_for_removal = True

        if self.text_type in ('not_arrow', 'immediate') and self.ready_for_removal:
            for sprite in self:
                sprite.kill()
            self.empty()  # Clear group explicitly

    def create_text_label(self, text, x, y, arrow=False, visible=False, recolor=False):
        char_list = []
        curr_width = x
        if arrow:
            temp_char = Regular_Font_Letter('selection', (curr_width, y), recolor=recolor)
            curr_width += 1
            char_list.append(temp_char)
        for char in text:
            temp_char = Regular_Font_Letter(char, (curr_width, y), recolor=recolor)
            curr_width += int(temp_char.width/scale_factor)
            char_list.append(Regular_Font_Letter(char, (curr_width, y), recolor=recolor))
        for item in char_list:
            self.add(item)
            if visible:
                item.reveal()
            else:
                item.hide()
        return char_list

    def set_letters(self, input_string, text_type):
        if len(input_string) > 108: #Need to adjust for new resolution(s)
            split_index = input_string.rfind(' ', 0, 108)
            if split_index == -1:
                split_index = 108  # no space found, hard split
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
        # Starting positions NEED ADJUSTED
        if self.special_top_left:
            starting_height_top = 7
            starting_height_bottom = 23
        else:
            starting_height_top = 324
            starting_height_bottom = 340
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

        if text_type == 'immediate':
            for item in self.char_list:
                item.reveal()


class Tileset_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super().__init__()
        self.tiles_dict = {}
        self.tile_map = tile_map

        tile_size = 16
        start_x, start_y = -96, -80
        indexes_to_change = []
        for row_index, (_, row) in enumerate(tile_map.iterrows()):
            y = start_y + row_index * tile_size
            for col_index, column in enumerate(row):
                x = start_x + col_index * tile_size
                if str(column) not in ["1", "3", "4"]:
                    #print(column)
                    indexes_to_change.append([row_index, col_index])
                    
                curr_tile = Tile(
                    (x, y),
                    column,
                    df_pos=(row_index, col_index)  # <--- pass DataFrame coordinates
                )
                self.tiles_dict[f"{row_index}_{col_index}"] = curr_tile
                self.add(curr_tile)
        self.moving = False
        for index in indexes_to_change:
            self.tile_map.iat[index[0], index[1]] = 3
        
    def move(self, dx, dy, speed, dt):
        move_x = dx * speed * dt * scale_factor
        move_y = dy * speed * dt * scale_factor

        for tile_sprite in self.tiles_dict.values():
            tile_sprite.pos_x += (move_x * 4)
            tile_sprite.pos_y += (move_y * 4)
            tile_sprite.rect.x = int(tile_sprite.pos_x)
            tile_sprite.rect.y = int(tile_sprite.pos_y)

    def check_move(self):
        global GAME_STATE
        self.moving = False
        dx = 0
        dy = 0

        dx, dy = get_move_vector()
        if dx != 0 or dy != 0:
            self.moving = True
            self.move(dx, dy, speed=60, dt=GAME_STATE["delta_time"])  # e.g., 60 pixels per second
            tile_below = GAME_STATE["cursor"].get_best_sprite_below()
            if tile_below.tile_number in [3, 4]: #This is a source of slow down and ideally we'd not move back
                self.move(-dx, -dy, speed=60, dt=GAME_STATE["delta_time"])
            else:
                GAME_STATE["building_group"].check_move()
                GAME_STATE["character_group"].check_move()
        else:
            self.moving = False

class Character_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super().__init__()
        global GAME_STATE
        self.tiles_dict = {}
        self.tile_map = tile_map

        tile_size = 16
        start_x, start_y = -96, -80

        for row_index, (_, row) in enumerate(tile_map.iterrows()):
            y = start_y + row_index * tile_size
            for col_index, column in enumerate(row):
                if column != 0:
                    x = start_x + col_index * tile_size
                    curr_character = Character_Sprite(
                        (x, y+16),
                        #column, This will be where we put in the type of character later,
                        unique_id = GAME_STATE["unique_character_int"],
                        df_pos=(row_index, col_index)  # <--- pass DataFrame coordinates
                    )
                    self.tiles_dict[f"{row_index}_{col_index}_{GAME_STATE["unique_character_int"]}"] = curr_character
                    self.add(curr_character)
                    GAME_STATE["unique_character_int"] += 1
        self.moving = False

    def move(self, dx, dy, speed, dt):
        move_x = dx * speed * dt * scale_factor
        move_y = dy * speed * dt * scale_factor

        for tile_sprite in self.tiles_dict.values():
            if isinstance(tile_sprite, Individual_Sprite):
                tile_sprite.pos_x += (move_x * 4)
                tile_sprite.pos_y += (move_y * 4)
                tile_sprite.rect.x = int(tile_sprite.pos_x)
                tile_sprite.rect.y = int(tile_sprite.pos_y)

    def check_move(self):
        global GAME_STATE
        self.moving = False
        dx = 0
        dy = 0

        dx, dy = get_move_vector()
        if dx != 0 or dy != 0:
            self.moving = True
            self.move(dx, dy, speed=60, dt=GAME_STATE["delta_time"])  # e.g., 60 pixels per second
            #tile_below = GAME_STATE["cursor"].get_best_sprite_below()
            #if tile_below.tile_number == 4:
            #    self.move(-dx, -dy, speed=60, dt=GAME_STATE["delta_time"])
        else:
            self.moving = False

    def remove_character(self, character):
        GAME_STATE["temp_character_group_dict"].pop(f"{character.df_pos[0]}_{character.df_pos[1]}_{character.unique_id}", None)
        #print(f"Character ending at {character.rect.x}, {character.rect.y}")
        self.remove(character)
        character.kill()
        #GAME_STATE["building_map_np"] = self.tile_map.values
        del character

    def add_character(self, df_pos, destination_list=['store_entrance', 'diner_entrance', 'apartment_entrance', "Exit"], grass_touched=False):
        tile_spawning_at = get_tile_at_pos(df_pos)
        curr_character = Character_Sprite(
                        (tile_spawning_at.rect.x/scale_factor, (tile_spawning_at.rect.y/scale_factor) + 16),
                        #column, This will be where we put in the type of character later
                        unique_id=GAME_STATE["unique_character_int"],
                        df_pos=df_pos,  # <--- pass DataFrame coordinates
                        goal_destinations=destination_list,
                        grass_touched=grass_touched
                    )
        GAME_STATE["temp_character_group_dict"][f"{df_pos[0]}_{df_pos[1]}_{GAME_STATE["unique_character_int"]}"] = curr_character
        self.add(curr_character)
        GAME_STATE["unique_character_int"] += 1
        GAME_STATE["overworld_sprites"].add(curr_character, layer=3)

class Building_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super().__init__()
        self.tiles_dict = {}
        self.tile_map = tile_map

        tile_size = 16
        start_x, start_y = -96, -80

        for row_index, (_, row) in enumerate(tile_map.iterrows()):
            y = start_y + row_index * tile_size
            for col_index, column in enumerate(row):
                if str(column) != "0" and str(column) != "Exit":
                    x = start_x + col_index * tile_size
                    curr_building = Generic_Building(
                        (x, y),
                        column,
                        df_pos=(row_index, col_index)  # <--- pass DataFrame coordinates
                    )
                    self.tiles_dict[f"{row_index}_{col_index}"] = curr_building
                    self.add(curr_building)

        self.moving = False

    def add_building(self, building):
        global GAME_STATE
        if GAME_STATE["money"] < GAME_STATE["current_stats"][0]:
            return "no money"
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        curr_building = Generic_Building(
        (int(GAME_STATE["selectedtile"].pos_x/scale_factor), int(GAME_STATE["selectedtile"].pos_y/scale_factor)),
        building,
        df_pos=GAME_STATE["selectedtile"].tile.df_pos  # <--- pass DataFrame coordinates
        )
        
        real_width = int(curr_building.surf.width/scale_factor)
        real_height = int(curr_building.surf.height/scale_factor)
        tiles_wide = math.ceil(real_width / 16)
        tiles_tall = math.ceil(real_height / 16)
        curr_row = 0
        while curr_row < tiles_tall:
            curr_column = 0
            while curr_column < tiles_wide:
                if str(self.tile_map.iat[r + curr_row, c + curr_column]) != "0" or str(GAME_STATE["tileset_group"].tile_map.iat[r + curr_row, c + curr_column]) != "1":
                    return 'no space'
                curr_column += 1
            curr_row += 1
        character_df_pos_to_check = []
        curr_row = 0
        while curr_row < tiles_tall:
            curr_column = 0
            while curr_column < tiles_wide:
                character_df_pos_to_check.append((r + curr_row, c + curr_column))
                curr_column += 1
            curr_row += 1
        for character in GAME_STATE["character_group"].tiles_dict.values():
            if isinstance(character, Individual_Sprite):
                if character.df_pos in character_df_pos_to_check:
                    return 'character'
        self.tiles_dict[f"{r}_{c}"] = curr_building
        self.tile_map.iat[r, c] = building
        curr_row = 0
        while curr_row < tiles_tall:
            curr_column = 0
            while curr_column < tiles_wide:
                if not (curr_row == 0 and curr_column == 0):
                    self.tile_map.iat[r + curr_row, c + curr_column] = building
                    self.tiles_dict[f"{r + curr_row}_{c + curr_column}"] = f"{r}_{c}"
                if curr_row == 3 and building == 'Apartment':
                    if curr_column == 1:
                        self.tile_map.iat[r + curr_row, c + curr_column] = 'apartment_entrance'
                    else:
                        self.tile_map.iat[r + curr_row, c + curr_column] = 'front'
                    self.tiles_dict[f"{r + curr_row}_{c + curr_column}"] = f"{r}_{c}"
                if curr_row == 4 and building == 'Store':
                    if curr_column == 3:
                        self.tile_map.iat[r + curr_row, c + curr_column] = 'store_entrance'
                    else:
                        self.tile_map.iat[r + curr_row, c + curr_column] = 'front'
                    self.tiles_dict[f"{r + curr_row}_{c + curr_column}"] = f"{r}_{c}"
                if curr_row == 4 and building == 'Diner':
                    if curr_column == 2:
                        self.tile_map.iat[r + curr_row, c + curr_column] = 'diner_entrance'
                    else:
                        self.tile_map.iat[r + curr_row, c + curr_column] = 'front'
                    self.tiles_dict[f"{r + curr_row}_{c + curr_column}"] = f"{r}_{c}"
                if curr_column == 6 and building == 'Diner':
                    self.tile_map.iat[r + curr_row, c + curr_column] = 0
                curr_column += 1
            curr_row += 1
        self.add(curr_building)
        GAME_STATE["overworld_sprites"].add(curr_building, layer=2)
        GAME_STATE["building_map_np"] = self.tile_map.values
        clear_character_targets()
        return 'pass'

    def remove_building(self):
        
        global GAME_STATE


        r, c = GAME_STATE["selectedtile"].tile.df_pos
        curr_building = self.tiles_dict[f"{r}_{c}"]
        if not isinstance(curr_building, Individual_Sprite):
            curr_building = self.tiles_dict[curr_building]
            r, c = curr_building.df_pos
        if curr_building.tourists != [] or curr_building.villagers != []:
            return False
        row = GAME_STATE["stats_dataframe"].loc[GAME_STATE["stats_dataframe"]["Building"] == curr_building.building]
        if row.empty:
            print(f"No data found for '{curr_building.building}'")
        else:
            row = row.iloc[0]
            GAME_STATE["money"] += int(row['Cost']/2)
            GAME_STATE["spookiness"] -= row["Spookiness"]


        real_width = int(curr_building.surf.width/scale_factor)
        real_height = int(curr_building.surf.height/scale_factor)
        tiles_wide = math.ceil(real_width / 16)
        tiles_tall = math.ceil(real_height / 16)
        curr_row = 0
        while curr_row < tiles_tall:
            curr_column = 0
            while curr_column < tiles_wide:
                self.tile_map.iat[r + curr_row, c + curr_column] = 0
                self.tiles_dict.pop(f"{r + curr_row}_{c + curr_column}", None)
                curr_column += 1
            curr_row += 1
        self.remove(curr_building)
        curr_building.kill()
        GAME_STATE["building_map_np"] = self.tile_map.values
        del curr_building
        clear_character_targets()
        return True

        
    def move(self, dx, dy, speed, dt):
        move_x = dx * speed * dt * scale_factor
        move_y = dy * speed * dt * scale_factor

        for tile_sprite in self.tiles_dict.values():
            if isinstance(tile_sprite, Individual_Sprite):
                tile_sprite.pos_x += (move_x * 4)
                tile_sprite.pos_y += (move_y * 4)
                tile_sprite.rect.x = int(tile_sprite.pos_x)
                tile_sprite.rect.y = int(tile_sprite.pos_y)

    def check_move(self):
        global GAME_STATE
        self.moving = False
        dx = 0
        dy = 0

        dx, dy = get_move_vector()
        if dx != 0 or dy != 0:
            self.moving = True
            self.move(dx, dy, speed=60, dt=GAME_STATE["delta_time"])  # e.g., 60 pixels per second
            tile_below = GAME_STATE["cursor"].get_best_sprite_below()
            if tile_below.tile_number == 4:
                self.move(-dx, -dy, speed=60, dt=GAME_STATE["delta_time"])
        else:
            self.moving = False

class Overworld_Menu(pygame.sprite.Group):
    def __init__(self, input_string, text_type, options=None, use_buy_sound=False, money_box=False, store_box=False, quantity_box=False, special_top_left=False):
        super(Overworld_Menu, self).__init__()
        if options:
            self.option_box = Overworld_Option_Box(top_left=(0,(SCREEN_HEIGHT-86)), options=options, use_buy_sound=use_buy_sound)
            self.add(self.option_box)
            self.number_of_option_boxes = 1
            self.previous_option_boxes = []
        else:
            self.option_box = None
            self.number_of_option_boxes = 0
        self.special_top_left = special_top_left
        if self.special_top_left:
            self.main_text_box = Overworld_Main_Text_box(top_left=(0,0))
        else:
            self.main_text_box = Overworld_Main_Text_box()
        self.curr_text = Regular_Font_Line(input_string=input_string, text_type=text_type, special_top_left=self.special_top_left)
        self.add(self.main_text_box)
        self.add(self.curr_text)
        self.info_box = None

    def update_curr_text(self):
        self.curr_text.update()

    def change_curr_text(self, input_string, text_type):
        for s in self.curr_text:
            s.kill()
            del s
        self.curr_text = Regular_Font_Line(input_string=input_string, text_type=text_type, special_top_left=self.special_top_left)
        self.add(self.curr_text)
        for sprite in self.curr_text:
            GAME_STATE["overworld_sprites"].add(sprite, layer=6)
    
    def update_option_box(self):
        self.option_box.update()

    def add_option_box(self, options):
        self.previous_option_boxes.append(self.option_box)
        self.option_box = Overworld_Option_Box(top_left=(208,(SCREEN_HEIGHT-86)), options=options)
        self.number_of_option_boxes += 1
        self.add(self.option_box)

    def add_info_box(self, options):
        if self.info_box:
            self.remove_info_box()
        self.info_box = Overworld_Option_Box(top_left=(416,(SCREEN_HEIGHT-86)), options=options, use_arrow=False)
        self.add(self.info_box)
        for sprite in self.info_box:
            GAME_STATE["overworld_sprites"].add(sprite, layer=5)

    def remove_info_box(self):
        for s in self.info_box:
            s.kill()
            del s
        self.info_box = None

    def remove_option_box(self):
        for s in self.option_box:
            s.kill()
            del s
        self.option_box = self.previous_option_boxes[-1]
        self.number_of_option_boxes -= 1


class Overworld_Option_Box(pygame.sprite.Group):
    def __init__(self, top_left, options, use_buy_sound=False, use_arrow=True):
        super(Overworld_Option_Box, self).__init__()
        if len(options) == 2:
            menu_box_sprite = Overworld_Wide_Option_Box(top_left)
        elif len(options) == 3:
            top_left = (top_left[0], top_left[1] - 12)
            menu_box_sprite = Overworld_Wide_Option_Box_3(top_left)
        elif len(options) == 4:
            top_left = (top_left[0], top_left[1] - 24)
            menu_box_sprite = Overworld_Wide_Option_Box_4(top_left)
        elif len(options) == 5:
            top_left = (top_left[0], top_left[1] - 36)
            menu_box_sprite = Overworld_Wide_Option_Box_5(top_left)
        else:
            print(f'inalid number of options: {len(options)}')
        self.use_buy_sound = use_buy_sound
        self.options = options
        
        self.add(menu_box_sprite)
        self.curr_selection = 1
        self.final_selection = None
        self.final_selection_text = None

        self.build_options(top_left, options, use_arrow)
        self.curr_selection_text = self.options[self.curr_selection - 1]

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
            curr_width += int(temp_char.width/scale_factor)
            char_list.append(Regular_Font_Letter(char, (curr_width, y), recolor=recolor))
        for item in char_list:
            self.add(item)
            if visible:
                item.reveal()
            else:
                item.hide()
        return char_list
    
    def update(self):
        self.get_selection_input()

    def clear_all_text(self):
        for char_list in self.option_characters_list:
            for char in char_list:
                char.kill()
                self.remove(char)

    def get_selection_input(self):
        global GAME_STATE
        new_selection = None
        if GAME_STATE["just_pressed"] != None:
            if GAME_STATE["just_pressed"]["action"]:
                #if not self.use_buy_sound:
                #    select_sound()
                self.final_selection = self.curr_selection
                self.final_selection_text = self.options[self.final_selection - 1]
                print(self.final_selection)
                print(self.final_selection_text)
            else:
                if GAME_STATE["just_pressed"]["up"]:
                    if self.curr_selection > 1:
                        new_selection = self.curr_selection - 1
                if GAME_STATE["just_pressed"]["down"]:
                    if self.curr_selection < len(self.option_characters_list):
                        new_selection = self.curr_selection + 1
        if new_selection != None and new_selection != self.curr_selection and self.final_selection == None:
            self.option_characters_list[self.curr_selection - 1][0].hide()
            self.curr_selection = new_selection
            self.option_characters_list[self.curr_selection - 1][0].reveal()
            self.curr_selection_text = self.options[self.curr_selection - 1]
            change_selection_sound()


#---------SOUND EFFECTS

SFX_DICT = {}

def load_sfx_from_folder(base_path, folder_names, target_dict):
    for folder in folder_names:
        folder_path = os.path.join(base_path, folder)
        if not os.path.isdir(folder_path):
            continue  # skip if folder doesn't exist

        folder_key = os.path.basename(folder_path)
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                image_key = f"{folder_key}_{file}"
                target_dict[image_key] = pygame.mixer.Sound(file_path)

# Usage
folders_to_load = ["SFX"]

load_sfx_from_folder(PATH_START, folders_to_load, SFX_DICT)

def walking_sound():
    #if not walking_sfx_channel.get_busy():
        # Play the sound
    walking_sfx_channel.play(SFX_DICT["SFX_Walk.wav"])

def exit_all_menus_sound():
    #if not menu_sfx_channel.get_busy():
        # Play the sound
    menu_sfx_channel.play(SFX_DICT["SFX_ExitAllMenus.wav"])

def next_menu_sound():
    #if not menu_sfx_channel.get_busy():
        # Play the sound
    menu_sfx_channel.play(SFX_DICT["SFX_NextMenu.wav"])

def final_confirm_sound():
    menu_sfx_channel.play(SFX_DICT["SFX_FinalConfirm.wav"])

def change_selection_sound():
    menu_sfx_channel.play(SFX_DICT["SFX_ChangeSelection.wav"])




#---------UTILITIES
def get_move_vector():
    keys = GAME_STATE["pressed_keys"]
    dx = 0
    dy = 0

    # Tiles move opposite to player input
    if keys["up"]:
        dy = 1   # moving tiles down = player moves up
    if keys["down"]:
        dy = -1  # moving tiles up = player moves down
    if keys["left"]:
        dx = 1   # moving tiles right = player moves left
    if keys["right"]:
        dx = -1  # moving tiles left = player moves right

    # Normalize diagonal movement
    if dx != 0 and dy != 0:
        magnitude = math.sqrt(dx**2 + dy**2)
        dx /= magnitude
        dy /= magnitude

    return dx, dy

def get_character_move_vector(dx, dy):

    # Normalize diagonal movement
    if dx != 0 and dy != 0:
        magnitude = math.sqrt(dx**2 + dy**2)
        dx /= magnitude
        dy /= magnitude

    return dx, dy



def kill_and_delete(object):
    object.kill()
    del object

def initialize_overworld():
    global GAME_STATE
    if not GAME_STATE["tileset_current"]:
        print('Initializing Overworld')
        for sprite in GAME_STATE["tileset_group"]:
            GAME_STATE["overworld_sprites"].add(sprite, layer=1)
        for sprite in GAME_STATE["building_group"]:
            GAME_STATE["overworld_sprites"].add(sprite, layer=2)
        for sprite in GAME_STATE["character_group"]:
            GAME_STATE["overworld_sprites"].add(sprite, layer=3)

        GAME_STATE["cursor"] = Cursor()
        GAME_STATE["overworld_sprites"].add(GAME_STATE["cursor"], layer=6)
        GAME_STATE["main_bottom_textbox"] = None

        GAME_STATE["selectedtile"] = SelectedTile()
        GAME_STATE["overworld_sprites"].add(GAME_STATE["selectedtile"], layer=5)
        print('Overworld Initialized')
        GAME_STATE["TopStatusBar"] = Overworld_Menu(input_string='$Day 001 00:00 Money $005000 Tourists: 0 Busy/1 Total Spookiness: 000', text_type='immediate', special_top_left=True)
        #GAME_STATE["TopStatusBar"].update_curr_text()
        for sprite in GAME_STATE["TopStatusBar"]:
            GAME_STATE["overworld_sprites"].add(sprite, layer=6)
        GAME_STATE["tileset_current"] = True


def get_inputs():
    if GAME_STATE["in_menu"] == True:
        GAME_STATE["pressed_keys"] = None
        for event in pygame.event.get():
            if event.type == KEYDOWN:
                # If the Escape key is pressed, stop the loop
                # Detect any key press (only print if no other key is being held)
                if not GAME_STATE["key_pressed"]:
                    #print("Key pressed:", event.key)
                    GAME_STATE["key_pressed"] = True
                    GAME_STATE["pressed_keys"] = pygame.key.get_pressed()
            elif event.type == KEYUP:
                # Reset the key_pressed flag when the key is released
                GAME_STATE["key_pressed"]  = False

            # Handle the quit event
            elif event.type == pygame.QUIT:
                #print("Quit event triggered")
                GAME_STATE["running"] = False

            #elif event.type == pygame.WINDOWFOCUSLOST:
            #    print("Window lost focus! Pausing unnecessary updates.")
    else:
        # Reset keys at the start of each frame (so releases are handled)
        DEAD_ZONE = 0.3  # Change this value to tweak sensitivity

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                GAME_STATE["running"] = False
            #elif event.type == pygame.WINDOWFOCUSLOST:
            #    print("Window lost focus! Pausing unnecessary updates.")

            # --- Keyboard input ---
            elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                keys = pygame.key.get_pressed()
                GAME_STATE["pressed_keys"]["up"] = keys[pygame.K_UP]
                GAME_STATE["pressed_keys"]["down"] = keys[pygame.K_DOWN]
                GAME_STATE["pressed_keys"]["left"] = keys[pygame.K_LEFT]
                GAME_STATE["pressed_keys"]["right"] = keys[pygame.K_RIGHT]
                GAME_STATE["pressed_keys"]["action"] = keys[pygame.K_RETURN]
                GAME_STATE["pressed_keys"]["back"] = keys[pygame.K_TAB]

            # --- Controller buttons ---
            elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                is_pressed = event.type == pygame.JOYBUTTONDOWN

                # X button (confirm)
                if event.button == 0:
                    GAME_STATE["pressed_keys"]["action"] = is_pressed
                if event.button == 1:
                    GAME_STATE["pressed_keys"]["back"] = is_pressed

                # D-pad buttons (example mapping)
                elif event.button == 11:
                    GAME_STATE["pressed_keys"]["up"] = is_pressed
                elif event.button == 14:
                    GAME_STATE["pressed_keys"]["right"] = is_pressed
                elif event.button == 12:
                    GAME_STATE["pressed_keys"]["down"] = is_pressed
                elif event.button == 13:
                    GAME_STATE["pressed_keys"]["left"] = is_pressed

            # --- Controller D-pad (usually axes 6/7 on DualSense) ---
            elif event.type == pygame.JOYAXISMOTION:
                # Axis 0 = X, Axis 1 = Y
                axis_val = event.value

                if event.axis == 0:  # Left/Right
                    if abs(axis_val) < DEAD_ZONE:
                        GAME_STATE["pressed_keys"]["left"] = False
                        GAME_STATE["pressed_keys"]["right"] = False
                    else:
                        GAME_STATE["pressed_keys"]["left"] = axis_val < -DEAD_ZONE
                        GAME_STATE["pressed_keys"]["right"] = axis_val > DEAD_ZONE

                elif event.axis == 1:  # Up/Down
                    if abs(axis_val) < DEAD_ZONE:
                        GAME_STATE["pressed_keys"]["up"] = False
                        GAME_STATE["pressed_keys"]["down"] = False
                    else:
                        GAME_STATE["pressed_keys"]["up"] = axis_val < -DEAD_ZONE
                        GAME_STATE["pressed_keys"]["down"] = axis_val > DEAD_ZONE

def update_input_edges():
    global GAME_STATE
    GAME_STATE["just_pressed"] = {}
    for key, pressed in GAME_STATE["pressed_keys"].items():
        prev = GAME_STATE["prev_pressed_keys"].get(key, False)
        GAME_STATE["just_pressed"][key] = (pressed and not prev)  # pressed this frame, not last
    #return just_pressed
    GAME_STATE["prev_pressed_keys"] = GAME_STATE["pressed_keys"].copy()

def kill_menu_and_clear():
    global GAME_STATE
    for s in GAME_STATE["OverworldMenu"]:
        s.kill()
        del s
    GAME_STATE["OverworldMenu"] = None
    if GAME_STATE["hover_building"] != None:
        if GAME_STATE["hover_building"].building != "Nothing":
            GAME_STATE["hover_building"].kill()
        del GAME_STATE["hover_building"]
        GAME_STATE["hover_building"] = None
    

def find_nearest_building(df_pos, target_building):
    global GAME_STATE
    GAME_STATE["building_group"].tile_map
    # Get coordinates of all building cells
    store_positions = np.argwhere(GAME_STATE["building_group"].tile_map.values == target_building)

    if len(store_positions) == 0:
        closest_pos = None
    else:
        # Compute distances from player_pos to each building
        distances = [np.linalg.norm(np.array(df_pos) - np.array(hp)) for hp in store_positions]

        # Combine distances and positions for tie-breaking
        sorted_stores = sorted(
            zip(distances, store_positions.tolist()),
            key=lambda x: (x[0], x[1][0], x[1][1])  # sort by distance, then row, then col
        )

        closest_pos = tuple(sorted_stores[0][1])

    return closest_pos

def find_nearest_building_path(df_pos, target_building):
    building_map = GAME_STATE["building_map_np"]
    tiles_map = GAME_STATE["tiles_map_np"]
    nrows, ncols = building_map.shape

    start = tuple(df_pos)
    directions = [(-1,0), (1,0), (0,-1), (0,1)]  # up, down, left, right

    queue = deque([start])
    visited = set([start])
    parent = {start: None}

    while queue:
        r, c = queue.popleft()

        if building_map[r, c] == target_building:
            if target_building != "Exit":
                curr_building = GAME_STATE["building_group"].tiles_dict[f"{r}_{c}"]
                if not isinstance(curr_building, Individual_Sprite):
                    curr_building = GAME_STATE["building_group"].tiles_dict[curr_building]
                if len(curr_building.tourists) >= curr_building.tourist_capacity:
                    continue
            #Get building, check capacity, skip if its 5
            # Reconstruct path
            path = []
            node = (r, c)
            while node is not None:
                path.append(node)
                node = parent[node]
            path.reverse()
            return path

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < nrows and 0 <= nc < ncols and (nr, nc) not in visited:
                b_val = building_map[nr, nc]
                t_val = tiles_map[nr, nc]
                #if f"{r}_{c}" in GAME_STATE["building_group"].tiles_dict:
                    #curr_building = GAME_STATE["building_group"].tiles_dict[f"{r}_{c}"]
                    #if not isinstance(curr_building, Individual_Sprite):
                    #   curr_building = GAME_STATE["building_group"].tiles_dict[curr_building]
                    #if len(curr_building.tourists) >= (curr_building.tourist_capacity - 1):
                    #    print('too many tourists other check')
                    #    continue
                if (str(b_val) in ["0", "front", "Exit"] and str(t_val) in ["1", "3"]) or b_val == target_building:
                    visited.add((nr, nc))
                    parent[(nr, nc)] = (r, c)
                    queue.append((nr, nc))
    #print(f'No path to {target_building} from {df_pos} found!')
    return None


def character_move(character, dx, dy, speed, dt):
    #print(f'dt is {dt}')
    #if dt > (1/300.0):
        #print('bigger')
    dt = min(dt, 1/float(TARGET_FPS)) #Check how this works with 60 FPS
    move_x = dx * speed * dt * scale_factor #float, usually -.2 something
    move_y = dy * speed * dt * scale_factor
    if abs(move_x) > 1 * scale_factor:
        #print('ayy')
        if move_x > 0:
            move_x = 1 * scale_factor
        else:
            move_x = -1 * scale_factor
        #print(move_x)
    if move_y > 1 * scale_factor:
        #print('ohh')
        if move_y > 0:
            move_y = 1 * scale_factor
        else:
            move_y = -1 * scale_factor
        #print(move_y)
    prev_character_rect_x = character.rect.x
    prev_character_rect_y = character.rect.y
    prev_pos_x = character.pos_x
    prev_pos_y = character.pos_y
    #print(f"{prev_character_rect_x}, {prev_character_rect_y}")
    #print(move_x)
    character.pos_x += (move_x)
    character.pos_y += (move_y)
    character.rect.x = round(character.pos_x) #when enough for it to be an int changes, this changes
    character.rect.y = round(character.pos_y)
    
    #print(f"pixels moved: {character.pixels_moved}")
    x_pixels_moved = character.rect.x - prev_character_rect_x #accurately detects pixels moved
    y_pixels_moved = character.rect.y - prev_character_rect_y
    x_pixels_moved = character.pos_x - prev_pos_x
    y_pixels_moved = character.pos_y - prev_pos_y
    character.pixels_moved += abs(x_pixels_moved)
    character.pixels_moved += abs(y_pixels_moved)
    #if x_pixels_moved not in [-1, 0, 1] or y_pixels_moved not in [-1, 0, 1]:
        #print(f"Character moved x {x_pixels_moved}, y {y_pixels_moved}")
    #print(f"now pixels moved: {character.pixels_moved}")
    if character.pixels_moved >= (16 * scale_factor):
        #print('changing target')
        GAME_STATE["temp_character_group_dict"].pop(f"{character.df_pos[0]}_{character.df_pos[1]}_{character.unique_id}", None)
        character.df_pos = (character.df_pos[0] + dy, character.df_pos[1] + dx)
        if not character.has_touched_grass:
            check_if_grass = get_displayed_tile_at_pos(character.df_pos)
            if str(check_if_grass) in ["1", "3", "4"]:
                print('grass touched')
                character.has_touched_grass = True
        GAME_STATE["temp_character_group_dict"][f"{character.df_pos[0]}_{character.df_pos[1]}_{character.unique_id}"] = character
        character.target = character.target[1:]
        #What if they move way more than 16 pixels?
        tile_size = 16 * scale_factor
        multiplier = math.floor(character.pixels_moved / tile_size)
        character.pixels_moved -= tile_size * multiplier



        #print(f'Target:  {character.target}')
        #print(f'Curr position: {character.df_pos}')
    #print(f"{character.rect.x}, {character.rect.y}")

    #new_pos = (int(character.rect.centery // (16 * scale_factor)), int(character.rect.centerx // (16 * scale_factor)))
    #print(new_pos)
    

    #print(f"Character df_pos: {character.df_pos}")
    #tile_below = character.get_best_sprite_below()
    #print(f"Tile below df_pos: {tile_below.df_pos}")
    #if tile_below.df_pos == character.target[0]:
        #character.target = character.target[1:]
        #character.df_pos = tile_below.df_pos
    '''
    character.df_pos_float[0] += ((character.rect.y - prev_character_rect_y)/16)
    character.df_pos_float[1] += ((character.rect.x - prev_character_rect_x)/16)
    if (math.floor(character.df_pos_float[0]) != character.df_pos[0]) or (math.floor(character.df_pos_float[1]) != character.df_pos[1]):
        character.df_pos = (math.floor(character.df_pos_float[0]), math.floor(character.df_pos_float[1]))
    '''
        # optionally print or trigger tile-entry events here


def character_check_direction(character):
    curr_target = character.target[0]

    if character.df_pos[0] > curr_target[0]:
        character.direction = 'Backward'
        return (0, -1)
    elif character.df_pos[0] < curr_target[0]:
        character.direction = 'Forward'
        return (0, 1)
    else: 
        if character.df_pos[1] > curr_target[1]:
            character.direction = 'Left'
            return (-1, 0)
        else:
            character.direction = 'Right'
            return (1, 0)
    
        

def get_tile_at_pos(pos):
    x, y = pos
    if f"{x}_{y}" in GAME_STATE["tileset_group"].tiles_dict:
        tile_number = GAME_STATE["tileset_group"].tiles_dict[f"{x}_{y}"]
    else:
        tile_number = None
    return tile_number

def get_displayed_tile_at_pos(pos):
    x, y = pos
    if f"{x}_{y}" in GAME_STATE["tileset_group"].tiles_dict:
        tile_number = GAME_STATE["tileset_group"].tiles_dict[f"{x}_{y}"].displayed_tile
    else:
        tile_number = None
    return tile_number


def character_check_move(character):
    #print()
    global GAME_STATE
    dx = 0
    dy = 0

    dx, dy = character_check_direction(character)
    dx, dy = get_character_move_vector(dx, dy)
    if dx != 0 or dy != 0:
        character.moving = True
        #tile_below = get_tile_at_pos((character.df_pos[1] + dx, character.df_pos[0] + dy))
        #if tile_below.tile_number != 4: #This will need to also account for buildings and other characters eventually
        character_move(character, dx, dy, speed=60, dt=GAME_STATE["delta_time"])
        character.character_moving_animation()
        #else:
            #print('blocked by tile')

def open_building_door(character):
    global GAME_STATE
    r, c = character.df_pos
    #self.tile_map.iat[r, c] = 0
    curr_building = GAME_STATE["building_group"].tiles_dict[f"{r}_{c}"]
    if not isinstance(curr_building, Individual_Sprite):
        curr_building = GAME_STATE["building_group"].tiles_dict[curr_building]
    if not curr_building.door_open:
        curr_building.open_door()
        GAME_STATE["buildings_to_close_door"].append(curr_building)
    if character.target == None:
        character.target = [(character.df_pos[0] -1, character.df_pos[1])]
        

def close_building_door(character):
    #print('after character moves, close the door, despawn character, add character to buildings list')
    global GAME_STATE
    r, c = character.df_pos
    #self.tile_map.iat[r, c] = 0
    curr_building = GAME_STATE["building_group"].tiles_dict[f"{r}_{c}"]
    if not isinstance(curr_building, Individual_Sprite):
        curr_building = GAME_STATE["building_group"].tiles_dict[curr_building]
    if character.character_type == 'Tourist':
        list_to_append = [character.character_type, character.goal_destinations[1:], 0, character.has_touched_grass]
        curr_building.tourists.append(list_to_append) #Change this to add a list with timer, then after timer changes character comes back out and money goes up
        #Tourists will need a goal
    #print('remove the tourist')
    GAME_STATE["character_group"].remove_character(character)
    GAME_STATE["number_tourists_busy"] += 1
    clear_character_targets()

def clear_character_targets():
    global GAME_STATE
    for character in GAME_STATE["character_group"].tiles_dict.values():
        if isinstance(character, Individual_Sprite):
            #print('found')
            if character.target:
                character.target = [character.target[0]]
                #character.check_buffer = 20
                #character.moving = False
                #character.character_stop_moving()

def replace_character_dict():
    if GAME_STATE["temp_character_group_dict"] != GAME_STATE["character_group"].tiles_dict:
        GAME_STATE["character_group"].tiles_dict = GAME_STATE["temp_character_group_dict"]
        GAME_STATE["temp_character_group_dict"] = GAME_STATE["character_group"].tiles_dict.copy()

def update_character_positions():
    global GAME_STATE
    for character in GAME_STATE["character_group"].tiles_dict.values():
        if isinstance(character, Individual_Sprite):
            if character.target is None:
                now = pygame.time.get_ticks()
                if now - character.last_check_update < (1000/60): #Adjust as needed, currently one tick every 60 seconds
                    continue
                character.last_check_update = now
                if character.check_buffer == 0:
                    if character.goal_destinations != []:
                        character.target = find_nearest_building_path(character.df_pos, character.goal_destinations[0])
                        if character.target is None:
                            character.check_buffer = 20
                        else:
                            character.target = character.target[1:]
                else:
                    character.check_buffer -= 1
            else:
                if character.target == [] and not character.at_destination:
                    character.moving = False
                    character.check_buffer = 0
                    character.character_stop_moving()
                    character.target = None
                    if GAME_STATE["building_group"].tile_map.iat[character.df_pos[0], character.df_pos[1]] == character.goal_destinations[0]:
                        character.at_destination = True
                        if character.goal_destinations[0] == 'Exit':
                            if not character.has_touched_grass:
                                GAME_STATE["spookiness"] += 1
                                print('Bonus spooky point!')
                            GAME_STATE["character_group"].remove_character(character)
                            GAME_STATE["number_tourists"] -= 1
                        else:
                            open_building_door(character)
                elif character.target == [] and character.at_destination:
                    close_building_door(character)
                elif character.target[-1] != character.df_pos:
                    character_check_move(character)

def spawn_new_tourists():
    global GAME_STATE
    now = pygame.time.get_ticks()
    if now - GAME_STATE["last_check_character_update"] >= 5000:
        GAME_STATE["last_check_character_update"] = now
        #34, 0 and 99, 0
        value = random.choice([0, 1])
        if value == 0:
            new_pos = (34, 0)
        else:
            new_pos = (34, 99)
        GAME_STATE["character_group"].add_character(new_pos)
        GAME_STATE["number_tourists"] += 1


def tourist_exit_building(building, index):
    global GAME_STATE
    #Get building's entrance
    r, c = building.df_pos
    if building.building == 'Store':
        r = r + 4
        c = c + 3
    elif building.building == 'Apartment':
        r = r + 3
        c = c + 1
    elif building.building == 'Diner':
        r = r + 4
        c = c + 2
    new_pos = (r, c)
    destination_list = building.tourists[index][1]
    print(new_pos)
    print(destination_list)
    grass_touched = building.tourists[index][2]
    GAME_STATE["character_group"].add_character(new_pos, destination_list, grass_touched)
    GAME_STATE["number_tourists_busy"] -= 1
    clear_character_targets()
    if not building.door_open:
        building.open_door()
        GAME_STATE["buildings_to_close_door"].append(building)
    row = GAME_STATE["stats_dataframe"].loc[GAME_STATE["stats_dataframe"]["Building"] == building.building]
    if row.empty:
        print(f"No data found for '{building.building}'")
    else:
        row = row.iloc[0]
        GAME_STATE["money"] += int(row['Revenue'])
        
    #Create tourist at that position

def close_building_doors():
    global GAME_STATE
    indexes_to_remove = []
    for i, building in enumerate(GAME_STATE["buildings_to_close_door"]):
        now = pygame.time.get_ticks()
        if now - building.last_check_update < (12000/60): #Adjust as needed, currently one tick every 60 seconds
            continue
        building.last_check_update = now
        if building.door_open:
            building.close_door()
        indexes_to_remove.append(i)
    for i in sorted(indexes_to_remove, reverse=True):
        del GAME_STATE["buildings_to_close_door"][i]


def update_in_game_time():
    global GAME_STATE
    if GAME_STATE["tileset_current"]:
        now = pygame.time.get_ticks()
        if now - GAME_STATE["last_check_clock_update"] >= 25: #375 real, 25 for 15x time
            GAME_STATE["last_check_clock_update"] = now
            GAME_STATE["current_minute"] += 1

            # Advance to next day
            if GAME_STATE["current_minute"] == 1440:
                GAME_STATE["current_day"] += 1
                GAME_STATE["current_minute"] = 0

            for building in GAME_STATE["building_group"]:
                if building.tourists:
                    indexes_to_remove = []
                    for i, curr_tourist in enumerate(building.tourists):
                        curr_tourist[2] += 1
                        if curr_tourist[2] == 60:
                            print(f"Tourist #{i} in {building} is ready to go")
                            tourist_exit_building(building=building,index=i)
                            indexes_to_remove.append(i)
                    for i in sorted(indexes_to_remove, reverse=True):
                        del building.tourists[i]
        
def update_top_display():
    global GAME_STATE
    if GAME_STATE["tileset_current"]:
        # --- Format time string ---
        day_str = f"{GAME_STATE['current_day']:03d}"  # always 3 digits, e.g. 001, 042, 123
        hours = GAME_STATE["current_minute"] // 60     # 0–23
        minutes = GAME_STATE["current_minute"] % 60    # 0–59
        time_str = f"{hours:02d}:{minutes:02d}"        # always HH:MM
        tourists_busy = f"{GAME_STATE["number_tourists_busy"]:03d}"
        tourists = f"{GAME_STATE["number_tourists"]:03d}"
        money = f"{GAME_STATE["money"]:06d}"
        spooky = f"{GAME_STATE["spookiness"]:06d}"

        display_str = f"Day {day_str} {time_str} Money ${money} Tourists: {tourists_busy} Busy/{tourists} Total Spookiness: {spooky}"
        if GAME_STATE["top_display_string"] != display_str:
            GAME_STATE["TopStatusBar"].change_curr_text(input_string=display_str, text_type='immediate')
            GAME_STATE["top_display_string"] = display_str

        
def construct_stats_list(building, inspecting=False):
    global GAME_STATE
    if inspecting == True:
        row = GAME_STATE["stats_dataframe"].loc[GAME_STATE["stats_dataframe"]["Building"] == building.building]
        if row.empty:
            return [f"No data found for '{building.building}'"]
    else:
        row = GAME_STATE["stats_dataframe"].loc[GAME_STATE["stats_dataframe"]["Building"] == building]
        if row.empty:
            return [f"No data found for '{building}'"]

    row = row.iloc[0]

    # Convert VisitTime (minutes) to a readable format
    if row["VisitTime"] >= 60:
        hours = int(row["VisitTime"] / 60)
        visit_time_str = f"Visit Time: {hours} Hour{'s' if hours != 1 else ''}"
    elif row["VisitTime"] == 0:
        visit_time_str = f"Visit Time: --"
    else:
        visit_time_str = f"Visit Time: {row['VisitTime']} Min"

    if row["Revenue"] != 0:
        revenue_str = f"Revenue: ${row['Revenue']}"
    else:
        revenue_str = f"Revenue: --"

    if inspecting:
        refund_str = f"Amount Refunded ${int(row['Cost']/2)}"

    if row["Capacity"] != 0:
        if inspecting:
            tourists_str = f"{len(building.tourists)} Tourists/{row['Capacity']} Max Capacity"
            capacity_str = ''
        else:
            capacity_str = f"Capacity: {row['Capacity']}"
        
    else:
        capacity_str = f"Capacity: --"
        tourists_str = f"Capacity: --" 

    

    # Create the info list
    info = [
        f"Cost: ${row['Cost']}",
        visit_time_str,
        revenue_str,
        capacity_str,
        f"Spooky Score: {row['Spookiness']}"
    ]
    if inspecting:
        print('yes inspecting')
        info = [refund_str,
            visit_time_str,
            revenue_str,
            tourists_str,
            f"Spooky Score: {row['Spookiness']}"
        ]

    GAME_STATE["current_stats_displayed"] = info
    print(GAME_STATE["current_stats_displayed"])
    info_normal = [row['Cost'],
        row["VisitTime"],
        row["Revenue"],
        row["Capacity"],
        row['Spookiness']
    ]
    GAME_STATE["current_stats"] = info_normal

def landscape_tile(adding=True):
    print('landscaping')
    r, c = GAME_STATE["selectedtile"].tile.df_pos
    main_tile = GAME_STATE["tileset_group"].tiles_dict[f"{r}_{c}"]

    offsets = [
        (-1, -1), (-1, 0), (-1, 1),  # 7, 8, 9
        (0, -1),  (0, 0),  (0, 1),   # 4, 5, 6
        (1, -1),  (1, 0),  (1, 1)    # 1, 2, 3
    ]

    grid = {}
    for dr, dc in offsets:
        key = (r + dr, c + dc)
        grid[key] = GAME_STATE["tileset_group"].tiles_dict.get(f"{r + dr}_{c + dc}")

    # Helper function
    def is_grass(tile):
        if tile in ["1", "3", "4"]:
            return True
        return False
    
    def is_grass_safe(tile_or_str):
        if tile_or_str is None:
            return True   # treat None/out-of-bounds as grass for border/overlay logic
        # if it's a tile object, extract its displayed_tile attribute
        if hasattr(tile_or_str, "displayed_tile"):
            val = tile_or_str.displayed_tile
        else:
            val = tile_or_str
        return val in ("1", "3", "4")

    #print(grid)
    # Directions
    directions = {
        "top": (-1, 0),
        "bottom": (1, 0),
        "left": (0, -1),
        "right": (0, 1)
    }

    if adding == True:
        main_tile.change_tile("center")
    else:
        main_tile.change_tile("1")

    # Check each tile in the 3x3 area
    all_tiles_skipped = True
    for (tr, tc), tile in grid.items():
        if tile is None or is_grass(tile.displayed_tile):
            continue  # Skip grass tiles
        all_tiles_skipped = False
        # Start with any existing borders from the tile's displayed name
        existing = tile.displayed_tile.split('_')
        borders = [b for b in existing if b in ["top", "bottom", "left", "right"]]

        # Add new borders based on surrounding grass
        for dir_name, (dr, dc) in directions.items():
            neighbor = grid.get((tr + dr, tc + dc))
            if neighbor == main_tile and dir_name in borders:
                borders.remove(dir_name)
            if neighbor is not None and is_grass(neighbor.displayed_tile):
                if dir_name not in borders:
                    borders.append(dir_name)

        # Ensure order is always consistent: top, bottom, left, right
        order = ["top", "bottom", "left", "right"]
        borders = [b for b in order if b in borders]

        # Handle corner overlays (diagonal grass between non-grass sides)
        overlays = []
        if not is_grass_safe(grid.get((tr - 1, tc))) and not is_grass_safe(grid.get((tr, tc + 1))) and is_grass_safe(grid.get((tr - 1, tc + 1))):
            overlays.append("top_right_overlay")
        if not is_grass_safe(grid.get((tr - 1, tc))) and not is_grass_safe(grid.get((tr, tc - 1))) and is_grass_safe(grid.get((tr - 1, tc - 1))):
            overlays.append("top_left_overlay")
        if not is_grass_safe(grid.get((tr + 1, tc))) and not is_grass_safe(grid.get((tr, tc + 1))) and is_grass_safe(grid.get((tr + 1, tc + 1))):
            overlays.append("bottom_right_overlay")
        if not is_grass_safe(grid.get((tr + 1, tc))) and not is_grass_safe(grid.get((tr, tc - 1))) and is_grass_safe(grid.get((tr + 1, tc - 1))):
            overlays.append("bottom_left_overlay")
        if overlays:
            print(f"{tr, tc}: {overlays}")
        # Apply changes
        if borders:
            tile.change_tile(f"{'_'.join(borders)}")
        else:
            tile.change_tile(f"center")
        if overlays:
            tile.set_corner_borders(overlays)
    


    


#---------GAME PHASES
def titlescreen_phase():
    global GAME_STATE
    if GAME_STATE["title_screen"] == None:
        GAME_STATE["title_screen"] = Title_Screen()
        GAME_STATE["overworld_sprites"].add(GAME_STATE["title_screen"], layer=9)
    elif GAME_STATE["just_pressed"] and GAME_STATE["just_pressed"]["action"]:
        kill_and_delete(GAME_STATE["title_screen"])
        GAME_STATE["current_phase"] = overworld_phase
        

def overworld_phase():
    global GAME_STATE
    if not GAME_STATE["tileset_current"]:
        initialize_overworld()
    if GAME_STATE["just_pressed"]["action"] and not GAME_STATE["just_pressed"]["back"]:
        GAME_STATE["current_phase"] = interact_with_tile_phase
        next_menu_sound()
    else:
        GAME_STATE["tileset_group"].check_move()
        tile_below = GAME_STATE["cursor"].get_best_sprite_below()
        GAME_STATE["selectedtile"].update_tile(tile_below)

def interact_with_tile_phase():
    global GAME_STATE
    if not GAME_STATE["OverworldMenu"]:
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        if str(GAME_STATE["building_group"].tile_map.iat[r, c]) == "0":  # or whatever value you want
            GAME_STATE["OverworldMenu"] = Overworld_Menu('What would you like to do?', options=["Place Building", "Place Object", "Landscape", "Nothing"], text_type='not_arrow')
        else:
            GAME_STATE["OverworldMenu"] = Overworld_Menu('What would you like to do?', options=["Remove Building", "Landscape", "Nothing"], text_type='not_arrow')
            curr_building = GAME_STATE["building_group"].tiles_dict[f"{r}_{c}"]
            if not isinstance(curr_building, Individual_Sprite):
                curr_building = GAME_STATE["building_group"].tiles_dict[curr_building]
            print(curr_building)
            construct_stats_list(curr_building, inspecting=True)
            GAME_STATE["OverworldMenu"].add_info_box(options=GAME_STATE["current_stats_displayed"])
        for sprite in GAME_STATE["OverworldMenu"]:
            GAME_STATE["overworld_sprites"].add(sprite, layer=6)
    if GAME_STATE["OverworldMenu"].curr_text.all_letters_set == False:
        #print('trying to update text')
        GAME_STATE["OverworldMenu"].update_curr_text()
    GAME_STATE["OverworldMenu"].update_option_box()
    if GAME_STATE["just_pressed"]["back"] or (GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Nothing"):
        kill_menu_and_clear()
        exit_all_menus_sound()
        GAME_STATE["current_phase"] = overworld_phase
    elif GAME_STATE["OverworldMenu"].option_box.final_selection_text in ["Place Building", "Place Object"]:
        if GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Place Building":
            GAME_STATE["OverworldMenu"].add_option_box(options=["Store", "Apartment", "Diner", "Nothing"])
            construct_stats_list("Store")
        else:
            GAME_STATE["OverworldMenu"].add_option_box(options=["Tree", "Pumpkin", "Nothing"])
            construct_stats_list("Tree")
        GAME_STATE["OverworldMenu"].add_info_box(options=GAME_STATE["current_stats_displayed"])
        for sprite in GAME_STATE["OverworldMenu"].option_box:
            GAME_STATE["overworld_sprites"].add(sprite, layer=6)
        if GAME_STATE["hover_building"] == None:
            GAME_STATE["hover_building"] = Hover_Building((int(GAME_STATE["selectedtile"].pos_x/scale_factor), int(GAME_STATE["selectedtile"].pos_y/scale_factor)), GAME_STATE["OverworldMenu"].option_box.curr_selection_text)
            GAME_STATE["overworld_sprites"].add(GAME_STATE["hover_building"], layer=4)
        next_menu_sound()
    elif GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Remove Building":
        check_building_removed_successful = GAME_STATE["building_group"].remove_building()
        if check_building_removed_successful:
            kill_menu_and_clear()
            GAME_STATE["current_phase"] = overworld_phase
            final_confirm_sound()
        else: 
            GAME_STATE["OverworldMenu"].option_box.final_selection = None
            GAME_STATE["OverworldMenu"].option_box.final_selection_text = None
            GAME_STATE["OverworldMenu"].change_curr_text('Cannot remove a building while people are in it.', text_type='not arrow')
    elif GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Landscape":
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        if str(get_displayed_tile_at_pos((r,c))) in ["1", "3", "4"]:
            GAME_STATE["OverworldMenu"].add_option_box(options=["Place Cement Tile $30", "Nothing"])
            for sprite in GAME_STATE["OverworldMenu"].option_box:
                GAME_STATE["overworld_sprites"].add(sprite, layer=6)
            next_menu_sound()
        else:
            GAME_STATE["OverworldMenu"].add_option_box(options=["Remove Cement Tile", "Nothing"])
            for sprite in GAME_STATE["OverworldMenu"].option_box:
                GAME_STATE["overworld_sprites"].add(sprite, layer=6)
            next_menu_sound()
    elif GAME_STATE["OverworldMenu"].option_box.final_selection != None and GAME_STATE["OverworldMenu"].option_box.final_selection_text not in ["Place Cement Tile $30", "Remove Cement Tile"] and GAME_STATE["OverworldMenu"].number_of_option_boxes == 2:
        check_building_added_successful = GAME_STATE["building_group"].add_building(GAME_STATE["OverworldMenu"].option_box.final_selection_text)
        if check_building_added_successful == 'pass':
            kill_menu_and_clear()
            GAME_STATE["current_phase"] = overworld_phase
            final_confirm_sound()
            GAME_STATE["money"] -= GAME_STATE["current_stats"][0]
            GAME_STATE["spookiness"] += GAME_STATE["current_stats"][4]
        else: 
            GAME_STATE["OverworldMenu"].option_box.final_selection = None
            if check_building_added_successful == 'no space':
                GAME_STATE["OverworldMenu"].change_curr_text('That building will not fit.', text_type='not arrow')
            elif check_building_added_successful == "no money":
                GAME_STATE["OverworldMenu"].change_curr_text('Cannot afford this building.', text_type='not arrow')
            else:
                GAME_STATE["OverworldMenu"].change_curr_text('Cannot place a building on top of a person.', text_type='not arrow')
    elif GAME_STATE["OverworldMenu"].option_box.final_selection != None and GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Place Cement Tile $30" and GAME_STATE["OverworldMenu"].number_of_option_boxes == 2:
        landscape_tile()
        kill_menu_and_clear()
        GAME_STATE["current_phase"] = overworld_phase
        final_confirm_sound()
        GAME_STATE["money"] -= 30
    elif GAME_STATE["OverworldMenu"].option_box.final_selection != None and GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Remove Cement Tile" and GAME_STATE["OverworldMenu"].number_of_option_boxes == 2:
        landscape_tile(adding=False)
        kill_menu_and_clear()
        GAME_STATE["current_phase"] = overworld_phase
        final_confirm_sound()
        GAME_STATE["money"] += 15
    elif GAME_STATE["hover_building"] != None:
        if GAME_STATE["hover_building"].building != GAME_STATE["OverworldMenu"].option_box.curr_selection_text:
            if GAME_STATE["hover_building"].building != "Nothing":
                GAME_STATE["hover_building"].kill()
            del GAME_STATE["hover_building"]
            GAME_STATE["hover_building"] = Hover_Building((int(GAME_STATE["selectedtile"].pos_x/scale_factor), int(GAME_STATE["selectedtile"].pos_y/scale_factor)), GAME_STATE["OverworldMenu"].option_box.curr_selection_text)
            if GAME_STATE["hover_building"].building != "Nothing":
                GAME_STATE["overworld_sprites"].add(GAME_STATE["hover_building"], layer=4)
                construct_stats_list(GAME_STATE["OverworldMenu"].option_box.curr_selection_text)
                GAME_STATE["OverworldMenu"].add_info_box(options=GAME_STATE["current_stats_displayed"])
            else:
                GAME_STATE["OverworldMenu"].remove_info_box()
        else:
            if GAME_STATE["hover_building"].building != "Nothing":
                GAME_STATE["hover_building"].fade_in_and_out()
    elif GAME_STATE["current_stats_displayed"] and "Max Capacity" in GAME_STATE["current_stats_displayed"]:
        previous_stats_list = GAME_STATE["current_stats_displayed"]
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        curr_building = GAME_STATE["building_group"].tiles_dict[f"{r}_{c}"]
        if not isinstance(curr_building, Individual_Sprite):
            curr_building = GAME_STATE["building_group"].tiles_dict[curr_building]
        construct_stats_list(curr_building, inspecting=True)
        if previous_stats_list != GAME_STATE["current_stats_displayed"]:
            GAME_STATE["OverworldMenu"].add_info_box(options=GAME_STATE["current_stats_displayed"])

        




#Initialize Global Variables

maps_path = os.path.join(PATH_START, "Maps")
backgroundtiles_path = os.path.join(maps_path, "BackgroundTiles.txt")
tile_map = pd.read_csv(backgroundtiles_path, sep='\t', header=None)

buildingmap_path = os.path.join(maps_path, "Buildings.txt")
building_map_fromsheet = pd.read_csv(buildingmap_path, sep='\t', header=None)
character_map = tile_map.copy()
character_map[:] = 0
character_map.iat[34, 0] = "test"
#character_map.iat[50, 50] = "test"
stats_path = os.path.join(maps_path, "BuildingStats.txt")
stats_dataframe = pd.read_csv(stats_path, sep='\t')

# Detect how many controllers are connected

joystick_count = pygame.joystick.get_count()
print(f"Joysticks detected: {joystick_count}")

if joystick_count > 0:
    joystick = pygame.joystick.Joystick(0)  # grab the first controller
    joystick.init()
    print(f"Controller name: {joystick.get_name()}")
    joystick.rumble(0.5, 1, 5000)


GAME_STATE = {
"running": True,
"clock": pygame.time.Clock(),
"in_menu": False,
"overworld_sprites": pygame.sprite.LayeredUpdates(),
"title_screen": None,
"pressed_keys": None,
"key_pressed": False,
"tileset_group": Tileset_Group(tile_map),
"building_group": Building_Group(building_map_fromsheet),
"tileset_current": False,
"OverworldMenu": None,
"last_check_character_update": 0,
"last_check_clock_update": 0,
"hover_building": None,
"unique_character_int": 0,
"current_minute": 0,
"current_day": 1,
"number_tourists": 1,
"number_tourists_busy": 0,
"money": 5000,
"spookiness": 0,
"top_display_string": '$Day 001 00:00 Money $005000 Tourists: 0 Busy/1 Total Spookiness: 000',
"buildings_to_close_door": [],
"stats_dataframe": stats_dataframe,
"current_stats_displayed": None,
"current_stats": None
}

GAME_STATE["character_group"] =  Character_Group(character_map)

GAME_STATE["temp_character_group_dict"] = GAME_STATE["character_group"].tiles_dict.copy()
GAME_STATE["building_map_np"] = GAME_STATE["building_group"].tile_map.values
GAME_STATE["tiles_map_np"] = GAME_STATE["tileset_group"].tile_map.values

GAME_STATE["current_phase"] = titlescreen_phase

GAME_STATE["pressed_keys"] = {
    "up": False,
    "down": False,
    "left": False,
    "right": False,
    "action": False
}
GAME_STATE["prev_pressed_keys"] = GAME_STATE["pressed_keys"].copy()



FONT = pygame.font.SysFont("Arial", 30)  # You can change size or font

# Set up channels
music_channel = pygame.mixer.Channel(0)

music_folder_path = os.path.join(PATH_START, "Music")
overworld_music_path = os.path.join(music_folder_path, "Night.mp3")
overworld_music_sound = pygame.mixer.Sound(overworld_music_path)

output_path = os.path.join(PATH_START, "Debug")

menu_sfx_channel = pygame.mixer.Channel(1)  # Find an available channel
walking_sfx_channel = pygame.mixer.Channel(2)

music_channel.play(overworld_music_sound, loops=-1)

async def main():
    global GAME_STATE
    last_frame_time = time.time()
    screen.set_alpha(None)
    while GAME_STATE["running"]:
        frame_start = time.time()
        # Detect frame freezes
        GAME_STATE["delta_time"] = frame_start - last_frame_time
        
        last_frame_time = frame_start
        event_start = time.time()
        get_inputs()
        update_input_edges()
        event_time = time.time() - event_start

        update_start = time.time()
            
        update_time = time.time() - update_start

        # Get the set of keys pressed and check for user input

        GAME_STATE["current_phase"]()

        update_character_positions()
        spawn_new_tourists()
        replace_character_dict()
        update_in_game_time()
        update_top_display()
        close_building_doors()
        
        # Clear the screen
        render_start = time.time()
        for entity in GAME_STATE["overworld_sprites"]:
            screen.blit(entity.surf, entity.rect)

            #screen.blit(pygame.transform.scale(entity.surf, (SCREEN_WIDTH * entity.rect.width, SCREEN_HEIGHT * entity.rect.height)), (0, 0))
        render_time = time.time() - render_start

        
        fps = GAME_STATE["clock"].get_fps()
        # Render FPS text
        fps_text = FONT.render(f"FPS: {int(fps)} TARGET FPS: {int(TARGET_FPS)}", True, (255, 255, 255))  # White color
        screen.blit(fps_text, (470 * scale_factor, 340 * scale_factor))  # Top-left corner (adjust as needed)
        pygame.display.flip()
        #print(f"FPS: {fps}")
        #get_memory_usage()
        frame_time = time.time() - frame_start
        #print(f"Event: {event_time:.4f}s | Update: {update_time:.4f}s | Render: {render_time:.4f}s | Total Frame: {frame_time:.4f}s")
        GAME_STATE["clock"].tick(TARGET_FPS)
        await asyncio.sleep(0)  # Very important, and keep it 0
    pygame.quit()
    sys.exit()


asyncio.run(main())

#Current changes in direction:
#Revenue will be earned when a tourist leaves a building as this will be more exciting for the player
#Villager system is on the back burner-we'll assume everyone is a tourist and if we're able to implement villagers later we will
#Likewise, buildings won't have daily costs yet though I'll include them in the stat sheet for if we implement them
#Skilled villager system and resident happiness similarly not yet in use
#Tourists will spawn every 12 seconds minus 1/10 second per spooky score


#Current major issues: 
#If tourists spawn on same spot, multiple tourists can enter a building simultaneously
#If tourists enter a building while looking at it for removal, the info box does not update accordingly


#Currently needs improved:
#Fade in/out for placing buildings is tied to the framerate
#Walk sound effects are very quiet
#Add ability to go back to previous menu when placing a building
#Map should be bigger

#Current next steps:
#Make spooky stat affect tourist spawning rate and fix ability for tourists to spawn on same spot if paths are blocked/no stores are open. Have tourists have random list of destinations that always end with exit.

#Add night/day cycle
#-Adjust lighting for all sprites besides certain buildings/objects
#-Adjust tourist frquency/goals
#-Change music and visuals for each "phase"
#-Set songs to play for just their duration (3 minutes)
#-Change second length to be dependant on amount of song played

#Add stats to split villagers/tourists

#Add logic for the player earning money
#Make buildings earn money
#Make buildings cost money
#Add ability to view building stats

#Add remaining menu sound effects
#-Exit Menu (Damage 02) - Needs logic for going back to previous menu
#-Error sound (cannot place building/remove building) - ?
#Add character entering a building sound effect
#Add general building sound effects

#Add logic for saving
#--Pressing start or enter goes into the pause menu
#--Pause Menu options are Save and Nothing
#--Save dataframes to files
#--Files should be able to be accessed later, even in exe build
#Allow for slower/faster movement based on stick direction
#Add logic for using a config file
#Add support for additonal controllers

#Add QOL improvements for a building being constructed:
#--Dust animation-make placeholder with multiple frames-should completely cover where building will be
#--Dust animation ends, building is there
#--Controller vibrates