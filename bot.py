"""
Telegram Bot Handler for Railway Deployment
Handles user input and triggers video generation
"""

import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from main import VideoGenerator, Logger
from datetime import datetime, timedelta
import json

# ============================================
# CONFIG
# ============================================

class BotConfig:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")  # Comma-separated user IDs
    
    # Rate limiting (1 video per day per user)
    COOLDOWN_HOURS = 24
    USER_COOLDOWNS = {}  # {user_id: last_generation_time}

# ============================================
# RATE LIMITER
# ============================================

class RateLimiter:
    @staticmethod
    def can_generate(user_id: int) -> tuple[bool, str]:
        """Check if user can generate video"""
        
        if str(user_id) in BotConfig.ADMIN_IDS:
            return True, ""
        
        if user_id in BotConfig.USER_COOLDOWNS:
            last_time = BotConfig.USER_COOLDOWNS[user_id]
            time_passed = datetime.now() - last_time
            
            if time_passed < timedelta(hours=BotConfig.COOLDOWN_HOURS):
                hours_left = BotConfig.COOLDOWN_HOURS - (time_passed.total_seconds() / 3600)
                return False, f"⏳ Tunggu {hours_left:.1f} jam lagi untuk generate video berikutnya."
        
        return True, ""
    
    @staticmethod
    def mark_generated(user_id: int):
        """Mark user as generated"""
        BotConfig.USER_COOLDOWNS[user_id] = datetime.now()

# ============================================
# COMMAND HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    
    welcome_text = """
🎬 **AI YouTube Video Generator Bot**

Buat video YouTube otomatis dengan AI!

**Commands:**
/buatvideo - Mulai buat video
/status - Cek status bot
/help - Bantuan

**Batasan:**
• 1 video per 24 jam per user
• Short video: 35-45 detik (7 scene)
• Long video: 3-5 menit (14-18 scene)

Ketik /buatvideo untuk mulai! 🚀
"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    
    help_text = """
📖 **Cara Pakai:**

1. Ketik: `/buatvideo`
2. Ikuti instruksi bot
3. Tunggu proses (5-10 menit)
4. Terima video!

**Format Input:**
```
Topik: teknologi AI masa depan
Mode: short (atau long)
Style: cinematic futuristic
```

**Tips:**
• Topik jelas & spesifik
• Short = viral potential
• Long = depth & value
• Style = kualitas visual

**Troubleshooting:**
• Bot lama? Server sedang load
• Error? Coba lagi 5 menit
• Stuck? Contact admin
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    
    user_id = update.effective_user.id
    can_gen, msg = RateLimiter.can_generate(user_id)
    
    if can_gen:
        status_text = "✅ **Status:** Siap generate video!"
    else:
        status_text = f"⏳ **Status:** {msg}"
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def buatvideo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buatvideo command"""
    
    user_id = update.effective_user.id
    
    # Check rate limit
    can_generate, cooldown_msg = RateLimiter.can_generate(user_id)
    if not can_generate:
        await update.message.reply_text(cooldown_msg)
        return
    
    # Ask for input
    instruction = """
📝 **Kirim detail video dalam format ini:**

```
Topik: [topik video kamu]
Mode: short atau long
Style: [gaya visual, contoh: cinematic, futuristic, minimalist]
```

**Contoh:**
```
Topik: Teknologi AI yang mengubah dunia
Mode: short
Style: cinematic futuristic
```

Ketik sekarang! 👇
"""
    
    await update.message.reply_text(instruction, parse_mode='Markdown')
    
    # Set state waiting for input
    context.user_data['waiting_for_input'] = True

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for video generation"""
    
    # Check if waiting for input
    if not context.user_data.get('waiting_for_input', False):
        return
    
    user_id = update.effective_user.id
    text = update.message.text
    
    # Parse input
    try:
        config = parse_video_config(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Format salah! Error: {str(e)}\n\nCoba lagi dengan format yang benar.")
        return
    
    # Clear waiting state
    context.user_data['waiting_for_input'] = False
    
    # Confirm and start
    confirm_text = f"""
✅ **Video Config Diterima!**

📌 Topik: {config['topic']}
🎬 Mode: {config['mode'].upper()}
🎨 Style: {config['style']}

⏳ Generating video... (5-10 menit)
Kamu akan dapat notifikasi setelah selesai!
"""
    
    await update.message.reply_text(confirm_text, parse_mode='Markdown')
    
    # Start generation in background
    asyncio.create_task(generate_video_task(update, context, config, user_id))

async def generate_video_task(update: Update, context: ContextTypes.DEFAULT_TYPE, config: dict, user_id: int):
    """Background task for video generation"""
    
    try:
        # Progress updates
        await update.message.reply_text("🧠 [1/5] Brainstorming dengan Gemini AI...")
        
        generator = VideoGenerator()
        
        # Generate video
        result = await generator.generate(
            topic=config['topic'],
            mode=config['mode'],
            style=config['style']
        )
        
        # Mark user as generated
        RateLimiter.mark_generated(user_id)
        
        # Success message
        success_text = f"""
✅ **VIDEO BERHASIL DIBUAT!**

📌 Title: {result['metadata']['title']}
📁 File: {result['video_path'].name}
⏱️ Duration: ~{config['mode'] == 'short' and '40' or '240'} detik

💾 File size: {result['video_path'].stat().st_size / 1024 / 1024:.1f} MB

🎉 Video siap diupload ke YouTube!
"""
        
        await update.message.reply_text(success_text, parse_mode='Markdown')
        
        # Send video file (if size < 50MB, Telegram limit)
        file_size_mb = result['video_path'].stat().st_size / 1024 / 1024
        
        if file_size_mb < 50:
            await update.message.reply_text("📤 Mengirim video...")
            with open(result['video_path'], 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"🎬 {result['metadata']['title']}"
                )
        else:
            await update.message.reply_text(
                "⚠️ Video terlalu besar untuk Telegram (>50MB).\n"
                "File tersimpan di server. Admin akan mengirim link download."
            )
        
        # Cleanup
        result['video_path'].unlink(missing_ok=True)
        
    except Exception as e:
        Logger.error(f"Video generation failed: {str(e)}")
        
        error_text = f"""
❌ **Generation Gagal!**

Error: {str(e)}

🔄 Silakan coba lagi atau hubungi admin.
"""
        
        await update.message.reply_text(error_text, parse_mode='Markdown')

def parse_video_config(text: str) -> dict:
    """Parse user input into config dict"""
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    config = {
        'topic': '',
        'mode': 'short',
        'style': 'cinematic'
    }
    
    for line in lines:
        if ':' not in line:
            continue
        
        key, value = line.split(':', 1)
        key = key.strip().lower()
        value = value.strip()
        
        if 'topik' in key or 'topic' in key:
            config['topic'] = value
        elif 'mode' in key:
            if 'long' in value.lower():
                config['mode'] = 'long'
            else:
                config['mode'] = 'short'
        elif 'style' in key or 'gaya' in key:
            config['style'] = value
    
    if not config['topic']:
        raise ValueError("Topik tidak boleh kosong!")
    
    return config

# ============================================
# MAIN BOT
# ============================================

def main():
    """Start the bot"""
    
    if not BotConfig.TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        return
    
    # Create application
    app = Application.builder().token(BotConfig.TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("buatvideo", buatvideo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    
    # Start bot
    print("🤖 Bot started!")
    print(f"🔗 Bot username: @{app.bot.username if hasattr(app.bot, 'username') else 'unknown'}")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
