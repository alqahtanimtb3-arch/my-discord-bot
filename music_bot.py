import discord
from discord.ext import commands
from discord.ui import View, button
import yt_dlp
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

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

# قريست أو قائمة الانتظار لكل سيرفر
# المفتاح هو الـ guild_id والقيمة هي قائمة الأغانيات المنتظرة
queues = {}
current_volumes = {}

class MusicControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
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

    @button(label="⏭️ سكيب", style=discord.ButtonStyle.secondary)
    async def skip_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop() # إيقاف الأغنية الحالية سيجعل البوت يشغل اللي بعدها في القائمة تلقائياً
            await interaction.response.send_message("⏭️ تم تخطي الأغنية.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شيء عشان تسوي له سكيب!", ephemeral=True)

    @button(label="⏹️ إيقاف", style=discord.ButtonStyle.danger)
    async def stop_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = self.ctx.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        vc = self.ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏹️ تم إيقاف الصوت وتفريغ القائمة.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شيء شغال أصلاً!", ephemeral=True)

def play_next(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and len(queues[guild_id]) > 0:
        next_url, next_title, author = queues[guild_id].pop(0)
        volume = current_volumes.get(guild_id, 0.5)
        
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(next_url, **FFMPEG_OPTIONS), volume=volume)
        
        def after_playing(error):
            if error:
                print(f"Error: {error}")
            play_next(ctx)

        ctx.voice_client.play(source, after=after_playing)
        
        # إرسال رسالة بالصوت الجديد
        fut = asyncio.run_coroutine_threadsafe(
            ctx.send(f"🎶 **جاري التشغيل (بطلب من {author}):** {next_title}"), bot.loop
        )
        try:
            fut.result()
        except Exception:
            pass
    else:
        # إذا خلصت القائمة، ممكن تخليه يفصل أو ينتظر
        pass

@bot.event
async def on_ready():
    print(f"✅ البوت شغال وجاهز باسم: {bot.user.name}")

@bot.command(name="ش")
async def play(ctx, *, query: str = None):
    if not query:
        await ctx.send("❌ اكتب اسم الأغنية أو الرابط بعد حرف ش!")
        return

    if not ctx.author.voice:
        await ctx.send("❌ لازم تكون داخل روم صوتي أول!")
        return

    voice_channel = ctx.author.voice.channel
    guild_id = ctx.guild.id

    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    async with ctx.typing():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]

            url = info['url']
            title = info.get('title', 'مقطع صوتي')

    if guild_id not in current_volumes:
        current_volumes[guild_id] = 0.5

    # إذا فيه أغنية شغالة أساساً، ضف الجديدة للقائمة
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        if guild_id not in queues:
            queues[guild_id] = []
        queues[guild_id].append((url, title, ctx.author.name))
        await ctx.send(qf := f"⏳ **تمت الإضافة للقائمة:** {title}\n📌 ترتيبها في الدور رقم: {len(queues[guild_id])}")
    else:
        # إذا ما فيه شيء شغال، شغلها فوراً
        if guild_id not in queues:
            queues[guild_id] = []
        
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=current_volumes[guild_id])
        
        def after_playing(error):
            if error:
                print(f"Error: {error}")
            play_next(ctx)

        ctx.voice_client.play(source, after=after_playing)
        view = MusicControlView(ctx)
        await ctx.send(f"🎶 **جاري التشغيل:** {title}\n👤 **بطلب من:** {ctx.author.name}", view=view)

@bot.command(name="ص")
async def volume(ctx, vol: int = None):
    guild_id = ctx.guild.id
    if vol is None or not (1 <= vol <= 150):
        await ctx.send("❌ اختر رقم صوت بين 1 و 150! (مثال: `ص 80`)")
        return

    current_volumes[guild_id] = vol / 100.0
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = current_volumes[guild_id]

    await ctx.send(f"🔊 تم ضبط مستوى الصوت على: **{vol}%**")

@bot.command(name="س")
async def stop(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        queues[guild_id].clear()
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        await ctx.send("⏹️ تم إيقاف الصوت وتفريغ القائمة.")
    else:
        await ctx.send("❌ ما فيه شيء شغال حالياً!")

@bot.command(name="خ")
async def leave(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        queues[guild_id].clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 تم الخروج من الروم.")
    else:
        await ctx.send("❌ البوت مو داخل روم أصلاً!")

bot.run(os.getenv('DISCORD_TOKEN'))