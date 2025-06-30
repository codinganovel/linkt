#!/usr/bin/env python3
"""
linkt - Terminal Bookmark Manager with Text Preview
Save links with automatic text extraction and search.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

# Handle platform-specific imports
try:
    import termios
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

# Optional dependencies with graceful fallback
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

# Check for external tools
HAS_LINKS = shutil.which('links') is not None
HAS_LYNX = shutil.which('lynx') is not None

# Configuration
LINKT_DIR = Path.home() / '.local' / 'bin'
BOOKMARKS_FILE = LINKT_DIR / '.linkt.json'
CACHE_DIR = LINKT_DIR / '.linkt_cache'

# Colors
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    GRAY = '\033[90m'
    
    # Background colors
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'

def colored(text: str, color: str = "", style: str = "") -> str:
    """Return colored text."""
    return f"{style}{color}{text}{Colors.RESET}"

class BookmarkManager:
    def __init__(self):
        self.bookmarks_file = BOOKMARKS_FILE
        self.cache_dir = CACHE_DIR
        self.ensure_directories()
        self.bookmarks = self.load_bookmarks()
    
    def ensure_directories(self):
        """Create necessary directories."""
        LINKT_DIR.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_bookmarks(self) -> Dict:
        """Load bookmarks from JSON file."""
        if not self.bookmarks_file.exists():
            return {"bookmarks": [], "next_id": 1}
        
        try:
            with open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure structure
                if "bookmarks" not in data:
                    data["bookmarks"] = []
                if "next_id" not in data:
                    data["next_id"] = 1
                return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(colored("⚠️  Warning: Corrupted bookmarks file, starting fresh", Colors.YELLOW))
            return {"bookmarks": [], "next_id": 1}
    
    def save_bookmarks(self):
        """Save bookmarks to JSON file."""
        try:
            with open(self.bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(colored(f"❌ Error saving bookmarks: {e}", Colors.RED))
    
    def fetch_page_text(self, url: str) -> Optional[str]:
        """Fetch and extract text content from URL using text browser rendering."""
        # Try Links first for best modern web rendering
        if HAS_LINKS:
            return self.fetch_with_links(url)
        
        # Fall back to Lynx for traditional text browser experience
        if HAS_LYNX:
            return self.fetch_with_lynx(url)
        
        # Fall back to fetching with requests and processing
        if not HAS_REQUESTS:
            return "⚠️  Install requests for web content: pip install requests\n⚠️  Or install links/lynx for best experience:\n   • Links: http://links.twibright.com\n   • Lynx: apt install lynx / brew install lynx"
        
        try:
            print(colored(f"🌐 Fetching content from {url}...", Colors.CYAN))
            
            # Set a reasonable timeout and user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; linkt bookmark manager)'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            
            if 'text/html' not in content_type:
                # Handle non-HTML content
                if 'application/json' in content_type:
                    return f"📄 JSON Content:\n\n{response.text[:2000]}..."
                elif 'text/' in content_type:
                    return f"📄 Text Content:\n\n{response.text[:2000]}..."
                else:
                    return f"📄 Binary content ({content_type})\nSize: {len(response.content)} bytes"
            
            # Extract text from HTML in priority order
            if HAS_HTML2TEXT:
                return self.extract_text_with_html2text(response.text)
            elif HAS_BEAUTIFULSOUP:
                return self.extract_text_with_bs4(response.text)
            else:
                return self.extract_text_simple(response.text)
                
        except requests.exceptions.RequestException as e:
            return f"❌ Failed to fetch: {e}"
        except Exception as e:
            return f"❌ Error processing content: {e}"
    
    def fetch_with_links(self, url: str) -> str:
        """Fetch content using Links browser for modern web rendering."""
        try:
            print(colored(f"🔗 Fetching with Links: {url}...", Colors.CYAN))
            
            # Run links with dump option for text output
            # Use -width 80 for consistent formatting
            result = subprocess.run(
                ['links', '-dump', '-width', '80', url],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and result.stdout.strip():
                content = result.stdout.strip()
                
                # Limit length for preview but preserve links formatting
                if len(content) > 4000:
                    content = content[:4000] + "\n\n... (truncated)"
                
                return f"🔗 Links Browser View:\n\n{content}"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return f"❌ Links failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return "⏰ Links timeout - page took too long to load"
        except FileNotFoundError:
            return "❌ Links not found (this shouldn't happen)"
        except Exception as e:
            return f"❌ Links error: {e}"
    
    def fetch_with_lynx(self, url: str) -> str:
        """Fetch content using Lynx browser for authentic text rendering."""
        try:
            print(colored(f"🦌 Fetching with Lynx: {url}...", Colors.CYAN))
            
            # Run lynx with dump option for text output
            result = subprocess.run(
                ['lynx', '-dump', '-nolist', '-nonumbers', url],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0:
                # Try with numbers for links (classic lynx style)
                result = subprocess.run(
                    ['lynx', '-dump', url],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
            
            if result.returncode == 0 and result.stdout.strip():
                content = result.stdout.strip()
                
                # Limit length for preview but preserve lynx formatting
                if len(content) > 4000:
                    content = content[:4000] + "\n\n... (truncated)"
                
                return f"🦌 Lynx Browser View:\n\n{content}"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return f"❌ Lynx failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return "⏰ Lynx timeout - page took too long to load"
        except FileNotFoundError:
            return "❌ Lynx not found (this shouldn't happen)"
        except Exception as e:
            return f"❌ Lynx error: {e}"
    
    def extract_text_with_html2text(self, html: str) -> str:
        """Extract text using html2text (Lynx-like formatting)."""
        try:
            h = html2text.HTML2Text()
            
            # Configure for Lynx-like output
            h.ignore_links = False  # Show links
            h.ignore_images = True
            h.ignore_emphasis = False
            h.body_width = 80  # Standard terminal width
            h.unicode_snob = True
            h.mark_code = True
            
            text = h.handle(html)
            
            # Clean up extra whitespace but preserve structure
            lines = text.split('\n')
            cleaned_lines = []
            empty_count = 0
            
            for line in lines:
                if line.strip():
                    cleaned_lines.append(line.rstrip())
                    empty_count = 0
                else:
                    empty_count += 1
                    if empty_count <= 2:  # Allow max 2 consecutive empty lines
                        cleaned_lines.append('')
            
            text = '\n'.join(cleaned_lines).strip()
            
            # Limit length
            if len(text) > 4000:
                text = text[:4000] + "\n\n... (truncated)"
            
            return f"📄 Text Browser View:\n\n{text}"
            
        except Exception as e:
            return f"❌ html2text error: {e}"
        """Extract clean text using BeautifulSoup."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Get title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "No Title"
            
            # Try to find main content areas first
            main_content = None
            for selector in ['main', 'article', '[role="main"]', '.content', '#content']:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            # Fall back to body if no main content found
            if not main_content:
                main_content = soup.find('body') or soup
            
            # Extract text
            text = main_content.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Limit length for preview
            if len(text) > 3000:
                text = text[:3000] + "\n\n... (truncated)"
            
            return f"📄 {title_text}\n\n{text}"
            
        except Exception as e:
            return f"❌ Error parsing HTML: {e}"
    
    def extract_text_simple(self, html: str) -> str:
        """Simple text extraction without BeautifulSoup."""
        # Remove script and style tags
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Limit length
        if len(text) > 3000:
            text = text[:3000] + "\n\n... (truncated)"
        
        return f"📄 Extracted Text:\n\n{text}"
    
    def get_cache_path(self, bookmark_id: int) -> Path:
        """Get cache file path for bookmark."""
        return self.cache_dir / f"{bookmark_id}.txt"
    
    def add_bookmark(self, url: str, description: str = "", tags: List[str] = None):
        """Add a new bookmark with text extraction."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Generate ID
        bookmark_id = self.bookmarks["next_id"]
        self.bookmarks["next_id"] += 1
        
        # Create bookmark entry
        bookmark = {
            "id": bookmark_id,
            "url": url,
            "description": description,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "domain": urlparse(url).netloc
        }
        
        # Fetch content
        content = self.fetch_page_text(url)
        if content:
            # Cache content
            cache_path = self.get_cache_path(bookmark_id)
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                bookmark["has_content"] = True
                
                # Show which method was used
                if HAS_LINKS:
                    print(colored("🔗 Content rendered with Links", Colors.GREEN))
                elif HAS_LYNX:
                    print(colored("🦌 Content rendered with Lynx", Colors.GREEN))
                elif HAS_HTML2TEXT:
                    print(colored("📄 Content converted with html2text", Colors.GREEN))
                else:
                    print(colored("📄 Content extracted", Colors.GREEN))
                    
            except OSError:
                bookmark["has_content"] = False
        else:
            bookmark["has_content"] = False
        
        self.bookmarks["bookmarks"].append(bookmark)
        self.save_bookmarks()
        
        print(colored(f"✅ Added bookmark #{bookmark_id}: {url}", Colors.GREEN))
        if description:
            print(colored(f"📝 Description: {description}", Colors.GRAY))
        if tags:
            print(colored(f"🏷️  Tags: {', '.join(tags)}", Colors.GRAY))
    
    def list_bookmarks(self, tag_filter: str = None):
        """List all bookmarks or filter by tag."""
        bookmarks = self.bookmarks["bookmarks"]
        
        if tag_filter:
            bookmarks = [b for b in bookmarks if tag_filter.lower() in [t.lower() for t in b.get("tags", [])]]
        
        if not bookmarks:
            if tag_filter:
                print(colored(f"📭 No bookmarks found with tag '{tag_filter}'", Colors.YELLOW))
            else:
                print(colored("📭 No bookmarks saved yet", Colors.YELLOW))
                print(colored("💡 Add one with: linkt add <url> [description]", Colors.CYAN))
            return
        
        print(colored(f"🔗 {len(bookmarks)} bookmark(s)", Colors.BLUE, Colors.BOLD))
        if tag_filter:
            print(colored(f"🏷️  Filtered by tag: {tag_filter}", Colors.CYAN))
        print()
        
        for bookmark in bookmarks:
            self.show_bookmark_summary(bookmark)
    
    def show_bookmark_summary(self, bookmark: Dict):
        """Show a summary of a bookmark."""
        bookmark_id = bookmark["id"]
        url = bookmark["url"]
        description = bookmark.get("description", "")
        tags = bookmark.get("tags", [])
        domain = bookmark.get("domain", "")
        has_content = bookmark.get("has_content", False)
        
        # Format created date
        try:
            created = datetime.fromisoformat(bookmark["created"])
            date_str = created.strftime("%Y-%m-%d")
        except:
            date_str = "unknown"
        
        content_indicator = "🔗" if has_content and HAS_LINKS else "🦌" if has_content and HAS_LYNX else "📄" if has_content else "📄?"
        
        print(colored(f"[{bookmark_id:3d}] {content_indicator} {url}", Colors.CYAN))
        if description:
            print(colored(f"      📝 {description}", Colors.WHITE))
        
        info_parts = []
        if domain:
            info_parts.append(f"🌐 {domain}")
        info_parts.append(f"📅 {date_str}")
        if tags:
            info_parts.append(f"🏷️  {', '.join(tags)}")
        
        if info_parts:
            print(colored(f"      {' • '.join(info_parts)}", Colors.GRAY))
        
        # Show content preview if available
        if has_content:
            self.show_content_preview(bookmark_id)
        
        print()
    
    def show_content_preview(self, bookmark_id: int, lines: int = 3):
        """Show preview of cached content."""
        cache_path = self.get_cache_path(bookmark_id)
        if not cache_path.exists():
            return
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Show first few lines
            content_lines = content.split('\n')[:lines]
            preview = '\n'.join(content_lines)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            
            for line in preview.split('\n'):
                if line.strip():
                    print(colored(f"      {line}", Colors.DIM))
        except OSError:
            pass
    
    def show_bookmark_content(self, bookmark_id: int):
        """Show full content of a bookmark."""
        bookmark = self.find_bookmark(bookmark_id)
        if not bookmark:
            print(colored(f"❌ Bookmark #{bookmark_id} not found", Colors.RED))
            return
        
        cache_path = self.get_cache_path(bookmark_id)
        if not cache_path.exists():
            print(colored(f"📄 No cached content for bookmark #{bookmark_id}", Colors.YELLOW))
            print(colored(f"🔗 URL: {bookmark['url']}", Colors.CYAN))
            return
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(colored("=" * 60, Colors.CYAN))
            print(colored(f"📄 Bookmark #{bookmark_id} Content", Colors.BLUE, Colors.BOLD))
            print(colored(f"🔗 {bookmark['url']}", Colors.CYAN))
            print(colored("=" * 60, Colors.CYAN))
            print()
            print(content)
            print()
            print(colored("=" * 60, Colors.CYAN))
            
        except OSError as e:
            print(colored(f"❌ Error reading content: {e}", Colors.RED))
    
    def search_bookmarks(self, query: str):
        """Search bookmarks by URL, description, tags, or content."""
        query_lower = query.lower()
        matches = []
        
        for bookmark in self.bookmarks["bookmarks"]:
            # Search in URL, description, and tags
            searchable = f"{bookmark['url']} {bookmark.get('description', '')} {' '.join(bookmark.get('tags', []))}"
            
            if query_lower in searchable.lower():
                matches.append((bookmark, "metadata"))
                continue
            
            # Search in cached content
            cache_path = self.get_cache_path(bookmark["id"])
            if cache_path.exists():
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if query_lower in content.lower():
                        matches.append((bookmark, "content"))
                except OSError:
                    pass
        
        if not matches:
            print(colored(f"🔍 No bookmarks found matching '{query}'", Colors.YELLOW))
            return
        
        print(colored(f"🔍 Found {len(matches)} bookmark(s) matching '{query}'", Colors.BLUE, Colors.BOLD))
        print()
        
        for bookmark, match_type in matches:
            match_indicator = "📝" if match_type == "metadata" else "📄"
            print(colored(f"{match_indicator} Found in {match_type}:", Colors.CYAN))
            self.show_bookmark_summary(bookmark)
    
    def find_bookmark(self, bookmark_id: int) -> Optional[Dict]:
        """Find bookmark by ID."""
        for bookmark in self.bookmarks["bookmarks"]:
            if bookmark["id"] == bookmark_id:
                return bookmark
        return None
    
    def remove_bookmark(self, bookmark_id: int):
        """Remove a bookmark and its cached content."""
        bookmark = self.find_bookmark(bookmark_id)
        if not bookmark:
            print(colored(f"❌ Bookmark #{bookmark_id} not found", Colors.RED))
            return
        
        # Remove from list
        self.bookmarks["bookmarks"] = [b for b in self.bookmarks["bookmarks"] if b["id"] != bookmark_id]
        
        # Remove cached content
        cache_path = self.get_cache_path(bookmark_id)
        if cache_path.exists():
            try:
                cache_path.unlink()
            except OSError:
                pass
        
        self.save_bookmarks()
        print(colored(f"🗑️  Removed bookmark #{bookmark_id}: {bookmark['url']}", Colors.GREEN))
    
    def copy_url(self, bookmark_id: int):
        """Copy bookmark URL to clipboard."""
        bookmark = self.find_bookmark(bookmark_id)
        if not bookmark:
            print(colored(f"❌ Bookmark #{bookmark_id} not found", Colors.RED))
            return
        
        if not HAS_CLIPBOARD:
            print(colored("⚠️  Install pyperclip for clipboard support: pip install pyperclip", Colors.YELLOW))
            print(colored(f"🔗 URL: {bookmark['url']}", Colors.CYAN))
            return
        
        try:
            pyperclip.copy(bookmark['url'])
            print(colored(f"📋 Copied to clipboard: {bookmark['url']}", Colors.GREEN))
        except Exception as e:
            print(colored(f"❌ Clipboard error: {e}", Colors.RED))
            print(colored(f"🔗 URL: {bookmark['url']}", Colors.CYAN))
    
    def run_tui(self):
        """Run the interactive TUI mode."""
        selected_index = 0
        search_mode = False
        search_query = ""
        
        print(colored("🚀 Starting linkt TUI mode...", Colors.BLUE, Colors.BOLD))
        time.sleep(1)
        
        while True:
            bookmarks = self.get_filtered_bookmarks(search_query if search_mode else "")
            
            # Handle selection bounds
            if selected_index >= len(bookmarks):
                selected_index = max(0, len(bookmarks) - 1)
            
            self.draw_tui(bookmarks, selected_index, search_mode, search_query)
            
            try:
                if HAS_TERMIOS:
                    key = self.get_key_termios()
                else:
                    key = self.get_key_fallback()
                
                # Handle search mode
                if search_mode:
                    if key == '\x1b':  # Escape
                        search_mode = False
                        search_query = ""
                        selected_index = 0
                    elif key == '\r':  # Enter
                        search_mode = False
                        selected_index = 0
                    elif key == '\x7f' or key == '\x08':  # Backspace
                        if search_query:
                            search_query = search_query[:-1]
                        else:
                            search_mode = False
                        selected_index = 0
                    elif key.isprintable():
                        search_query += key
                        selected_index = 0
                    continue
                
                # Navigation
                if key == 'j' or key == 'DOWN':
                    selected_index = min(len(bookmarks) - 1, selected_index + 1)
                elif key == 'k' or key == 'UP':
                    selected_index = max(0, selected_index - 1)
                elif key == 'g':
                    selected_index = 0
                elif key == 'G':
                    selected_index = max(0, len(bookmarks) - 1)
                
                # Actions
                elif key == '\r' and bookmarks:  # Enter - view content
                    self.show_bookmark_content_tui(bookmarks[selected_index]["id"])
                elif key == 'c' and bookmarks:  # Copy URL
                    self.copy_url(bookmarks[selected_index]["id"])
                    time.sleep(1)
                elif key == 'd' and bookmarks:  # Delete
                    self.delete_bookmark_tui(bookmarks[selected_index])
                elif key == 'a':  # Add bookmark
                    self.add_bookmark_tui()
                elif key == '/':  # Search
                    search_mode = True
                    search_query = ""
                elif key == 'r':  # Refresh/reload content
                    if bookmarks:
                        self.refresh_bookmark_content(bookmarks[selected_index]["id"])
                elif key == '?':  # Help
                    self.show_tui_help()
                elif key == 'q' or key == '\x03':  # Quit
                    break
                    
            except KeyboardInterrupt:
                break
        
        print(colored("\n👋 Goodbye!", Colors.CYAN))
    
    def get_filtered_bookmarks(self, query: str) -> List[Dict]:
        """Get bookmarks filtered by search query."""
        if not query:
            return self.bookmarks["bookmarks"]
        
        query_lower = query.lower()
        matches = []
        
        for bookmark in self.bookmarks["bookmarks"]:
            # Search in URL, description, and tags
            searchable = f"{bookmark['url']} {bookmark.get('description', '')} {' '.join(bookmark.get('tags', []))}"
            
            if query_lower in searchable.lower():
                matches.append(bookmark)
                continue
            
            # Search in cached content
            cache_path = self.get_cache_path(bookmark["id"])
            if cache_path.exists():
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if query_lower in content.lower():
                        matches.append(bookmark)
                except OSError:
                    pass
        
        return matches
    
    def get_key_termios(self) -> str:
        """Get a single keypress using termios."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            
            # Handle arrow keys
            if key == '\x1b':
                key += sys.stdin.read(2)
                if key == '\x1b[A':
                    return 'UP'
                elif key == '\x1b[B':
                    return 'DOWN'
                elif key == '\x1b[C':
                    return 'RIGHT'
                elif key == '\x1b[D':
                    return 'LEFT'
                else:
                    return '\x1b'  # Just escape
            
            return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    def get_key_fallback(self) -> str:
        """Fallback input method for systems without termios."""
        print(colored("Commands: j/k (up/down), Enter (view), c (copy), d (delete), a (add), / (search), q (quit)", Colors.GRAY))
        command = input(colored("> ", Colors.CYAN)).strip().lower()
        
        if command in ['j', 'down']:
            return 'j'
        elif command in ['k', 'up']:
            return 'k'
        elif command in ['enter', 'view', 'v']:
            return '\r'
        elif command in ['copy', 'c']:
            return 'c'
        elif command in ['delete', 'del', 'd']:
            return 'd'
        elif command in ['add', 'a']:
            return 'a'
        elif command in ['search', '/']:
            return '/'
        elif command in ['quit', 'q', 'exit']:
            return 'q'
        elif command in ['help', '?', 'h']:
            return '?'
        else:
            return command[0] if command else ''
    
    def draw_tui(self, bookmarks: List[Dict], selected_index: int, search_mode: bool, search_query: str):
        """Draw the TUI interface."""
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Header
        width = 80
        print(colored("╔" + "═" * (width - 2) + "╗", Colors.CYAN))
        title = "🔗 linkt - Bookmark Manager"
        padding = (width - len(title) - 2) // 2
        print(colored("║" + " " * padding + title + " " * (width - padding - len(title) - 2) + "║", Colors.BLUE, Colors.BOLD))
        print(colored("╠" + "═" * (width - 2) + "╣", Colors.CYAN))
        
        # Status line
        if search_mode:
            status = f"🔍 Search: {search_query}_"
        elif search_query:
            status = f"🔍 Filtered: {search_query} ({len(bookmarks)} results)"
        else:
            status = f"📚 {len(bookmarks)} bookmark(s)"
        
        # Rendering method indicator
        if HAS_LINKS:
            render_method = "🔗 Links"
        elif HAS_LYNX:
            render_method = "🦌 Lynx"
        elif HAS_HTML2TEXT:
            render_method = "📄 html2text"
        else:
            render_method = "🔧 Basic"
        
        status_line = f"{status} | {render_method}"
        print(colored("║ " + status_line + " " * (width - len(status_line) - 3) + "║", Colors.WHITE))
        print(colored("╠" + "═" * (width - 2) + "╣", Colors.CYAN))
        
        # Bookmarks list
        display_height = 12
        
        if not bookmarks:
            empty_msg = "No bookmarks found" if search_query else "No bookmarks yet"
            for i in range(display_height):
                if i == display_height // 2:
                    msg = f"📭 {empty_msg}"
                    padding = (width - len(msg) - 2) // 2
                    print(colored("║" + " " * padding + msg + " " * (width - padding - len(msg) - 2) + "║", Colors.YELLOW))
                else:
                    print(colored("║" + " " * (width - 2) + "║", Colors.CYAN))
        else:
            # Calculate scroll offset
            start_idx = max(0, min(selected_index - display_height // 2, len(bookmarks) - display_height))
            end_idx = min(start_idx + display_height, len(bookmarks))
            
            for i in range(display_height):
                if i < end_idx - start_idx:
                    bookmark_idx = start_idx + i
                    bookmark = bookmarks[bookmark_idx]
                    is_selected = bookmark_idx == selected_index
                    
                    # Format bookmark line
                    bookmark_id = bookmark["id"]
                    url = bookmark["url"]
                    description = bookmark.get("description", "")
                    has_content = bookmark.get("has_content", False)
                    
                    # Indicators
                    content_icon = "🔗" if has_content and HAS_LINKS else "🦌" if has_content and HAS_LYNX else "📄" if has_content else "📄?"
                    
                    # Truncate for display
                    max_url_len = 40
                    display_url = url if len(url) <= max_url_len else url[:max_url_len-3] + "..."
                    
                    line = f" {content_icon} [{bookmark_id:3d}] {display_url}"
                    if description:
                        remaining = width - len(line) - 4
                        if remaining > 10:
                            desc_part = description[:remaining-3] + "..." if len(description) > remaining else description
                            line += f" - {desc_part}"
                    
                    # Pad line
                    line = line[:width-4] + " " * max(0, width - len(line) - 4)
                    
                    if is_selected:
                        print(colored("║" + line + " ║", Colors.WHITE, Colors.BG_BLUE))
                    else:
                        print(colored("║ " + line[1:] + " ║", Colors.WHITE))
                else:
                    print(colored("║" + " " * (width - 2) + "║", Colors.CYAN))
        
        # Preview section
        print(colored("╠" + "═" * (width - 2) + "╣", Colors.CYAN))
        
        if bookmarks and 0 <= selected_index < len(bookmarks):
            bookmark = bookmarks[selected_index]
            
            # Show bookmark details
            tags = bookmark.get("tags", [])
            created = bookmark.get("created", "")
            try:
                created_date = datetime.fromisoformat(created).strftime("%Y-%m-%d") if created else "Unknown"
            except:
                created_date = "Unknown"
            
            details = f"📅 {created_date}"
            if tags:
                details += f" | 🏷️  {', '.join(tags)}"
            
            print(colored("║ " + details + " " * (width - len(details) - 3) + "║", Colors.GRAY))
            
            # Show content preview
            self.show_tui_preview(bookmark["id"], width - 4, 3)
        else:
            for i in range(4):
                print(colored("║" + " " * (width - 2) + "║", Colors.CYAN))
        
        # Footer
        print(colored("╠" + "═" * (width - 2) + "╣", Colors.CYAN))
        
        if search_mode:
            help_lines = ["Escape: exit search | Backspace: delete char | Enter: apply filter"]
        else:
            help_lines = [
                "j/k: navigate | Enter: view | a: add | r: refresh | d: delete",
                "c: copy | /: search | g/G: top/bottom | ?: help | q: quit"
            ]
        
        # Show help lines
        for i, help_text in enumerate(help_lines):
            if i < 2:  # Show max 2 lines
                if len(help_text) > width - 4:
                    # Truncate if still too long
                    help_text = help_text[:width-7] + "..."
                print(colored("║ " + help_text + " " * (width - len(help_text) - 3) + "║", Colors.GRAY))
        
        # Add empty line if only one help line
        if len(help_lines) == 1:
            print(colored("║" + " " * (width - 2) + "║", Colors.CYAN))
        
        print(colored("╚" + "═" * (width - 2) + "╝", Colors.CYAN))
    
    def show_tui_preview(self, bookmark_id: int, max_width: int, max_lines: int):
        """Show preview of bookmark content in TUI."""
        cache_path = self.get_cache_path(bookmark_id)
        if not cache_path.exists():
            for i in range(max_lines):
                content = "📭 No cached content available" if i == 1 else ""
                print(colored("║ " + content + " " * (max_width - len(content) - 1) + "║", Colors.GRAY))
            return
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clean and split content into lines
            lines = []
            for line in content.split('\n'):
                if line.strip():
                    # Wrap long lines
                    while len(line) > max_width - 2:
                        lines.append(line[:max_width-2])
                        line = line[max_width-2:]
                    if line:
                        lines.append(line)
                elif len(lines) > 0 and lines[-1]:  # Add empty line only after content
                    lines.append("")
            
            # Show first few lines
            for i in range(max_lines):
                if i < len(lines):
                    line_content = lines[i][:max_width-2]
                    print(colored("║ " + line_content + " " * (max_width - len(line_content) - 1) + "║", Colors.WHITE))
                else:
                    print(colored("║" + " " * max_width + "║", Colors.CYAN))
                    
        except OSError:
            for i in range(max_lines):
                content = "❌ Error reading content" if i == 1 else ""
                print(colored("║ " + content + " " * (max_width - len(content) - 1) + "║", Colors.RED))
    
    def show_bookmark_content_tui(self, bookmark_id: int):
        """Show full bookmark content in TUI mode."""
        bookmark = self.find_bookmark(bookmark_id)
        if not bookmark:
            return
        
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Show content
        print(colored("=" * 80, Colors.CYAN))
        print(colored(f"🔗 Bookmark #{bookmark_id}: {bookmark['url']}", Colors.BLUE, Colors.BOLD))
        print(colored("=" * 80, Colors.CYAN))
        print()
        
        cache_path = self.get_cache_path(bookmark_id)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                print(content)
            except OSError:
                print(colored("❌ Error reading cached content", Colors.RED))
        else:
            print(colored("📭 No cached content available", Colors.YELLOW))
        
        print()
        print(colored("=" * 80, Colors.CYAN))
        print(colored("Press any key to return...", Colors.GRAY))
        
        # Wait for keypress
        if HAS_TERMIOS:
            self.get_key_termios()
        else:
            input()
    
    def add_bookmark_tui(self):
        """Add bookmark in TUI mode."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(colored("╔═ Add New Bookmark ══════════════════════════════════════════╗", Colors.CYAN))
        print(colored("║                                                              ║", Colors.CYAN))
        print(colored("║ Enter bookmark details (Ctrl+C to cancel):                  ║", Colors.WHITE))
        print(colored("║                                                              ║", Colors.CYAN))
        print(colored("╚══════════════════════════════════════════════════════════════╝", Colors.CYAN))
        print()
        
        try:
            url = input(colored("🔗 URL: ", Colors.CYAN)).strip()
            if not url:
                return
            
            description = input(colored("📝 Description (optional): ", Colors.CYAN)).strip()
            tags_input = input(colored("🏷️  Tags (comma-separated, optional): ", Colors.CYAN)).strip()
            
            tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()] if tags_input else []
            
            print()
            print(colored("🌐 Adding bookmark and fetching content...", Colors.BLUE))
            
            self.add_bookmark(url, description, tags)
            
            time.sleep(2)  # Show success message
            
        except KeyboardInterrupt:
            print(colored("\n❌ Cancelled", Colors.YELLOW))
            time.sleep(1)
    
    def delete_bookmark_tui(self, bookmark: Dict):
        """Delete bookmark with confirmation in TUI mode."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(colored("╔═ Delete Bookmark ═══════════════════════════════════════════╗", Colors.RED))
        print(colored("║                                                              ║", Colors.RED))
        print(colored("║ Are you sure you want to delete this bookmark?              ║", Colors.WHITE))
        print(colored("║                                                              ║", Colors.RED))
        print(colored("╚══════════════════════════════════════════════════════════════╝", Colors.RED))
        print()
        
        print(colored(f"🔗 URL: {bookmark['url']}", Colors.CYAN))
        if bookmark.get('description'):
            print(colored(f"📝 Description: {bookmark['description']}", Colors.WHITE))
        print()
        
        print(colored("y = Yes, delete | Any other key = Cancel", Colors.GRAY))
        
        if HAS_TERMIOS:
            key = self.get_key_termios()
        else:
            key = input(colored("Delete? (y/N): ", Colors.YELLOW)).strip().lower()
        
        if key.lower() == 'y':
            self.remove_bookmark(bookmark['id'])
            time.sleep(1)
    
    def refresh_bookmark_content(self, bookmark_id: int):
        """Refresh cached content for a bookmark."""
        bookmark = self.find_bookmark(bookmark_id)
        if not bookmark:
            return
        
        print(colored(f"🔄 Refreshing content for bookmark #{bookmark_id}...", Colors.BLUE))
        
        # Fetch fresh content
        content = self.fetch_page_text(bookmark['url'])
        if content:
            cache_path = self.get_cache_path(bookmark_id)
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Update bookmark record
                for b in self.bookmarks["bookmarks"]:
                    if b["id"] == bookmark_id:
                        b["has_content"] = True
                        break
                
                self.save_bookmarks()
                print(colored("✅ Content refreshed!", Colors.GREEN))
            except OSError:
                print(colored("❌ Failed to save refreshed content", Colors.RED))
        else:
            print(colored("❌ Failed to refresh content", Colors.RED))
        
        time.sleep(1)
    
    def show_tui_help(self):
        """Show help in TUI mode."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(colored("╔═ linkt Help ════════════════════════════════════════════════╗", Colors.BLUE))
        print(colored("║                                                              ║", Colors.BLUE))
        print(colored("║ 🔗 Terminal Bookmark Manager with Lynx-style Rendering      ║", Colors.WHITE, Colors.BOLD))
        print(colored("║                                                              ║", Colors.BLUE))
        print(colored("╠══════════════════════════════════════════════════════════════╣", Colors.BLUE))
        print(colored("║                                                              ║", Colors.BLUE))
        print(colored("║ Navigation:                                                  ║", Colors.CYAN, Colors.BOLD))
        print(colored("║   j, ↓        Move down                                      ║", Colors.WHITE))
        print(colored("║   k, ↑        Move up                                        ║", Colors.WHITE))
        print(colored("║   g           Go to top                                      ║", Colors.WHITE))
        print(colored("║   G           Go to bottom                                   ║", Colors.WHITE))
        print(colored("║                                                              ║", Colors.BLUE))
        print(colored("║ Actions:                                                     ║", Colors.CYAN, Colors.BOLD))
        print(colored("║   Enter       View bookmark content                          ║", Colors.WHITE))
        print(colored("║   c           Copy URL to clipboard                          ║", Colors.WHITE))
        print(colored("║   d           Delete bookmark                                ║", Colors.WHITE))
        print(colored("║   a           Add new bookmark                               ║", Colors.WHITE))
        print(colored("║   r           Refresh content                                ║", Colors.WHITE))
        print(colored("║   /           Search bookmarks                               ║", Colors.WHITE))
        print(colored("║   q           Quit                                           ║", Colors.WHITE))
        print(colored("║                                                              ║", Colors.BLUE))
        print(colored("║ Features:                                                    ║", Colors.CYAN, Colors.BOLD))
        print(colored("║   🔗 Links browser rendering (best modern web experience)   ║", Colors.WHITE))
        print(colored("║   🦌 Lynx browser rendering (classic text browser)          ║", Colors.WHITE))
        print(colored("║   📄 Local content caching                                  ║", Colors.WHITE))
        print(colored("║   🔍 Full-text search                                       ║", Colors.WHITE))
        print(colored("║   🏷️  Tag organization                                       ║", Colors.WHITE))
        print(colored("║                                                              ║", Colors.BLUE))
        print(colored("╚══════════════════════════════════════════════════════════════╝", Colors.BLUE))
        print()
        print(colored("Press any key to return...", Colors.GRAY))
        
        # Wait for keypress
        if HAS_TERMIOS:
            self.get_key_termios()
        else:
            input()

def show_help():
    """Show help information."""
    print(colored("🔗 linkt - Terminal Bookmark Manager", Colors.BLUE, Colors.BOLD))
    print()
    print(colored("Usage:", Colors.CYAN, Colors.BOLD))
    print("  linkt                               # Interactive TUI mode (default)")
    print("  linkt add <url> [description] [--tags tag1,tag2]")
    print("  linkt list [--tag tag]")
    print("  linkt search <query>")
    print("  linkt show <id>")
    print("  linkt copy <id>")
    print("  linkt remove <id>")
    print("  linkt tui                           # Explicit TUI mode")
    print("  linkt status                        # Show dependency status")
    print()
    print(colored("Examples:", Colors.CYAN, Colors.BOLD))
    print("  linkt                              # Start interactive TUI")
    print("  linkt add https://python.org 'Python documentation'")
    print("  linkt add github.com/user/repo --tags python,github")
    print("  linkt list --tag python")
    print("  linkt search 'api documentation'")
    print("  linkt show 5")
    print("  linkt copy 3")
    print()
    print(colored("Features:", Colors.CYAN, Colors.BOLD))
    print("  🔗 Links browser rendering (best modern web experience)")
    print("  🦌 Lynx browser rendering (classic text browser)")
    print("  📄 Automatic text extraction from web pages")
    print("  🏷️  Tag-based organization")
    print("  🔍 Search in URLs, descriptions, tags, and content")
    print("  📋 Clipboard integration")
    print("  💾 Local caching of page content")
    print()
    print(colored("Dependencies:", Colors.CYAN, Colors.BOLD))
    print("  Recommended: links (from http://links.twibright.com)")
    print("  Alternative: lynx (classic text browser)")
    print("  Optional: pip install requests html2text pyperclip")
    print("  Core features work with minimal dependencies")

def check_dependencies():
    """Check and report dependency status."""
    # External tools
    tools = [
        ("links", HAS_LINKS, "Modern text browser with better rendering (recommended)"),
        ("lynx", HAS_LYNX, "Classic text browser (widely available)"),
    ]
    
    # Python packages
    packages = [
        ("requests", HAS_REQUESTS, "Web page fetching"),
        ("html2text", HAS_HTML2TEXT, "Lynx-like text conversion"),
        ("beautifulsoup4", HAS_BEAUTIFULSOUP, "HTML parsing fallback"),
        ("pyperclip", HAS_CLIPBOARD, "Clipboard support")
    ]
    
    print(colored("📦 External Tools:", Colors.BLUE, Colors.BOLD))
    for name, available, description in tools:
        status = "✅" if available else "❌"
        print(f"  {status} {name:<15} - {description}")
    
    print()
    print(colored("🐍 Python Packages:", Colors.BLUE, Colors.BOLD))
    for name, available, description in packages:
        status = "✅" if available else "❌"
        print(f"  {status} {name:<15} - {description}")
    
    # Installation suggestions
    missing_tools = [name for name, available, _ in tools if not available]
    missing_packages = [name for name, available, _ in packages if not available]
    
    if missing_tools or missing_packages:
        print()
        print(colored("💡 Installation suggestions:", Colors.CYAN, Colors.BOLD))
        
        if missing_tools:
            print(colored("External tools:", Colors.CYAN))
            if 'links' in missing_tools:
                print("  # Links (recommended):")
                print("  # Visit: http://links.twibright.com")
                print("  # macOS:")
                print("  brew install links")
                print("  # Ubuntu/Debian:")
                print("  sudo apt install links")
                print("  # Arch:")
                print("  sudo pacman -S links")
                print()
            if 'lynx' in missing_tools:
                print("  # Lynx (classic):")
                print("  # macOS:")
                print("  brew install lynx")
                print("  # Ubuntu/Debian:")
                print("  sudo apt install lynx")
                print("  # Arch:")
                print("  sudo pacman -S lynx")
            
        if missing_packages:
            print(colored("Python packages:", Colors.CYAN))
            print(f"  pip install {' '.join(missing_packages)}")
    
    # Show current rendering method
    print()
    print(colored("🔧 Current rendering method:", Colors.BLUE, Colors.BOLD))
    if HAS_LINKS:
        print("  🔗 Using Links (best modern web experience)")
    elif HAS_LYNX:
        print("  🦌 Using Lynx (classic text browser)")
    elif HAS_HTML2TEXT:
        print("  📄 Using html2text (good text-like formatting)")
    elif HAS_BEAUTIFULSOUP:
        print("  🔧 Using BeautifulSoup (basic text extraction)")
    else:
        print("  ⚠️  Using simple regex (limited functionality)")
    
    print()

def main():
    parser = argparse.ArgumentParser(
        description="linkt - Terminal Bookmark Manager with Text Preview",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  linkt add https://python.org 'Python docs' --tags python,docs
  linkt list --tag python
  linkt search 'python tutorial'
  linkt show 5
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a bookmark')
    add_parser.add_argument('url', help='URL to bookmark')
    add_parser.add_argument('description', nargs='?', default='', help='Optional description')
    add_parser.add_argument('--tags', help='Comma-separated tags')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List bookmarks')
    list_parser.add_argument('--tag', help='Filter by tag')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search bookmarks')
    search_parser.add_argument('query', help='Search query')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show bookmark content')
    show_parser.add_argument('id', type=int, help='Bookmark ID')
    
    # Copy command
    copy_parser = subparsers.add_parser('copy', help='Copy bookmark URL')
    copy_parser.add_argument('id', type=int, help='Bookmark ID')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove bookmark')
    remove_parser.add_argument('id', type=int, help='Bookmark ID')
    
    # Status command
    subparsers.add_parser('status', help='Show dependency status')
    
    # TUI command
    subparsers.add_parser('tui', help='Start interactive TUI mode')
    
    args = parser.parse_args()
    
    # Default to TUI mode if no command specified
    if not args.command:
        manager = BookmarkManager()
        manager.run_tui()
        return
    
    manager = BookmarkManager()
    
    if args.command == 'add':
        tags = []
        if args.tags:
            tags = [tag.strip() for tag in args.tags.split(',')]
        manager.add_bookmark(args.url, args.description, tags)
    
    elif args.command == 'list':
        manager.list_bookmarks(args.tag)
    
    elif args.command == 'search':
        manager.search_bookmarks(args.query)
    
    elif args.command == 'show':
        manager.show_bookmark_content(args.id)
    
    elif args.command == 'copy':
        manager.copy_url(args.id)
    
    elif args.command == 'remove':
        manager.remove_bookmark(args.id)
    
    elif args.command == 'status':
        check_dependencies()
    
    elif args.command == 'tui':
        manager.run_tui()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colored("\n👋 Goodbye!", Colors.CYAN))
    except Exception as e:
        print(colored(f"❌ Error: {e}", Colors.RED))
        sys.exit(1)