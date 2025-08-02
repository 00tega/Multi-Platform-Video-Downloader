from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
import yt_dlp
import os
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
import logging
import json
import shutil
import re

# Load environment variables from .env file
load_dotenv()

# === Logging Configuration ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === Configuration ===
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Please set TELEGRAM_BOT_TOKEN in your .env file")

ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
RATE_LIMIT_REQUESTS = 3
RATE_LIMIT_WINDOW = 300
MAX_CONCURRENT_DOWNLOADS = 2
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_VIDEO_DURATION = 600  # 10 minutes

# === Analytics Storage ===
analytics = {
    'total_downloads': 0,
    'daily_downloads': defaultdict(int),
    'platform_stats': defaultdict(int),
    'user_stats': defaultdict(int),
    'error_stats': defaultdict(int),
    'start_time': datetime.now()
}

# Load existing analytics
def load_analytics():
    try:
        if os.path.exists('analytics.json'):
            with open('analytics.json', 'r') as f:
                data = json.load(f)
                analytics.update(data)
                analytics['start_time'] = datetime.fromisoformat(analytics.get('start_time', datetime.now().isoformat()))
    except Exception as e:
        logger.error(f"Failed to load analytics: {e}")

def save_analytics():
    try:
        data = analytics.copy()
        data['start_time'] = analytics['start_time'].isoformat()
        with open('analytics.json', 'w') as f:
            json.dump(data, f, default=str)
    except Exception as e:
        logger.error(f"Failed to save analytics: {e}")

load_analytics()

# === Rate Limiting Storage ===
user_requests = defaultdict(deque)
download_queue = asyncio.Queue()
active_downloads = 0
download_lock = asyncio.Lock()
user_progress = {}  # Track download progress per user

class RateLimiter:
    def __init__(self, max_requests=3, window_seconds=300):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests = defaultdict(deque)
    
    def is_allowed(self, user_id):
        now = datetime.now()
        user_queue = self.user_requests[user_id]
        
        # Remove old requests outside the time window
        while user_queue and user_queue[0] < now - timedelta(seconds=self.window_seconds):
            user_queue.popleft()
        
        # Check if user has exceeded rate limit
        if len(user_queue) >= self.max_requests:
            return False, user_queue[0] + timedelta(seconds=self.window_seconds)
        
        # Add current request timestamp
        user_queue.append(now)
        return True, None
    
    def get_remaining_requests(self, user_id):
        now = datetime.now()
        user_queue = self.user_requests[user_id]
        
        # Clean old requests
        while user_queue and user_queue[0] < now - timedelta(seconds=self.window_seconds):
            user_queue.popleft()
        
        return max(0, self.max_requests - len(user_queue))

rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

def get_platform_from_url(url):
    """Extract platform name from URL"""
    if 'tiktok.com' in url:
        return 'TikTok'
    elif 'instagram.com' in url:
        return 'Instagram'
    elif any(domain in url for domain in ['twitter.com', 'x.com']):
        return 'Twitter/X'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'Facebook'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'YouTube'
    return 'Unknown'

def get_error_message(error_str):
    """Convert technical errors to user-friendly messages"""
    error_lower = str(error_str).lower()
    
    if 'private' in error_lower or 'unavailable' in error_lower:
        return "❌ This video is private or unavailable. Make sure it's public!"
    elif 'not found' in error_lower or '404' in error_lower:
        return "❌ Video not found. The link might be broken or the video was deleted."
    elif 'geo' in error_lower or 'region' in error_lower:
        return "❌ This video is blocked in your region."
    elif 'login' in error_lower or 'authentication' in error_lower:
        return "❌ This video requires login. Please use a public video."
    elif 'network' in error_lower or 'connection' in error_lower:
        return "❌ Network error. Please try again in a moment."
    elif 'timeout' in error_lower:
        return "❌ Download timed out. The video might be too large or server is slow."
    elif 'format' in error_lower:
        return "❌ Video format not supported or no suitable format found."
    else:
        return f"❌ Download failed: {str(error_str)[:100]}..."

# === Progress Hook for yt-dlp ===
def create_progress_hook(user_id, update, loop):
    """Create a progress hook for yt-dlp downloads"""
    
    def progress_hook(d):
        try:
            if d['status'] == 'downloading':
                if user_id in user_progress:
                    percent = d.get('_percent_str', 'N/A').strip()
                    speed = d.get('_speed_str', 'N/A').strip()
                    
                    # Update progress every 10% to avoid spam
                    current_percent = float(percent.replace('%', '')) if percent != 'N/A' else 0
                    last_percent = user_progress[user_id].get('last_percent', 0)
                    
                    if current_percent - last_percent >= 10 or current_percent >= 99:
                        user_progress[user_id]['last_percent'] = current_percent
                        progress_text = f"⏬ Downloading... {percent}"
                        if speed != 'N/A':
                            progress_text += f" at {speed}"
                        
                        # Schedule the update in the event loop
                        try:
                            asyncio.run_coroutine_threadsafe(
                                user_progress[user_id]['message'].edit_text(progress_text),
                                loop
                            )
                        except:
                            pass  # Ignore edit errors
                            
            elif d['status'] == 'finished':
                if user_id in user_progress:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            user_progress[user_id]['message'].edit_text("📤 Upload in progress..."),
                            loop
                        )
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Progress hook error: {e}")
    
    return progress_hook

# === Download Queue Worker ===
async def download_worker():
    """Background worker that processes download queue"""
    global active_downloads
    
    logger.info("Download worker started")
    
    while True:
        try:
            task = await download_queue.get()
            
            async with download_lock:
                while active_downloads >= MAX_CONCURRENT_DOWNLOADS:
                    await asyncio.sleep(1)
                active_downloads += 1
            
            await process_download_task(task)
            download_queue.task_done()
            
            async with download_lock:
                active_downloads -= 1
                
        except Exception as e:
            logger.error(f"Download worker error: {e}")
            async with download_lock:
                active_downloads = max(0, active_downloads - 1)

async def process_download_task(task):
    """Process individual download task"""
    update, url = task
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    platform = get_platform_from_url(url)
    
    logger.info(f"Processing {platform} download for user {user_id} (@{username}): {url}")
    
    try:
        # Send initial progress message
        progress_msg = await update.message.reply_text("🎬 Preparing download...")
        user_progress[user_id] = {
            'message': progress_msg,
            'last_percent': 0
        }
        
        # yt-dlp options
        ydl_opts = {
            'outtmpl': '%(id)s_%(uploader)s.%(ext)s',
            'format': 'mp4/best[filesize<50M]/best',
            'noplaylist': True,
            'extract_flat': False,
            'progress_hooks': [create_progress_hook(user_id, update, asyncio.get_event_loop())],
        }
        
        # Extract video info first
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                # Check video duration
                duration = info.get('duration', 0)
                if duration and duration > MAX_VIDEO_DURATION:
                    await progress_msg.edit_text(
                        f"❌ Video too long ({duration//60}m {duration%60}s). "
                        f"Maximum allowed: {MAX_VIDEO_DURATION//60} minutes."
                    )
                    return
                
                # Check file size estimate
                filesize = info.get('filesize') or info.get('filesize_approx', 0)
                if filesize and filesize > MAX_FILE_SIZE:
                    size_mb = filesize / (1024 * 1024)
                    await progress_msg.edit_text(
                        f"❌ Video too large ({size_mb:.1f}MB). "
                        f"Maximum allowed: {MAX_FILE_SIZE//1024//1024}MB."
                    )
                    return
                
                # Show video info
                title = info.get('title', 'Unknown')[:50]
                uploader = info.get('uploader', 'Unknown')
                duration_str = f"{duration//60}m {duration%60}s" if duration else "Unknown"
                
                await progress_msg.edit_text(
                    f"📹 *{title}*\n"
                    f"👤 {uploader}\n"
                    f"⏱️ {duration_str}\n"
                    f"🎬 Starting download..."
                )
                
            except Exception as e:
                logger.warning(f"Failed to extract info for {url}: {e}")
                info = None
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        # Send the video
        try:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                with open(file_path, 'rb') as video_file:
                    caption = (
                        f"✅ Downloaded from {platform}\n"
                        f"👤 {info.get('uploader', 'Unknown')}\n"
                        f"📁 {file_size/(1024*1024):.1f}MB"
                    )
                    
                    await update.message.reply_video(
                        video=video_file,
                        caption=caption
                    )
                
                # Update analytics
                analytics['total_downloads'] += 1
                analytics['daily_downloads'][datetime.now().strftime('%Y-%m-%d')] += 1
                analytics['platform_stats'][platform] += 1
                analytics['user_stats'][user_id] += 1
                save_analytics()
                
                logger.info(f"Successfully sent {platform} video to user {user_id}")
                
        except Exception as e:
            error_msg = get_error_message(str(e))
            await progress_msg.edit_text(f"⚠️ Failed to send video: {error_msg}")
            logger.error(f"Failed to send video to user {user_id}: {e}")
            
        finally:
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up file: {file_path}")
            
            if user_id in user_progress:
                del user_progress[user_id]
                
    except Exception as e:
        error_msg = get_error_message(str(e))
        await user_progress.get(user_id, {}).get('message', update.message).reply_text(error_msg)
        
        # Update error analytics
        analytics['error_stats'][platform] += 1
        save_analytics()
        
        logger.error(f"Download failed for user {user_id} ({platform}): {e}")
        
        if user_id in user_progress:
            del user_progress[user_id]

# === Set up clickable bot commands ===
async def set_commands(application):
    commands = [
        BotCommand("start", "Start the bot and get instructions"),
        BotCommand("help", "Get help on how to use the bot"),
        BotCommand("status", "Check your rate limit status"),
        BotCommand("queue", "Check download queue status"),
        BotCommand("stats", "View your download statistics")
    ]
    
    if ADMIN_IDS:
        commands.append(BotCommand("admin", "Admin panel (admins only)"))
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands set successfully")

# === Command Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "there"
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    keyboard = [
        [InlineKeyboardButton("📊 My Stats", callback_data="user_stats")],
        [InlineKeyboardButton("📋 Queue Status", callback_data="queue_status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Welcome {user_name}!\n\n"
        f"🎬 *Supported Platforms:*\n"
        f"• TikTok\n• Instagram\n• Twitter/X\n• Facebook\n• YouTube Shorts\n\n"
        f"📊 *Rate Limits:*\n"
        f"• {RATE_LIMIT_REQUESTS} downloads per {RATE_LIMIT_WINDOW//60} minutes\n"
        f"• Max {MAX_CONCURRENT_DOWNLOADS} concurrent downloads\n"
        f"• Max file size: {MAX_FILE_SIZE//1024//1024}MB\n"
        f"• Max duration: {MAX_VIDEO_DURATION//60} minutes\n\n"
        f"📤 Just send me a video link to get started!",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📌 *How to use this bot:*\n\n"
        "1️⃣ Send me a video link from supported platforms\n"
        "2️⃣ Wait for the download to complete\n"
        "3️⃣ Receive your video!\n\n"
        "🎬 *Supported Platforms:*\n"
        "• TikTok (tiktok.com)\n"
        "• Instagram (instagram.com)\n"
        "• Twitter/X (twitter.com, x.com)\n"
        "• Facebook (facebook.com, fb.watch)\n"
        "• YouTube Shorts (youtube.com, youtu.be)\n\n"
        "📊 *Commands:*\n"
        "• /status - Check your rate limit status\n"
        "• /queue - Check download queue status\n"
        "• /stats - View your download statistics\n\n"
        f"⚡ *Limits:* {RATE_LIMIT_REQUESTS} downloads per {RATE_LIMIT_WINDOW//60} minutes\n"
        f"📁 *Max file size:* {MAX_FILE_SIZE//1024//1024}MB\n"
        f"⏱️ *Max duration:* {MAX_VIDEO_DURATION//60} minutes\n\n"
        "_Note: Only public videos are supported._"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    remaining = rate_limiter.get_remaining_requests(user_id)
    
    status_text = (
        f"📊 *Your Status:*\n\n"
        f"• Remaining downloads: {remaining}/{RATE_LIMIT_REQUESTS}\n"
        f"• Rate limit window: {RATE_LIMIT_WINDOW//60} minutes\n"
        f"• Queue position: {download_queue.qsize()} pending\n"
        f"• Active downloads: {active_downloads}/{MAX_CONCURRENT_DOWNLOADS}\n"
        f"• Your total downloads: {analytics['user_stats'][user_id]}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue_size = download_queue.qsize()
    queue_text = (
        f"🔄 *Queue Status:*\n\n"
        f"• Pending downloads: {queue_size}\n"
        f"• Active downloads: {active_downloads}/{MAX_CONCURRENT_DOWNLOADS}\n"
        f"• Estimated wait: ~{queue_size * 30} seconds\n"
        f"• Bot uptime: {str(datetime.now() - analytics['start_time']).split('.')[0]}"
    )
    await update.message.reply_text(queue_text, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_downloads = analytics['user_stats'][user_id]
    
    # Top platforms for this user (simplified)
    remaining = rate_limiter.get_remaining_requests(user_id)
    
    stats_text = (
        f"📈 *Your Statistics:*\n\n"
        f"• Total downloads: {user_downloads}\n"
        f"• Remaining today: {remaining}/{RATE_LIMIT_REQUESTS}\n"
        f"• Account created: Just now\n\n"
        f"🏆 *Global Stats:*\n"
        f"• Total bot downloads: {analytics['total_downloads']}\n"
        f"• Downloads today: {analytics['daily_downloads'][datetime.now().strftime('%Y-%m-%d')]}\n"
        f"• Active users today: {len([u for u, c in analytics['user_stats'].items() if c > 0])}"
    )
    
    await update.message.reply_text(stats_text, parse_mode="Markdown")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    logger.info(f"Admin {user_id} accessed admin panel")
    
    # System stats
    disk_usage = shutil.disk_usage('.')
    uptime = datetime.now() - analytics['start_time']
    
    # Top platforms
    top_platforms = sorted(analytics['platform_stats'].items(), key=lambda x: x[1], reverse=True)[:5]
    platform_text = "\n".join([f"• {platform}: {count}" for platform, count in top_platforms])
    
    # Recent errors
    error_text = "\n".join([f"• {platform}: {count}" for platform, count in analytics['error_stats'].items()][:3])
    
    admin_text = (
        f"🔧 *Admin Panel*\n\n"
        f"📊 *System Status:*\n"
        f"• Uptime: {str(uptime).split('.')[0]}\n"
        f"• Total downloads: {analytics['total_downloads']}\n"
        f"• Active users: {len(analytics['user_stats'])}\n"
        f"• Queue size: {download_queue.qsize()}\n"
        f"• Active downloads: {active_downloads}/{MAX_CONCURRENT_DOWNLOADS}\n\n"
        f"💾 *Storage:*\n"
        f"• Free space: {disk_usage.free//1024//1024//1024}GB\n\n"
        f"🎬 *Top Platforms:*\n{platform_text}\n\n"
        f"❌ *Recent Errors:*\n{error_text or 'None'}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_detailed")],
        [InlineKeyboardButton("🔄 Restart Queue", callback_data="admin_restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(admin_text, parse_mode="Markdown", reply_markup=reply_markup)

# === Callback Query Handler ===
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "user_stats":
        await stats_command(update, context)
    elif query.data == "queue_status":
        await queue_command(update, context)
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "admin_detailed" and query.from_user.id in ADMIN_IDS:
        # Show detailed admin stats
        daily_stats = sorted(analytics['daily_downloads'].items())[-7:]  # Last 7 days
        daily_text = "\n".join([f"• {date}: {count}" for date, count in daily_stats])
        
        detailed_text = (
            f"📈 *Detailed Statistics*\n\n"
            f"📅 *Last 7 Days:*\n{daily_text}\n\n"
            f"👥 *User Activity:*\n"
            f"• Total unique users: {len(analytics['user_stats'])}\n"
            f"• Average downloads per user: {analytics['total_downloads'] / max(len(analytics['user_stats']), 1):.1f}"
        )
        
        await query.edit_message_text(detailed_text, parse_mode="Markdown")

# === Message Handler ===
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    url = update.message.text.strip()
    
    logger.info(f"Received URL from user {user_id} (@{username}): {url}")
    
    # Check rate limiting
    allowed, reset_time = rate_limiter.is_allowed(user_id)
    if not allowed:
        time_left = int((reset_time - datetime.now()).total_seconds())
        await update.message.reply_text(
            f"⏰ Rate limit exceeded!\n"
            f"Try again in {time_left//60}m {time_left%60}s\n"
            f"Use /status to check your limits."
        )
        return
    
    # Check supported platforms
    supported_domains = [
        'tiktok.com', 'instagram.com', 'twitter.com', 'x.com',
        'facebook.com', 'fb.watch', 'youtube.com', 'youtu.be'
    ]
    
    if not any(domain in url for domain in supported_domains):
        await update.message.reply_text(
            "❌ Unsupported platform!\n\n"
            "🎬 *Supported platforms:*\n"
            "• TikTok (tiktok.com)\n"
            "• Instagram (instagram.com)\n"
            "• Twitter/X (twitter.com, x.com)\n"
            "• Facebook (facebook.com, fb.watch)\n"
            "• YouTube Shorts (youtube.com, youtu.be)\n\n"
            "Use /help for more information."
        )
        return
    
    # Add to download queue
    await download_queue.put((update, url))
    queue_position = download_queue.qsize()
    platform = get_platform_from_url(url)
    
    remaining = rate_limiter.get_remaining_requests(user_id)
    await update.message.reply_text(
        f"✅ Added {platform} video to queue!\n"
        f"📍 Position: {queue_position}\n"
        f"📊 Remaining downloads: {remaining}/{RATE_LIMIT_REQUESTS}\n"
        f"⏱️ Estimated wait: ~{queue_position * 30}s"
    )

# === Application Setup ===
async def post_init(application):
    await set_commands(application)
    # Start the download worker
    asyncio.create_task(download_worker())
    logger.info("Bot initialization completed")

# Create application with simple approach - no custom timeouts for now
app = ApplicationBuilder().token(TOKEN).build()

# === Register Handlers ===
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("queue", queue_command))
app.add_handler(CommandHandler("stats", stats_command))
app.add_handler(CommandHandler("admin", admin_command))
app.add_handler(CallbackQueryHandler(button_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

# === Run the bot ===
if __name__ == "__main__":
    logger.info("🤖 Enhanced bot starting...")
    logger.info(f"📊 Rate limits: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW//60} minutes")
    logger.info(f"⚡ Max concurrent downloads: {MAX_CONCURRENT_DOWNLOADS}")
    logger.info(f"👑 Admin users: {len(ADMIN_IDS)}")
    
    try:
        # Initialize bot components
        async def startup():
            await post_init(app)
        
        # Run startup in the background
        asyncio.get_event_loop().run_until_complete(startup())
        
        # Start the bot
        app.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        save_analytics()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        save_analytics()
        raise