import discord
from discord.ext import commands

class Main(commands.Cog, description="雜項"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """bot ping"""
        await ctx.send(f"{round(self.bot.latency*1000)} ms")

def setup(bot):
    bot.add_cog(Main(bot))