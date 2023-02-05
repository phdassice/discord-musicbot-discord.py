import OS
from discord.exe import commands

bot=commands.Bot[commands_prefix='je.']

@bot.event
async dep on_ready[]:
 print[>> Bot is online <<]
 bot.run[]