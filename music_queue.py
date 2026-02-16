import random
from enum import Enum
from typing import List, Dict, Optional, Tuple

class LoopMode(Enum):
    """Enum for different loop modes"""
    OFF = 0
    SINGLE = 1
    ALL = 2

class MusicQueue:
    def __init__(self):
        self.songs: List[Dict] = []  # List of song dictionaries
        self.current_index: int = 0  # Current position in queue (0-indexed)
        self.loop_mode: LoopMode = LoopMode.OFF
        self.original_order: List[Dict] = []  # Store original order for unshuffle
        self.is_shuffled: bool = False
        
    def add(self, song: Dict) -> None:
        """
        Add a single song to the queue
        
        Args:
            song: Song dictionary to add
        """
        self.songs.append(song)
        # If this is the first song added and we're not shuffled, update original order
        if not self.is_shuffled:
            self.original_order.append(song)
        
    def add_multiple(self, songs: List[Dict]) -> None:
        """
        Add multiple songs to the queue
        
        Args:
            songs: List of song dictionaries to add
        """
        self.songs.extend(songs)
        # If we're not shuffled, update original order
        if not self.is_shuffled:
            self.original_order.extend(songs)
        
    def remove(self, index: int) -> Optional[Dict]:
        """
        Remove song at specified index (0-indexed)
        
        Args:
            index: Position to remove (0-indexed)
            
        Returns:
            Removed song or None if index invalid
        """
        if 0 <= index < len(self.songs):
            removed_song = self.songs.pop(index)
            
            # Also remove from original order if not shuffled
            if not self.is_shuffled and index < len(self.original_order):
                self.original_order.pop(index)
            
            # Adjust current index if needed
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index:
                # If removing current song, try to move to next
                if self.current_index >= len(self.songs):
                    self.current_index = max(0, len(self.songs) - 1)
            
            return removed_song
        return None
        
    def get_current(self) -> Optional[Dict]:
        """
        Get current song without advancing
        
        Returns:
            Current song or None if queue empty
        """
        if self.is_empty() or self.current_index >= len(self.songs):
            return None
        return self.songs[self.current_index]
        
    def next(self) -> Optional[Dict]:
        """
        Move to next song and return it
        
        Returns:
            Next song or None if no next song
        """
        if self.is_empty():
            return None
            
        if self.loop_mode == LoopMode.SINGLE:
            # Single loop - stay on current song
            return self.get_current()
        
        # Move to next position
        self.current_index += 1
        
        # Handle loop modes
        if self.current_index >= len(self.songs):
            if self.loop_mode == LoopMode.ALL:
                # Loop all - go back to start
                self.current_index = 0
            else:
                # No loop - we're at the end
                self.current_index = len(self.songs) - 1
                return None
        
        return self.get_current()
        
    def previous(self) -> Optional[Dict]:
        """
        Move to previous song and return it
        
        Returns:
            Previous song or None if no previous song
        """
        if self.is_empty():
            return None
            
        self.current_index -= 1
        
        # Handle wrap-around for loop all mode
        if self.current_index < 0:
            if self.loop_mode == LoopMode.ALL:
                self.current_index = len(self.songs) - 1
            else:
                self.current_index = 0
                return None
                
        return self.get_current()
        
    def shuffle(self) -> None:
        """
        Shuffle the queue, keeping current song in place
        Only shuffles songs after current position
        """
        if len(self.songs) < 2:
            return
            
        # Save current song
        current_song = self.get_current()
        
        # Store original order if this is the first shuffle
        if not self.is_shuffled:
            self.original_order = self.songs.copy()
            self.is_shuffled = True
        
        # Only shuffle songs after current position
        if self.current_index + 1 < len(self.songs):
            songs_after_current = self.songs[self.current_index + 1:]
            random.shuffle(songs_after_current)
            self.songs = self.songs[:self.current_index + 1] + songs_after_current
        
        # Verify current song is still in the same position
        if current_song and self.songs[self.current_index] != current_song:
            # Find current song and swap it back to current position
            for i in range(len(self.songs)):
                if self.songs[i] == current_song:
                    self.songs[self.current_index], self.songs[i] = self.songs[i], self.songs[self.current_index]
                    break
        
    def unshuffle(self) -> None:
        """
        Restore original queue order
        """
        if self.is_shuffled and self.original_order:
            current_song = self.get_current()
            
            # Restore original order
            self.songs = self.original_order.copy()
            self.is_shuffled = False
            
            # Find and set current index based on current song
            if current_song:
                for i, song in enumerate(self.songs):
                    if song == current_song:
                        self.current_index = i
                        break
        
    def clear(self) -> None:
        """Clear all songs from queue and reset state"""
        self.songs.clear()
        self.original_order.clear()
        self.current_index = 0
        self.loop_mode = LoopMode.OFF
        self.is_shuffled = False
        
    def is_empty(self) -> bool:
        """
        Check if queue is empty
        
        Returns:
            True if queue has no songs
        """
        return len(self.songs) == 0
        
    def has_next(self) -> bool:
        """
        Check if there's a next song available
        
        Returns:
            True if next song exists or loop is enabled
        """
        if self.is_empty():
            return False
            
        if self.loop_mode != LoopMode.OFF:
            return True
            
        return self.current_index < len(self.songs) - 1
        
    def toggle_loop(self) -> LoopMode:
        """
        Cycle through loop modes: OFF -> ALL -> SINGLE -> OFF
        
        Returns:
            New loop mode
        """
        if self.loop_mode == LoopMode.OFF:
            self.loop_mode = LoopMode.ALL
        elif self.loop_mode == LoopMode.ALL:
            self.loop_mode = LoopMode.SINGLE
        else:
            self.loop_mode = LoopMode.OFF
            
        return self.loop_mode
        
    def set_loop_mode(self, mode: LoopMode) -> None:
        """
        Set specific loop mode
        
        Args:
            mode: LoopMode to set
        """
        self.loop_mode = mode
        
    def get_all(self) -> List[Dict]:
        """
        Get copy of all songs in queue
        
        Returns:
            List of all songs
        """
        return self.songs.copy()
        
    def get_position(self) -> Tuple[int, int]:
        """
        Get current position information
        
        Returns:
            Tuple of (current_index, total_songs)
        """
        return (self.current_index, len(self.songs))
        
    def get_remaining(self) -> List[Dict]:
        """
        Get all songs after current position
        
        Returns:
            List of remaining songs
        """
        if self.is_empty() or self.current_index >= len(self.songs) - 1:
            return []
        return self.songs[self.current_index + 1:]
        
    def jump_to(self, position: int) -> Optional[Dict]:
        """
        Jump to specific position in queue (0-indexed)
        
        Args:
            position: Position to jump to
            
        Returns:
            Song at new position or None if invalid
        """
        if 0 <= position < len(self.songs):
            self.current_index = position
            return self.get_current()
        return None
        
    def get_loop_mode(self) -> LoopMode:
        """
        Get current loop mode
        
        Returns:
            Current LoopMode
        """
        return self.loop_mode
        
    def get_loop_mode_string(self) -> str:
        """
        Get human-readable loop mode string
        
        Returns:
            String representation of loop mode
        """
        if self.loop_mode == LoopMode.OFF:
            return "OFF"
        elif self.loop_mode == LoopMode.SINGLE:
            return "SINGLE"
        else:
            return "ALL"
            
    def is_shuffled_state(self) -> bool:
        """
        Check if queue is currently shuffled
        
        Returns:
            True if queue is shuffled
        """
        return self.is_shuffled
        
    def get_queue_info(self) -> Dict:
        """
        Get comprehensive queue information
        
        Returns:
            Dictionary with queue stats
        """
        return {
            'total_songs': len(self.songs),
            'current_position': self.current_index,
            'loop_mode': self.get_loop_mode_string(),
            'is_shuffled': self.is_shuffled,
            'has_next': self.has_next(),
            'current_song': self.get_current()
        }
        
    def remove_by_filter(self, filter_func) -> List[Dict]:
        """
        Remove songs that match filter function
        
        Args:
            filter_func: Function that takes a song and returns bool
            
        Returns:
            List of removed songs
        """
        removed_songs = []
        new_songs = []
        new_original = []
        
        current_song = self.get_current()
        
        # Filter songs
        for i, song in enumerate(self.songs):
            if filter_func(song):
                removed_songs.append(song)
            else:
                new_songs.append(song)
                
        # Filter original order if not shuffled
        if not self.is_shuffled:
            for song in self.original_order:
                if not filter_func(song):
                    new_original.append(song)
        
        self.songs = new_songs
        if not self.is_shuffled:
            self.original_order = new_original
            
        # Adjust current index
        if current_song and current_song in removed_songs:
            # Current song was removed, try to find new position
            if self.songs:
                self.current_index = 0
            else:
                self.current_index = 0
        else:
            # Recalculate current index
            if current_song and current_song in self.songs:
                self.current_index = self.songs.index(current_song)
            else:
                self.current_index = min(self.current_index, len(self.songs) - 1)
                if self.current_index < 0:
                    self.current_index = 0
                    
        return removed_songs

    @property
    def songs_count(self) -> int:
        """Get total number of songs in queue"""
        return len(self.songs)