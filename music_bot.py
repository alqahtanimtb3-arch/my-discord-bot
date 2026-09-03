import discord
from discord.ext import commands
from discord.ui import View, button
import yt_dlp
import asyncio

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

# إعدادات yt-dlp للبحث واستخراج البيانات
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# متغيرات عامة لحفظ الحالة وسهولة التقديم والترجيع
current_volume = 0.5  # الصوت الافتراضي 50%
current_url = None
current_start_time = 0

# واجهة الأزرار التفاعلية بشات الروم
class MusicControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None) # الأزرار تبق شغال وما تنتهي
        self.ctx = ctx

    @button(label="⏸️ / ▶️", style=discord.ButtonStyle.primary)
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ تم الإيقاف المؤقت.", ephemeral=True)
        elif vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ تم إكمال التشغيل.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شيء شغال حالياً!", ephemeral=True)

    @button(label="⏹️ إيقاف", style=discord.ButtonStyle.danger)
    async def stop_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏹️ تم إيقاف الصوت.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شيء شغال أصلاً!", ephemeral=True)

    @button(label="⏪ -10 ثواني", style=discord.ButtonStyle.secondary)
    async def rewind_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_start_time
        vc = self.ctx.voice_client
        if vc and current_url:
            current_start_time = max(0, current_start_time - 10)
            await play_audio_at_time(self.ctx, current_url, current_start_time)
            await interaction.response.send_message(f"⏪ تم الترجيع لـ {current_start_time} ثانية.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شيء شغال حالياً!", ephemeral=True)

    @button(label="⏩ +10 ثواني", style=discord.ButtonStyle.secondary)
    async def forward_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_start_time
        vc = self.ctx.voice_client
        if vc and current_url:
            current_start_time += 10
            await play_audio_at_time(self.ctx, current_url, current_start_time)
            await interaction.response.send_message(f"⏩ تم التقديم لـ {current_start_time} ثانية.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شيء شغال حالياً!", ephemeral=True)

# دالة مساعدة لتشغيل الصوت عند وقت محدد (تفيد بالتقديم والترجيع)
async def play_audio_at_time(ctx, url, start_seconds=0):
    global current_volume
    ffmpeg_opts = {
        'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_seconds}',
        'options': '-vn'
    }
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **ffmpeg_opts), volume=current_volume)
    ctx.voice_client.play(source)

@bot.event
async def on_ready():
    print(f"✅ البوت شغال وجاهز باسم: {bot.user.name}")

# 1. أمر التشغيل: ش (اسم أو رابط)
@bot.command(name="ش")
async def play(ctx, *, query: str = None):
    global current_url, current_start_time, current_volume
    if not query:
        await ctx.send("❌ اكتب اسم الأغنية أو الرابط بعد حرف ش!")
        return

    if not ctx.author.voice:
        await ctx.send("❌ لازم تكون داخل روم صوتي أول!")
        return

    voice_channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    async with ctx.typing():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]

            current_url = info['url']
            title = info.get('title', 'مقطع صوتي')

        current_start_time = 0
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(current_url, **FFMPEG_OPTIONS), volume=current_volume)
        
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

        ctx.voice_client.play(source)

        # إرسال الرسالة مع الأزرار التفاعلية
        view = MusicControlView(ctx)
        await ctx.send(f"🎶 **جاري التشغيل:** {title}\n🔊 **مستوى الصوت الحالي:** {int(current_volume * 100)}%", view=view)

# 2. أمر التحكم بالصوت: ص (من 1 إلى 150)
@bot.command(name="ص")
async def volume(ctx, vol: int = None):
    global current_volume
    if vol is None or not (1 <= vol <= 150):
        await ctx.send("❌ اختر رقم صوت بين 1 و 150! (مثال: `ص 80`)")
        return

    current_volume = vol / 100.0
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = current_volume

    await ctx.send(f"🔊 تم ضبط مستوى الصوت على: **{vol}%**")

# 3. أمر إيقاف الصوت فقط: س
@bot.command(name="س")
async def stop(ctx):
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        await ctx.send("⏹️ تم إيقاف الصوت.")
    else:
        await ctx.send("❌ ما فيه شيء شغال حالياً!")

# 4. أمر الخروج نهائياً من الروم: خ
@bot.command(name="خ")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 تم الخروج من الروم.")
    else:
        await ctx.send("❌ البوت مو داخل روم أصلاً!")

bot.run("")