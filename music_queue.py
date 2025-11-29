import random
from enum import Enum

class LoopMode(Enum):
    OFF = 0
    SINGLE = 1
    ALL = 2

class MusicQueue:
    def __init__(self):
        self.songs = []
        self.current_index = 0
        self.loop_mode = LoopMode.OFF
        self.original_songs = []
        self._is_shuffled = False
    
    @property
    def is_shuffled(self):
        return self._is_shuffled
    
    def add(self, song):
        self.songs.append(song)
        if not self._is_shuffled:
            self.original_songs.append(song)
    
    def add_multiple(self, songs):
        self.songs.extend(songs)
        if not self._is_shuffled:
            self.original_songs.extend(songs)
    
    def remove(self, index):
        if 0 <= index < len(self.songs):
            removed_song = self.songs.pop(index)
            
            if removed_song in self.original_songs:
                self.original_songs.remove(removed_song)
            
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index and self.current_index >= len(self.songs):
                self.current_index = max(0, len(self.songs) - 1)
            
            return removed_song
        return None
    
    def get_current(self):
        if 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None
    
    def next(self):
        if self.is_empty():
            return None
            
        if self.loop_mode == LoopMode.SINGLE:
            return self.get_current()
        
        self.current_index += 1
        
        if self.loop_mode == LoopMode.ALL and self.current_index >= len(self.songs):
            self.current_index = 0
        
        return self.get_current()
    
    def previous(self):
        if self.current_index > 0:
            self.current_index -= 1
        elif self.loop_mode == LoopMode.ALL:
            self.current_index = len(self.songs) - 1
        
        return self.get_current()
    
    def shuffle(self):
        if len(self.songs) <= 1:
            return
            
        if not self._is_shuffled:
            self.original_songs = self.songs.copy()
            self._is_shuffled = True
        
        if self.current_index < len(self.songs) - 1:
            remaining = self.songs[self.current_index + 1:]
            random.shuffle(remaining)
            self.songs = self.songs[:self.current_index + 1] + remaining
    
    def unshuffle(self):
        if self._is_shuffled and self.original_songs:
            current_song = self.get_current()
            self.songs = self.original_songs.copy()
            
            if current_song:
                try:
                    self.current_index = self.songs.index(current_song)
                except ValueError:
                    self.current_index = 0
            
            self._is_shuffled = False
            self.original_songs = []
    
    def clear(self):
        self.songs = []
        self.original_songs = []
        self.current_index = 0
        self._is_shuffled = False
        self.loop_mode = LoopMode.OFF
    
    def is_empty(self):
        return len(self.songs) == 0
    
    def has_next(self):
        if self.is_empty():
            return False
        
        if self.loop_mode == LoopMode.SINGLE:
            return True
        
        if self.loop_mode == LoopMode.ALL:
            return len(self.songs) > 0
        
        return self.current_index + 1 < len(self.songs)
    
    def set_loop_mode(self, mode):
        self.loop_mode = mode
    
    def get_loop_mode(self):
        return self.loop_mode
    
    def cycle_loop_mode(self):
        if self.loop_mode == LoopMode.OFF:
            self.loop_mode = LoopMode.ALL
        elif self.loop_mode == LoopMode.ALL:
            self.loop_mode = LoopMode.SINGLE
        else:
            self.loop_mode = LoopMode.OFF
        
        return self.loop_mode
    
    def get_all(self):
        return self.songs.copy()
    
    def get_position(self):
        return (self.current_index, len(self.songs))