import yt_dlp
import os
from dotenv import load_dotenv

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

load_dotenv()

class MusicHandler:
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        spotify_id = os.getenv('SPOTIFY_CLIENT_ID')
        spotify_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        
        if not SPOTIPY_AVAILABLE:
            self.spotify = None
            print("⚠️  spotipy not installed - Spotify support disabled")
        elif spotify_id and spotify_secret:
            auth_manager = SpotifyClientCredentials(
                client_id=spotify_id,
                client_secret=spotify_secret
            )
            self.spotify = spotipy.Spotify(auth_manager=auth_manager)
        else:
            self.spotify = None
            print("⚠️  Spotify credentials not found - Spotify support disabled")
    
    def get_youtube_info(self, url):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:
                    info = info['entries'][0]
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'url': info['url'],
                    'duration': info.get('duration', 0),
                    'source': 'youtube',
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url', url)
                }
        except Exception as e:
            print(f"❌ Error getting YouTube info: {e}")
            return None
    
    def get_spotify_info(self, url):
        if not self.spotify:
            raise Exception("Spotify credentials not configured")
        
        try:
            track_id = url.split('/')[-1].split('?')[0]
            track = self.spotify.track(track_id)
            
            return {
                'title': track['name'],
                'artist': track['artists'][0]['name'],
                'duration': track['duration_ms'] // 1000,
                'album': track['album']['name'],
                'thumbnail': track['album']['images'][0]['url'] if track['album']['images'] else None
            }
        except Exception as e:
            print(f"❌ Error getting Spotify info: {e}")
            return None
    
    def spotify_to_youtube(self, spotify_info):
        query = f"{spotify_info['artist']} - {spotify_info['title']} audio"
        search_url = f"ytsearch:{query}"
        youtube_info = self.get_youtube_info(search_url)
        
        if youtube_info:
            youtube_info['original_title'] = f"{spotify_info['artist']} - {spotify_info['title']}"
            youtube_info['source'] = 'spotify'
        
        return youtube_info
    
    def get_song(self, url):
        if 'spotify.com' in url:
            spotify_info = self.get_spotify_info(url)
            if not spotify_info:
                return None
            return self.spotify_to_youtube(spotify_info)
        else:
            return self.get_youtube_info(url)
    
    def get_playlist(self, url):
        if 'spotify.com' in url and 'playlist' in url:
            return self._get_spotify_playlist(url)
        elif 'youtube.com' in url or 'youtu.be' in url:
            return self._get_youtube_playlist(url)
        else:
            return []
    
    def _get_youtube_playlist(self, url):
        try:
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['extract_flat'] = 'in_playlist'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' not in info:
                    return []
                
                songs = []
                for entry in info['entries']:
                    if entry:
                        song_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        song_info = self.get_youtube_info(song_url)
                        if song_info:
                            songs.append(song_info)
                
                return songs
        except Exception as e:
            print(f"❌ Error getting YouTube playlist: {e}")
            return []
    
    def _get_spotify_playlist(self, url):
        if not self.spotify:
            raise Exception("Spotify credentials not configured")
        
        try:
            playlist_id = url.split('/')[-1].split('?')[0]
            results = self.spotify.playlist_tracks(playlist_id)
            tracks = results['items']
            
            while results['next']:
                results = self.spotify.next(results)
                tracks.extend(results['items'])
            
            songs = []
            for item in tracks:
                if item['track']:
                    track = item['track']
                    spotify_info = {
                        'title': track['name'],
                        'artist': track['artists'][0]['name'],
                        'duration': track['duration_ms'] // 1000
                    }
                    
                    youtube_info = self.spotify_to_youtube(spotify_info)
                    if youtube_info:
                        songs.append(youtube_info)
            
            return songs
        except Exception as e:
            print(f"❌ Error getting Spotify playlist: {e}")
            return []