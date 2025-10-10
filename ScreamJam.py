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

#gc.set_debug(gc.DEBUG_STATS)

print(pygame.version.ver)   # full version as string
print(pygame.version.vernum)  # tuple: (major, minor, patch)

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
TARGET_FPS = 60
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
    def __init__(self, image_key, subsurface_rect, start_pos, tile_number=None):
        super().__init__()
        self.full_image = IMAGES_DICT[image_key]
        if tile_number is not None:
            self.tile_number = tile_number

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

    def get_sprites_below_cursor(self):
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
        colliding.sort(key=lambda sa: (-sa[1], sa[0].rect.x, sa[0].rect.y))

        # For debugging: print every colliding tile and its overlap area
        #for s, area in colliding:
        #    print(f"Colliding tile: {s.tile_number} at {s.pos_x}, {s.pos_y} overlap={area}")

        return [s for s, area in colliding]

    def get_best_sprite_below_cursor(self):
        """Return the single sprite that the cursor overlaps the most,
        or None if none overlap."""
        colliding = self.get_sprites_below_cursor()
        return colliding[0] if colliding else None

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
        #print(f"new tile pos x: {int(new_tile.pos_x)} pos y: {int(new_tile.pos_y)}")
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
            tile_number = tile_number
        )
        self.df_pos = df_pos

class Generic_Building(Individual_Sprite):
    def __init__(self, top_left, building, df_pos=None):
        super().__init__(
            image_key=f"Buildings_{building}.png",
            subsurface_rect=None,
            start_pos=['tl', top_left]
        )
        self.df_pos = df_pos

class Overworld_Main_Text_box(Individual_Sprite):
    def __init__(self):
        super().__init__(
            image_key="UI_Textbox.png",
            subsurface_rect=(0,0,640,43),
            start_pos=['tl', (0, 317)]
        )

class Overworld_Wide_Option_Box(Individual_Sprite):
    def __init__(self, top_left):
        super().__init__(
            image_key="UI_WideOptionBox.png",
            subsurface_rect=(0,0,208,43),
            start_pos=['tl', top_left]
        )

class Character_Sprite(Individual_Sprite):
    def __init__(self, bottom_left, df_pos=None):
        super().__init__(
            image_key="Characters_Forward.png",
            subsurface_rect=(0,0,16,24),
            start_pos=['bl', bottom_left]
        )
        self.df_pos=df_pos

#---------SPRITE GROUPS
class Regular_Font_Line(pygame.sprite.Group):
    def __init__(self, input_string, text_type):
        super(Regular_Font_Line, self).__init__()
        self.text_type = text_type
        self.set_letters(input_string, self.text_type)
        self.reveal_speed = 40  # ms per letter (~25 letters/sec)
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
        if len(input_string) > 36: #Need to adjust for new resolution(s)
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
        # Starting positions NEED ADJUSTED
        starting_height_top = 324
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


class Tileset_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super().__init__()
        self.tiles_list = []

        tile_size = 16
        start_x, start_y = -96, -80

        for row_index, (_, row) in enumerate(tile_map.iterrows()):
            y = start_y + row_index * tile_size
            for col_index, column in enumerate(row):
                x = start_x + col_index * tile_size
                curr_tile = Tile(
                    (x, y),
                    column,
                    df_pos=(row_index, col_index)  # <--- pass DataFrame coordinates
                )
                self.tiles_list.append(curr_tile)
                self.add(curr_tile)
        self.moving = False
        
    def move(self, dx, dy, speed, dt):
        move_x = dx * speed * dt * scale_factor
        move_y = dy * speed * dt * scale_factor

        for tile_sprite in self.tiles_list:
            tile_sprite.pos_x += (move_x * 3)
            tile_sprite.pos_y += (move_y * 3)
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
            tile_below = GAME_STATE["cursor"].get_best_sprite_below_cursor()
            if tile_below.tile_number == 4: #This is a source of slow down and ideally we'd not move back
                self.move(-dx, -dy, speed=60, dt=GAME_STATE["delta_time"])
            else:
                GAME_STATE["building_group"].check_move()
                GAME_STATE["character_group"].check_move()
        else:
            self.moving = False

class Character_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super().__init__()
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
                        (x, y),
                        #column, This will be where we put in the type of character later
                        df_pos=(row_index, col_index)  # <--- pass DataFrame coordinates
                    )
                    self.tiles_dict[f"{row_index}_{col_index}"] = curr_character
                    self.add(curr_character)
        self.moving = False

    def move(self, dx, dy, speed, dt):
        move_x = dx * speed * dt * scale_factor
        move_y = dy * speed * dt * scale_factor

        for tile_sprite in self.tiles_dict.values():
            if isinstance(tile_sprite, Individual_Sprite):
                tile_sprite.pos_x += (move_x * 3)
                tile_sprite.pos_y += (move_y * 3)
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
            tile_below = GAME_STATE["cursor"].get_best_sprite_below_cursor()
            if tile_below.tile_number == 4:
                self.move(-dx, -dy, speed=60, dt=GAME_STATE["delta_time"])
        else:
            self.moving = False

class Building_Group(pygame.sprite.Group):
    def __init__(self, tile_map):
        super().__init__()
        #self.tiles_list = []
        self.tiles_dict = {}
        self.tile_map = tile_map

        tile_size = 16
        start_x, start_y = -96, -80

        for row_index, (_, row) in enumerate(tile_map.iterrows()):
            y = start_y + row_index * tile_size
            for col_index, column in enumerate(row):
                if column != 0:
                    x = start_x + col_index * tile_size
                    curr_building = Generic_Building(
                        (x, y),
                        column,
                        df_pos=(row_index, col_index)  # <--- pass DataFrame coordinates
                    )
                    #self.tiles_list.append(curr_building)
                    self.add(curr_building)
        self.moving = False

    def add_building(self, building):
        global GAME_STATE
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        print(f"{GAME_STATE["selectedtile"].pos_x}, {GAME_STATE["selectedtile"].pos_y}")
        curr_building = Generic_Building(
        (int(GAME_STATE["selectedtile"].pos_x/scale_factor), int(GAME_STATE["selectedtile"].pos_y/scale_factor)),
        building,
        df_pos=GAME_STATE["selectedtile"].tile.df_pos  # <--- pass DataFrame coordinates
        )
        #self.tiles_list.append(curr_building)
        
        print(f"In Game: {curr_building.surf.width}, {curr_building.surf.height}")
        real_width = int(curr_building.surf.width/scale_factor)
        real_height = int(curr_building.surf.height/scale_factor)
        print(f"Real: {real_width}, {real_height}")
        tiles_wide = math.ceil(real_width / 16)
        tiles_tall = math.ceil(real_height / 16)
        print(f"Dimensions: {tiles_wide}, {tiles_tall}")
        curr_row = 0
        while curr_row < tiles_tall:
            curr_column = 0
            while curr_column < tiles_wide:
                if str(self.tile_map.iat[r + curr_row, c + curr_column]) != "0":
                    print(f"Can't place due to {str(self.tile_map.iat[r + curr_row, c + curr_column])} at {(r + curr_row)}, {(c + curr_column)} ")
                    return False
                curr_column += 1
            curr_row += 1
        self.tiles_dict[f"{r}_{c}"] = curr_building
        self.tile_map.iat[r, c] = building
        curr_row = 0
        while curr_row < tiles_tall:
            curr_column = 0
            while curr_column < tiles_wide:
                if not (curr_row == 0 and curr_column == 0):
                    self.tile_map.iat[r + curr_row, c + curr_column] = building
                    self.tiles_dict[f"{r + curr_row}_{c + curr_column}"] = f"{r}_{c}"
                curr_column += 1
            curr_row += 1
        self.add(curr_building)
        GAME_STATE["overworld_sprites"].add(curr_building, layer=2)
        return True

    def remove_building(self):
        global GAME_STATE
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        self.tile_map.iat[r, c] = 0
        curr_building = self.tiles_dict[f"{r}_{c}"]
        if not isinstance(curr_building, Individual_Sprite):
            curr_building = self.tiles_dict[curr_building]
        self.remove(curr_building)
        curr_building.kill()
        del curr_building

        
    def move(self, dx, dy, speed, dt):
        move_x = dx * speed * dt * scale_factor
        move_y = dy * speed * dt * scale_factor

        for tile_sprite in self.tiles_dict.values():
            if isinstance(tile_sprite, Individual_Sprite):
                tile_sprite.pos_x += (move_x * 3)
                tile_sprite.pos_y += (move_y * 3)
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
            tile_below = GAME_STATE["cursor"].get_best_sprite_below_cursor()
            if tile_below.tile_number == 4:
                self.move(-dx, -dy, speed=60, dt=GAME_STATE["delta_time"])
        else:
            self.moving = False

class Overworld_Menu(pygame.sprite.Group):
    def __init__(self, input_string, text_type, options=None, use_buy_sound=False, money_box=False, store_box=False, quantity_box=False):
        super(Overworld_Menu, self).__init__()
        if options:
            self.option_box = Overworld_Option_Box(top_left=(0,(SCREEN_HEIGHT-86)), options=options, use_buy_sound=use_buy_sound)
            self.add(self.option_box)
            self.number_of_option_boxes = 1
            self.previous_option_boxes = []
        else:
            self.option_box = None
            self.number_of_option_boxes = 0
        self.main_text_box = Overworld_Main_Text_box()
        self.curr_text = Regular_Font_Line(input_string=input_string, text_type=text_type)
        self.add(self.main_text_box)
        self.add(self.curr_text)

    def update_curr_text(self):
        self.curr_text.update()

    def change_curr_text(self, input_string, text_type):
        for s in self.curr_text:
            s.kill()
            del s
        self.curr_text = Regular_Font_Line(input_string=input_string, text_type=text_type)
        self.add(self.curr_text)
        for sprite in self.curr_text:
            GAME_STATE["overworld_sprites"].add(sprite, layer=5)
    
    def update_option_box(self):
        self.option_box.update()

    def add_option_box(self, options):
        self.previous_option_boxes.append(self.option_box)
        self.option_box = Overworld_Option_Box(top_left=(208,(SCREEN_HEIGHT-86)), options=options)
        self.number_of_option_boxes += 1
        self.add(self.option_box)
        

    def remove_option_box(self):
        for s in self.option_box:
            s.kill()
            del s
        self.option_box = self.previous_option_boxes[-1]
        self.number_of_option_boxes -= 1


class Overworld_Option_Box(pygame.sprite.Group):
    def __init__(self, top_left, options, use_buy_sound=False, use_arrow=True):
        super(Overworld_Option_Box, self).__init__()
        menu_box_sprite = Overworld_Wide_Option_Box(top_left)
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
        GAME_STATE["overworld_sprites"].add(GAME_STATE["cursor"], layer=5)
        GAME_STATE["main_bottom_textbox"] = None

        GAME_STATE["selectedtile"] = SelectedTile()
        GAME_STATE["overworld_sprites"].add(GAME_STATE["selectedtile"], layer=4)
        print('Overworld Initialized')
        GAME_STATE["tileset_current"] = True


def get_inputs():
    if GAME_STATE["in_menu"] == True:
        GAME_STATE["pressed_keys"] = None
        for event in pygame.event.get():
            #print(event)
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

            elif event.type == pygame.WINDOWFOCUSLOST:
                print("Window lost focus! Pausing unnecessary updates.")
    else:
        # Reset keys at the start of each frame (so releases are handled)
        DEAD_ZONE = 0.3  # Change this value to tweak sensitivity

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                GAME_STATE["running"] = False
            elif event.type == pygame.WINDOWFOCUSLOST:
                print("Window lost focus! Pausing unnecessary updates.")

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


#---------GAME PHASES
def titlescreen_phase():
    global GAME_STATE
    if GAME_STATE["title_screen"] == None:
        GAME_STATE["title_screen"] = Title_Screen()
        GAME_STATE["overworld_sprites"].add(GAME_STATE["title_screen"], layer=9)
    elif GAME_STATE["just_pressed"] and GAME_STATE["just_pressed"]["action"]:
        print('got to here')
        kill_and_delete(GAME_STATE["title_screen"])
        GAME_STATE["current_phase"] = overworld_phase
        

def overworld_phase():
    global GAME_STATE
    if not GAME_STATE["tileset_current"]:
        initialize_overworld()
    if GAME_STATE["just_pressed"]["action"] and not GAME_STATE["just_pressed"]["back"]:
        GAME_STATE["current_phase"] = interact_with_tile_phase
    else:
        GAME_STATE["tileset_group"].check_move()
        #GAME_STATE["building_group"].check_move()
        tile_below = GAME_STATE["cursor"].get_best_sprite_below_cursor()
        #print(f"Best Colliding tile: {tile_below.tile_number} at {tile_below.pos_x}, {tile_below.pos_y}")
        #if tile_below != GAME_STATE["selectedtile"].tile:
        GAME_STATE["selectedtile"].update_tile(tile_below)

def interact_with_tile_phase():
    global GAME_STATE
    #GAME_STATE["OverworldMenu"] = Overworld_Menu('What would you like to do?', options=["Place Building", "Nothing"], text_type='not_arrow')
    if not GAME_STATE["OverworldMenu"]:
        r, c = GAME_STATE["selectedtile"].tile.df_pos
        print(f"value: {GAME_STATE["building_group"].tile_map.iat[r, c]}")
        if str(GAME_STATE["building_group"].tile_map.iat[r, c]) == "0":  # or whatever value you want
            GAME_STATE["OverworldMenu"] = Overworld_Menu('What would you like to do?', options=["Place Building", "Nothing"], text_type='not_arrow')
        else:
            GAME_STATE["OverworldMenu"] = Overworld_Menu('What would you like to do?', options=["Remove Building", "Nothing"], text_type='not_arrow')
        #GAME_STATE["main_bottom_textbox"] = Overworld_Main_Text_box()
        for sprite in GAME_STATE["OverworldMenu"]:
            GAME_STATE["overworld_sprites"].add(sprite, layer=5)
        #GAME_STATE["overworld_sprites"].add(GAME_STATE["OverworldMenu"], layer=5)
        #GAME_STATE["curr_bottom_text"] = Regular_Font_Line(input_string=f'What would you like to do?', text_type='not_arrow')
        #GAME_STATE["overworld_sprites"].add(GAME_STATE["curr_bottom_text"], layer=6)
    if GAME_STATE["OverworldMenu"].curr_text.all_letters_set == False:
        GAME_STATE["OverworldMenu"].update_curr_text()
    GAME_STATE["OverworldMenu"].update_option_box()
    if GAME_STATE["just_pressed"]["back"] or (GAME_STATE["OverworldMenu"].option_box.final_selection == 2 and GAME_STATE["OverworldMenu"].number_of_option_boxes == 1):
        print('ayy lmao')
        kill_menu_and_clear()
        GAME_STATE["current_phase"] = overworld_phase
    elif GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Place Building" and GAME_STATE["OverworldMenu"].number_of_option_boxes == 1:
        print('build options')
        GAME_STATE["OverworldMenu"].add_option_box(options=["Haunted Hotel", "Abnormal Apartment"])
        for sprite in GAME_STATE["OverworldMenu"].option_box:
            GAME_STATE["overworld_sprites"].add(sprite, layer=5)
    elif GAME_STATE["OverworldMenu"].option_box.final_selection_text == "Remove Building" and GAME_STATE["OverworldMenu"].number_of_option_boxes == 1:
        print('remove building')
        GAME_STATE["building_group"].remove_building()
        kill_menu_and_clear()
        GAME_STATE["current_phase"] = overworld_phase
    elif GAME_STATE["OverworldMenu"].option_box.final_selection == 1 and GAME_STATE["OverworldMenu"].number_of_option_boxes == 2:
        print('create building')
        check_building_added_successful = GAME_STATE["building_group"].add_building("Hotel")
        if check_building_added_successful:
            kill_menu_and_clear()
            GAME_STATE["current_phase"] = overworld_phase
        else: 
            GAME_STATE["OverworldMenu"].option_box.final_selection = None
            GAME_STATE["OverworldMenu"].change_curr_text('That building will not fit', text_type='not arrow')




#Initialize Global Variables

maps_path = os.path.join(PATH_START, "Maps")
backgroundtiles_path = os.path.join(maps_path, "BackgroundTiles.txt")
tile_map = pd.read_csv(backgroundtiles_path, sep='\t', header=None)
zero_map = tile_map * 0
character_map = tile_map * 0
character_map.iat[20, 26] = "test"

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
"building_group": Building_Group(zero_map),
"character_group": Character_Group(character_map),
"tileset_current": False,
"OverworldMenu": None
}

GAME_STATE["current_phase"] = titlescreen_phase

GAME_STATE["pressed_keys"] = {
    "up": False,
    "down": False,
    "left": False,
    "right": False,
    "action": False
}
GAME_STATE["prev_pressed_keys"] = GAME_STATE["pressed_keys"].copy()



FONT = pygame.font.SysFont("Arial", 50)  # You can change size or font

# Set up channels
music_channel = pygame.mixer.Channel(0)

music_folder_path = os.path.join(PATH_START, "Music")
overworld_music_path = os.path.join(music_folder_path, "Daytime Theme - Draft 2.wav")
overworld_music_sound = pygame.mixer.Sound(overworld_music_path)

sfx_channel = pygame.mixer.Channel(1)  # Find an available channel
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
        
        # Clear the screen
        render_start = time.time()
        #print('testing tilesets')
        for entity in GAME_STATE["overworld_sprites"]:
            screen.blit(entity.surf, entity.rect)
            #print(f'number of sprites is {i}')

            #screen.blit(pygame.transform.scale(entity.surf, (SCREEN_WIDTH * entity.rect.width, SCREEN_HEIGHT * entity.rect.height)), (0, 0))
        render_time = time.time() - render_start

        
        fps = GAME_STATE["clock"].get_fps()
        # Render FPS text
        fps_text = FONT.render(f"FPS: {int(fps)} TARGET FPS: {int(TARGET_FPS)}", True, (255, 255, 255))  # White color
        screen.blit(fps_text, (10, 10))  # Top-left corner (adjust as needed)
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

#Current next steps:

#Fix Place Building Bug
#--Buildings can't be placed where other buildings currently are. However, if a building is too big for its current space, it won't stop the overlap. This will cause issues when moving the camera

#Add logic for characters to walk around and to find their ways to buildings

#Add logic for not placing buildings where characters currently are

#Add logic for placing different types of buildings

#Add time of day logic

#Add logic for a building being constructed
#--Building goes on selected tile, anchored to top left
#--Dust animation-make placeholder with multiple frames-should completely cover where building will be
#--Dust animation ends, building is there
#--Building is placed in building list dataframe

#Add logic for saving
#--Pressing start or enter goes into the pause menu
#--Pause Menu options are Save and Nothing
#--Save dataframes to files
#--Files should be able to be accessed later, even in exe build

#Allow for slower/faster movement based on stick direction

#Add logic for using a config file

#Add additonal controllers