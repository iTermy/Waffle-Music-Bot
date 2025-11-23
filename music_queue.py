import random

class MusicQueue:
    """Manages the music queue"""
    
    def __init__(self):
        self.songs = []
        self.current_index = 0
        self.loop_enabled = False
    
    def add(self, song):
        """
        Add a song to the queue
        
        Args:
            song: Dict with song info
        """
        self.songs.append(song)
    
    def add_multiple(self, songs):
        """
        Add multiple songs to queue
        
        Args:
            songs: List of song dicts
        """
        self.songs.extend(songs)
    
    def remove(self, index):
        """
        Remove song at index (0-based)
        
        Args:
            index: Position in queue (0-based)
        
        Returns:
            Removed song dict or None
        """
        if 0 <= index < len(self.songs):
            return self.songs.pop(index)
        return None
    
    def get_current(self):
        """
        Get current song without moving forward
        
        Returns:
            Current song dict or None
        """
        if 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None
    
    def next(self):
        """
        Move to next song
        
        Returns:
            Next song dict or None
        """
        self.current_index += 1
        
        # Handle loop
        if self.loop_enabled and self.current_index >= len(self.songs):
            self.current_index = 0
        
        return self.get_current()
    
    def previous(self):
        """
        Move to previous song
        
        Returns:
            Previous song dict or None
        """
        if self.current_index > 0:
            self.current_index -= 1
        return self.get_current()
    
    def shuffle(self):
        """Shuffle all songs after current one"""
        if self.current_index < len(self.songs) - 1:
            # Get songs after current
            remaining = self.songs[self.current_index + 1:]
            random.shuffle(remaining)
            
            # Rebuild queue
            self.songs = self.songs[:self.current_index + 1] + remaining
    
    def clear(self):
        """Clear entire queue"""
        self.songs = []
        self.current_index = 0
    
    def is_empty(self):
        """Check if queue has any songs"""
        return len(self.songs) == 0
    
    def has_next(self):
        """Check if there's a next song"""
        if self.loop_enabled:
            return not self.is_empty()
        return self.current_index + 1 < len(self.songs)
    
    def toggle_loop(self):
        """
        Toggle loop mode
        
        Returns:
            New loop state (bool)
        """
        self.loop_enabled = not self.loop_enabled
        return self.loop_enabled
    
    def get_all(self):
        """
        Get all songs in queue
        
        Returns:
            List of all songs
        """
        return self.songs.copy()
    
    def get_position(self):
        """
        Get current position in queue
        
        Returns:
            Tuple of (current_index, total_songs)
        """
        return (self.current_index, len(self.songs))