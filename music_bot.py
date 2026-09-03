import discord
from discord.ext import commands
import yt_dlp
import os

# إعدادات yt-dlp مع تفعيل ملف الكوكيز للتغلب على حظر يوتيوب
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'cookiefile': 'cookies.txt',  # استخدام ملف الكوكيز لتجنب مطالبة تسجيل الدخول
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

queues = {}
current_volumes = {}

# دالة لتشغيل الأغنية التالية في القائمة (ضعها مع دوال البوت لديك إذا لم تكن موجودة)
def play_next(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and len(queues[guild_id]) > 0:
        url, title, requester = queues[guild_id].pop(0)
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=current_volumes.get(guild_id, 0.5))
        
        def after_playing(error):
            if error:
                print(f"Error: {error}")
            play_next(ctx)
            
        ctx.voice_client.play(source, after=after_playing)

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
        search_query = query if query.startswith("http") else f"ytsearch:{query}"
        
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if 'entries' in info:
                    info = info['entries'][0]

                url = info['url']
                title = info.get('title', 'مقطع صوتي')
        except Exception as e:
            await ctx.send(f"❌ حدث خطأ أثناء البحث: تأكد من صحة ملف الكوكيز أو الرابط.")
            print(f"YT-DLP Error: {e}")
            return

    if guild_id not in current_volumes:
        current_volumes[guild_id] = 0.5

    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        if guild_id not in queues:
            queues[guild_id] = []
        queues[guild_id].append((url, title, ctx.author.name))
        await ctx.send(فا"⏳ **تمت الإضافة للقائمة:** {title}\n📌 ترتيبها في الدور رقم: {len(queues[guild_id])}")
    else:
        if guild_id not in queues:
            queues[guild_id] = []
        
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=current_volumes[guild_id])
        
        def after_playing(error):
            if error:
                print(f"Error: {error}")
            play_next(ctx)

        ctx.voice_client.play(source, after=after_playing)
        try:
            view = MusicControlView(ctx)
            await ctx.send(f"🎶 **جاري التشغيل:** {title}\n👤 **بطلب من:** {ctx.author.name}", view=view)
        except NameError:
            await ctx.send(f"🎶 **جاري التشغيل:** {title}\n👤 **بطلب من:** {ctx.author.name}")