# 🎬 Telegram Video Downloader Bot

A powerful Telegram bot that downloads videos from popular social media platforms with enhanced private video support and advanced queue management.

## ✨ Features

- 🌐 **Multi-Platform Support**: TikTok, Instagram, Twitter/X, Facebook
- 🔒 **Private Video Downloads**: Enhanced extraction methods for private content
- ⚡ **Queue Management**: Concurrent downloads with smart rate limiting
- 📊 **Analytics**: Comprehensive download statistics and user tracking
- 🛡️ **Rate Limiting**: Prevent abuse with configurable limits
- 🔄 **Auto-Retry**: Multiple extraction attempts for better success rates
- 👑 **Admin Panel**: Detailed system monitoring and statistics
- 📱 **User-Friendly**: Simple interface with command menu integration

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/telegram-video-downloader
   cd telegram-video-downloader
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file**
   ```bash
   cp .env.example .env
   ```

4. **Configure your bot**
   Edit `.env` file:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ADMIN_IDS=your_user_id,another_admin_id
   INSTAGRAM_COOKIES_PATH=cookies/instagram.txt
   TIKTOK_COOKIES_PATH=cookies/tiktok.txt
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

## 📋 Requirements

Create a `requirements.txt` file with:

```
# Telegram Bot Framework - Use specific working version
python-telegram-bot==20.3

# Video Downloading
yt-dlp>=2023.12.30

# Environment Variables
python-dotenv>=1.0.0

# Enhanced Features Added
# All features are built-in, no additional dependencies needed!

# Optional: Enhanced Functionality
# requests>=2.31.0        # For HTTP requests (if needed)
# aiofiles>=23.0.0        # For async file operations (if needed)
# pillow>=10.0.0          # For image processing (if needed)

# Development Dependencies (uncomment if needed)
# pytest>=7.0.0           # For testing
# black>=23.0.0           # Code formatting
# flake8>=6.0.0           # Code linting
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | ✅ Yes | - |
| `ADMIN_IDS` | Comma-separated admin user IDs | ❌ No | - |
| `INSTAGRAM_COOKIES_PATH` | Path to Instagram cookies file | ❌ No | `cookies/instagram.txt` |
| `TIKTOK_COOKIES_PATH` | Path to TikTok cookies file | ❌ No | `cookies/tiktok.txt` |

### Rate Limiting Settings

You can modify these in the code:

```python
RATE_LIMIT_REQUESTS = 3      # Downloads per time window
RATE_LIMIT_WINDOW = 300      # Time window in seconds (5 minutes)
MAX_CONCURRENT_DOWNLOADS = 2  # Simultaneous downloads
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_VIDEO_DURATION = 900     # 15 minutes
```

## 🔒 Private Video Support

For better success with private videos, you can optionally provide cookie files:

1. **Create cookies directory**
   ```bash
   mkdir cookies
   ```

2. **Export cookies** from your browser using extensions like:
   - "Get cookies.txt" 
   - "Cookie Editor"

3. **Save cookies** in Netscape format:
   - `cookies/instagram.txt` - Instagram cookies
   - `cookies/tiktok.txt` - TikTok cookies

## 🎯 Supported Platforms

| Platform | Public Videos | Private Videos | Notes |
|----------|---------------|----------------|-------|
| TikTok | ✅ | ✅ | Enhanced extraction methods |
| Instagram | ✅ | ✅ | Stories, posts, reels |
| Twitter/X | ✅ | ⚠️ | Limited private support |
| Facebook | ✅ | ⚠️ | Public posts and fb.watch |

## 📱 Commands

### User Commands
- `/start` - Welcome message and bot info
- `/help` - Detailed usage instructions
- `/status` - Check your rate limit status
- `/queue` - View download queue status
- `/stats` - Your personal download statistics

### Admin Commands
- `/admin` - Access admin panel with system stats

## 🔧 Usage

1. **Start the bot** - Send `/start` to get information
2. **Send a video link** - Just paste any supported platform URL
3. **Wait for download** - Bot will queue and process your request
4. **Receive video** - Downloaded video will be sent to you

### Example
```
User: https://www.tiktok.com/@user/video/1234567890
Bot: ✅ Added TikTok video to queue!
     📍 Position: 1
     📊 Remaining downloads: 2/3
     ⏱️ Estimated wait: ~45s

Bot: 🎬 Preparing download...
Bot: ⏬ Downloading... 50% at 2.1MB/s
Bot: 📤 Upload in progress...
Bot: [VIDEO FILE] ✅ Downloaded from TikTok
     👤 @username
     📁 15.2MB
```

## 📊 Analytics

The bot tracks comprehensive analytics:

- **Download Statistics**: Total downloads, daily counts, platform breakdown
- **User Activity**: Individual user stats, active users
- **Error Tracking**: Failed downloads by platform
- **Private Video Stats**: Success rates for private content
- **System Metrics**: Queue status, uptime, storage usage

Analytics are automatically saved to `analytics.json` and persist between restarts.

## 🛠️ Advanced Features

### Queue System
- **Concurrent Processing**: Multiple downloads simultaneously
- **Fair Queuing**: First-come, first-served processing
- **Progress Tracking**: Real-time download progress updates
- **Auto-cleanup**: Temporary files automatically removed

### Error Handling
- **Smart Retry**: Multiple extraction attempts with different methods
- **User-Friendly Messages**: Technical errors converted to readable messages
- **Comprehensive Logging**: Detailed logs for debugging

### Rate Limiting
- **Per-User Limits**: Prevent individual user abuse
- **Time Windows**: Rolling time-based restrictions
- **Admin Exemption**: Admins can bypass rate limits
- **Graceful Degradation**: Clear messages when limits exceeded

## 🐛 Troubleshooting

### Common Issues

**Bot doesn't respond to commands:**
- Check if the bot token is correct
- Ensure the bot is started with `/start`
- Verify network connectivity

**Downloads fail:**
- Check if the video is public and accessible
- Try a different video from the same platform
- Check the logs for specific error messages

**Private videos don't work:**
- Ensure cookie files are properly formatted
- Check cookie file permissions
- Verify cookies are still valid

**Rate limiting issues:**
- Wait for the rate limit window to reset
- Check your remaining requests with `/status`
- Contact admin if you think there's an error

### Logs

Check `bot.log` for detailed error information:
```bash
tail -f bot.log
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This bot is for educational purposes only. Users are responsible for complying with the terms of service of the platforms they download content from. Respect copyright laws and content creators' rights.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video extraction library
- [@BotFather](https://t.me/BotFather) - Telegram's bot creation tool

## 📧 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yourusername/telegram-video-downloader/issues) page
2. Create a new issue with detailed information
3. Contact the bot admin using `/admin` command (if you're authorized)

---

Made with ❤️ for the community