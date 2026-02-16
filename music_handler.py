import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv
import re
import asyncio
import concurrent.futures

# Load environment variables
load_dotenv()

class MusicHandler:
    def __init__(self):
        # YouTube DL configuration - optimized for large playlists
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Extract minimal info first for playlists
            'noplaylist': False,
            'ignoreerrors': True,  # Skip unavailable videos in playlists
            'extractaudio': True,
            'audioformat': 'mp3',
            'default_search': 'ytsearch',
            'playlistend': 500,  # Limit large playlists to 500 songs
        }
        
        # Thread pool for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        
        # Initialize Spotify client if credentials are available
        self.spotify_client = None
        self._init_spotify()
        
    def _init_spotify(self):
        """Initialize Spotify client if credentials are available"""
        try:
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            if client_id and client_secret:
                auth_manager = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret
                )
                self.spotify_client = spotipy.Spotify(auth_manager=auth_manager)
                print("✅ Spotify client initialized successfully")
            else:
                print("⚠️ Spotify credentials not found. Spotify features disabled.")
        except Exception as e:
            print(f"⚠️ Failed to initialize Spotify client: {e}")
            self.spotify_client = None

    def get_song(self, query: str) -> dict | None:
        """
        Get song information from YouTube or Spotify
        """
        try:
            # Check if it's a Spotify URL
            if self._is_spotify_url(query) and self.spotify_client:
                return self._get_spotify_track(query)
            
            # Otherwise, treat as YouTube or search query
            return self._get_youtube_info(query)
            
        except Exception as e:
            print(f"Error getting song: {e}")
            return None

    def get_playlist(self, url: str) -> list[dict]:
        """
        Get all songs from a playlist URL - optimized for large playlists
        """
        try:
            # Check if it's a Spotify playlist
            if self._is_spotify_playlist(url) and self.spotify_client:
                return self._get_spotify_playlist(url)
            
            # Otherwise, treat as YouTube playlist
            return self._get_youtube_playlist_optimized(url)
            
        except Exception as e:
            print(f"Error getting playlist: {e}")
            return []

    def _get_youtube_info(self, query: str) -> dict | None:
        """
        Extract YouTube video information
        """
        try:
            # Use different options for single songs vs playlists
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['extract_flat'] = False  # Get full info for single songs
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                
                # Handle search results - take first result
                if 'entries' in info:
                    if info['entries']:
                        info = info['entries'][0]
                    else:
                        return None
                
                return self._format_youtube_song(info)
                
        except Exception as e:
            print(f"YouTube extraction error: {e}")
            return None

    def _get_youtube_playlist_optimized(self, url: str) -> list[dict]:
        """
        Optimized method for large YouTube playlists
        """
        songs = []
        failed_count = 0
        
        try:
            print(f"Starting playlist extraction: {url}")
            
            # First, extract playlist info with flat extraction
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False)
                
                if not playlist_info or 'entries' not in playlist_info:
                    print("No playlist entries found")
                    return []
                
                total_entries = len(playlist_info['entries'])
                print(f"Found {total_entries} entries in playlist")
                
                # Process entries in batches to avoid memory issues
                batch_size = 50
                for batch_start in range(0, total_entries, batch_size):
                    batch_end = min(batch_start + batch_size, total_entries)
                    batch_entries = playlist_info['entries'][batch_start:batch_end]
                    
                    print(f"Processing batch {batch_start//batch_size + 1}: entries {batch_start} to {batch_end-1}")
                    
                    for i, entry in enumerate(batch_entries):
                        if entry is None:
                            failed_count += 1
                            continue
                            
                        try:
                            # For large playlists, use the flat info if available
                            if entry.get('url') or entry.get('webpage_url'):
                                song_info = self._format_flat_song(entry)
                                if song_info:
                                    songs.append(song_info)
                                else:
                                    failed_count += 1
                            else:
                                # Fallback to individual extraction
                                song_url = f"https://www.youtube.com/watch?v={entry['id']}"
                                song_info = self._get_youtube_info(song_url)
                                
                                if song_info:
                                    songs.append(song_info)
                                else:
                                    failed_count += 1
                                    
                        except Exception as e:
                            print(f"Failed to process song {batch_start + i}: {e}")
                            failed_count += 1
                
                print(f"✅ YouTube playlist: {len(songs)} songs loaded, {failed_count} failed")
                return songs
                
        except Exception as e:
            print(f"YouTube playlist extraction error: {e}")
            return []

    def _format_flat_song(self, entry: dict) -> dict | None:
        """
        Format song from flat playlist extraction (faster for large playlists)
        """
        try:
            title = entry.get('title', 'Unknown Title')
            if title == 'Unknown Title' and entry.get('id'):
                # Try to get better title
                title = f"Video {entry['id']}"
                
            duration = entry.get('duration', 0)
            if not duration:
                duration = entry.get('approx_duration', 0)
                
            webpage_url = entry.get('webpage_url')
            if not webpage_url and entry.get('id'):
                webpage_url = f"https://www.youtube.com/watch?v={entry['id']}"
                
            return {
                'title': title,
                'url': None,  # Will be populated when played
                'duration': int(duration) if duration else 0,
                'source': 'youtube',
                'thumbnail': entry.get('thumbnail'),
                'webpage_url': webpage_url,
                'id': entry.get('id')
            }
        except Exception as e:
            print(f"Error formatting flat song: {e}")
            return None

    # ... (keep the rest of the spotify methods the same as before)

    def _get_spotify_track(self, url: str) -> dict | None:
        """Extract Spotify track information and convert to YouTube"""
        try:
            track_id = self._extract_spotify_id(url)
            if not track_id:
                return None
            
            track_info = self.spotify_client.track(track_id)
            if not track_info:
                return None
            
            artists = ', '.join([artist['name'] for artist in track_info['artists']])
            search_query = f"{artists} - {track_info['name']}"
            
            youtube_song = self._get_youtube_info(search_query)
            if youtube_song:
                youtube_song['original_title'] = f"{artists} - {track_info['name']}"
                youtube_song['spotify_url'] = url
                return youtube_song
                
            return None
            
        except Exception as e:
            print(f"Spotify track extraction error: {e}")
            return None

    def _get_spotify_playlist(self, url: str) -> list[dict]:
        """Extract all songs from Spotify playlist and convert to YouTube"""
        songs = []
        failed_count = 0
        
        try:
            playlist_id = self._extract_spotify_id(url)
            if not playlist_id:
                return []
            
            playlist_info = self.spotify_client.playlist_tracks(playlist_id)
            if not playlist_info:
                return []
            
            # Process tracks in batches
            batch_size = 50
            all_tracks = []
            
            # Collect all tracks first
            while playlist_info:
                all_tracks.extend(playlist_info['items'])
                if playlist_info['next']:
                    playlist_info = self.spotify_client.next(playlist_info)
                else:
                    break
            
            print(f"Processing {len(all_tracks)} Spotify tracks...")
            
            # Process in batches
            for batch_start in range(0, len(all_tracks), batch_size):
                batch_end = min(batch_start + batch_size, len(all_tracks))
                batch = all_tracks[batch_start:batch_end]
                
                for item in batch:
                    if not item or not item['track']:
                        failed_count += 1
                        continue
                        
                    try:
                        track = item['track']
                        artists = ', '.join([artist['name'] for artist in track['artists']])
                        search_query = f"{artists} - {track['name']}"
                        
                        youtube_song = self._get_youtube_info(search_query)
                        if youtube_song:
                            youtube_song['original_title'] = f"{artists} - {track['name']}"
                            youtube_song['spotify_url'] = track['external_urls']['spotify']
                            songs.append(youtube_song)
                        else:
                            failed_count += 1
                            
                    except Exception as e:
                        print(f"Failed to convert Spotify track: {e}")
                        failed_count += 1
            
            print(f"✅ Spotify playlist: {len(songs)} songs loaded, {failed_count} failed")
            return songs
            
        except Exception as e:
            print(f"Spotify playlist extraction error: {e}")
            return []

    def _format_youtube_song(self, info: dict) -> dict:
        """Format YouTube extraction info into standard song dictionary"""
        url = None
        if 'url' in info:
            url = info['url']
        elif 'formats' in info:
            for format in info['formats']:
                if format.get('acodec') != 'none' and format.get('vcodec') == 'none':
                    url = format['url']
                    break
        
        if not url and 'formats' in info and info['formats']:
            url = info['formats'][0]['url']
        
        duration = info.get('duration', 0)
        if not duration and 'approx_duration' in info:
            try:
                parts = info['approx_duration'].split(':')
                if len(parts) == 2:
                    duration = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except:
                duration = 0
        
        return {
            'title': info.get('title', 'Unknown Title'),
            'url': url,
            'duration': int(duration) if duration else 0,
            'source': 'youtube',
            'thumbnail': info.get('thumbnail'),
            'webpage_url': info.get('webpage_url', info.get('original_url')),
        }

    def _is_spotify_url(self, url: str) -> bool:
        return bool(re.match(r'https?://open\.spotify\.com/track/[\w]+', url))

    def _is_spotify_playlist(self, url: str) -> bool:
        return bool(re.match(r'https?://open\.spotify\.com/playlist/[\w]+', url))

    def _extract_spotify_id(self, url: str) -> str | None:
        match = re.search(r'spotify\.com/(?:track|playlist)/([\w]+)', url)
        return match.group(1) if match else None

    def search_song(self, query: str) -> dict | None:
        return self._get_youtube_info(query)

    def refresh_url(self, song: dict) -> dict | None:
        if not song.get('webpage_url'):
            return None
            
        try:
            refreshed_song = self.get_song(song['webpage_url'])
            if refreshed_song:
                refreshed_song['original_title'] = song.get('original_title')
                refreshed_song['spotify_url'] = song.get('spotify_url')
                return refreshed_song
        except Exception as e:
            print(f"Error refreshing URL: {e}")
            
        return None