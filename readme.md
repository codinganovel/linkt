# linkt
**linkt** is a terminal bookmark manager with text browser rendering. It's a tool designed to save links with automatic content extraction using Links/Lynx browsers, providing offline text-based previews with full-text search and tag organization.
> No browser clutter. No online dependencies. Just save, cache, and browse.
---
## ✨ Features
- Links/Lynx browser rendering for authentic text-based content
- Automatic page content caching for offline browsing
- Interactive TUI mode with vim-style navigation
- Full-text search across URLs, descriptions, tags, and cached content
- Tag-based organization and filtering
- Clipboard integration for quick URL copying
- Local storage with instant content preview
- Command-line interface for scripting and automation
---
## 📦 Installation

[get yanked](https://github.com/codinganovel/yanked)

---
## 🚀 Usage
### Interactive TUI Mode (Default)
```bash
# Start interactive bookmark manager
linkt                          # TUI mode (default)
linkt tui                      # Explicit TUI mode
```
Navigate with vim-style keys:
- `j/k`: Navigate up/down
- `Enter`: View full cached content
- `a`: Add new bookmark
- `r`: Refresh/re-fetch content
- `d`: Delete bookmark
- `c`: Copy URL to clipboard
- `/`: Search bookmarks
- `g/G`: Jump to top/bottom
- `?`: Show help
- `q`: Quit

### Command Line Mode
```bash
# Add bookmarks
linkt add https://example.com "Example site" --tags web,demo
linkt add github.com/user/repo --tags coding,github

# List and search
linkt list                     # List all bookmarks
linkt list --tag python       # Filter by tag
linkt search "documentation"   # Search all content

# View and manage
linkt show 5                   # View cached content
linkt copy 3                   # Copy URL to clipboard
linkt remove 2                 # Delete bookmark
linkt status                   # Show dependency status
```

---
### Available Commands
| Command                           | Description                          |
|-----------------------------------|--------------------------------------|
| `linkt`                          | Interactive TUI mode (default)       |
| `linkt add <url> [desc] [--tags]` | Add bookmark with content caching   |
| `linkt list [--tag tag]`         | List bookmarks, optionally filtered |
| `linkt search <query>`           | Search URLs, descriptions, and content |
| `linkt show <id>`                | View full cached content            |
| `linkt copy <id>`                | Copy bookmark URL to clipboard     |
| `linkt remove <id>`              | Delete bookmark and cached content |
| `linkt tui`                      | Start interactive TUI mode          |
| `linkt status`                   | Show dependency and rendering status |

Content is automatically fetched and cached locally when bookmarks are added.
---
## 📋 Text Browser Support & Dependencies
`linkt` uses external text browsers for the best content rendering experience.

### Text Browsers (Recommended)
✅ **Links** - Modern text browser with excellent CSS/table support  
📦 **Installation:**
```bash
# macOS
brew install links
# Ubuntu/Debian  
sudo apt install links
# Arch
sudo pacman -S links
# Visit: http://links.twibright.com
```

✅ **Lynx** - Classic text browser (widely available fallback)
```bash
# macOS
brew install lynx
# Ubuntu/Debian
sudo apt install lynx  
# Arch
sudo pacman -S lynx
```

### Python Dependencies (Optional)
```bash
pip install requests html2text beautifulsoup4 pyperclip
```

**Rendering Priority:**
1. 🔗 **Links** - Best modern web experience
2. 🦌 **Lynx** - Classic text browser  
3. 📄 **html2text** - Python text conversion
4. 🔧 **BeautifulSoup** - Basic HTML parsing
5. ⚠️ **Simple regex** - Last resort

### Clipboard Support
- **macOS/Windows**: Works out of the box
- **Linux**: Requires `xclip` or `xsel`

---
## 💾 Local Storage
Bookmarks and cached content are stored locally:
- **Bookmarks database**: `~/.local/bin/.linkt.json`
- **Cached content**: `~/.local/bin/.linkt_cache/`

Content is cached when bookmarks are added and remains available offline. Use `r` (refresh) in TUI or re-add bookmarks to update cached content.

---
## 📄 License

under ☕️, check out [the-coffee-license](https://github.com/codinganovel/The-Coffee-License)

I've included both licenses with the repo, do what you know is right. The licensing works by assuming your operating under good faith.
---
## ✍️ Created by Sam  
Because bookmarks should show you what's actually on the page.
