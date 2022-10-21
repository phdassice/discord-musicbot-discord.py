import os
import discord
from discord import Intents
from discord.ext import commands
from pretty_help import PrettyHelp

owners = [使用者ID]
activity = discord.Activity(type=discord.ActivityType.playing, name="可以改")
bot = commands.Bot(command_prefix="你要的前奏, activity=activity, owner_ids = set(owners), intents=Intents.all())
ending_note = "可以改"
bot.help_command = PrettyHelp(color=0xffffff, ending_note=ending_note)
@bot.event
#當機器人完成啟動時
async def on_ready():
	print('> 啟動的機器人是：', bot.user)
	print('機器人成功載入資料可以聽音樂了')
@bot.command()
async def load(ctx, extension):
  """開發者專用"""
  is_owner = await ctx.bot.is_owner(ctx.author)
  if is_owner:
	  bot.load_extension(f'cogs.{extension}')
	  await ctx.send(f'載入{extension}完成')
  else:
    await ctx.send("你好像沒有權限使用這個指令欸你卻定你是開發者嗎?")

@bot.command()
async def unload(ctx, extension):
  """開發者專用"""
  is_owner = await ctx.bot.is_owner(ctx.author)
  if is_owner:
	  bot.unload_extension(f'cogs.{extension}')
	  await ctx.send(f'卸載{extension}完成')
  else:
    await ctx.send("你好像沒有權限使用這個指令欸你卻定你是開發者嗎?")

@bot.command()
async def reload(ctx, extension):
  """開發者專用"""
  is_owner = await ctx.bot.is_owner(ctx.author)
  if is_owner:
	  bot.reload_extension(f'cogs.{extension}')
	  await ctx.send(f'重新載入{extension}完成')
  else:
    await ctx.send("你好像沒有權限使用這個指令欸你卻定你是開發者嗎?")

@bot.command()
async def reloadall(ctx):
  """開發者專用"""
  is_owner = await ctx.bot.is_owner(ctx.author)
  if is_owner:
    for file in os.listdir("cogs"):
      if file.endswith(".py"):
        name = file[:-3]
        bot.reload_extension(f"cogs.{name}")
    await ctx.send("重新載入成功")
  else:
    await ctx.send("你好像沒有權限使用這個指令欸你卻定你是開發者嗎?")

for Filename in os.listdir('./cogs'):
	if Filename.endswith('.py'):
		bot.load_extension(f'cogs.{Filename[:-3]}')

if __name__ == "__main__":
	bot.run('TOKEN')
    #TOKEN HERE