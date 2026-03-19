import discord
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1480921604677570560  # your guild ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(e)

    print(f"Logged in as {bot.user}")

# Guild-only slash command
@bot.tree.command(
    name="test",
    description="Test command with 3 fields",
    guild=discord.Object(id=GUILD_ID)
)
async def test(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Test Command",
        description="Guild-only test embed",
        color=discord.Color.blue()
    )

    embed.add_field(name="Field 1", value="Value 1", inline=False)
    embed.add_field(name="Field 2", value="Value 2", inline=False)
    embed.add_field(name="Field 3", value="Value 3", inline=False)

    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
