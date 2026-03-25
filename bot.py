import os
import discord
from discord import app_commands
from discord.ext import commands
import threading
from flask import Flask, request, jsonify
import requests
import logging
import uuid

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
PYTHON_SERVER_URL = "https://test-production-91a9.up.railway.app/push_payload"

ALLOWED_ROLES = ["Creator", "Moderator", "Sys"]

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

payload_queue = []
queue_lock = threading.Lock()

@app.route("/push_payload", methods=["POST"])
def push_payload():
    try:
        data = request.get_json()
        with queue_lock:
            payload_queue.append(data)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("push error:", e)
        return jsonify({"status": "error"}), 400

@app.route("/pop_payload", methods=["POST"])
def pop_payload():
    with queue_lock:
        if payload_queue:
            return jsonify(payload_queue.pop(0)), 200
        return jsonify({}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def has_allowed_role(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    return any(r.name in ALLOWED_ROLES for r in interaction.user.roles)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)

@bot.tree.command(name="time", description="Manage time", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Username", amount="Amount like 100,000", action="Action")
@app_commands.choices(action=[app_commands.Choice(name="Restore", value="Restore"), app_commands.Choice(name="Remove", value="Remove")])
async def time(interaction: discord.Interaction, user: str, amount: str, action: app_commands.Choice[str]):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("No permission!", ephemeral=True)
        return
    try:
        clean_amount = int(amount.replace(",", ""))
    except ValueError:
        await interaction.response.send_message("Invalid amount!", ephemeral=True)
        return

    payload = {"id": str(uuid.uuid4()), "attributes": {"username": user, "amount": str(clean_amount), "action": action.name}}
    try:
        requests.post(PYTHON_SERVER_URL, json=payload, timeout=5)
    except Exception as e:
        print("send failed:", e)

    embed = discord.Embed(title=action.name, color=discord.Color.from_rgb(80, 80, 80))
    embed.add_field(name="Successful", value=f"{clean_amount:,}", inline=True)
    embed.add_field(name="User", value=user, inline=True)
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gameban", description="Ban or Unban a player", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Username", action="Ban or Unban", reason="Reason", temp="Duration")
@app_commands.choices(
    action=[app_commands.Choice(name="Ban", value="Ban"), app_commands.Choice(name="Unban", value="Unban")],
    reason=[app_commands.Choice(name="Exploiting", value="Exploiting"), app_commands.Choice(name="Association", value="Association"), app_commands.Choice(name="Blacklisted", value="Blacklisted")],
    temp=[app_commands.Choice(name="1 Day", value="1 Day"), app_commands.Choice(name="7 Days", value="7 Days"), app_commands.Choice(name="30 Days", value="30 Days"), app_commands.Choice(name="3 Months", value="3 Months"), app_commands.Choice(name="1 Year", value="1 Year"), app_commands.Choice(name="Permanent", value="Permanent")]
)
async def gameban(interaction: discord.Interaction, user: str, action: app_commands.Choice[str], reason: app_commands.Choice[str] = None, temp: app_commands.Choice[str] = None):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("No permission!", ephemeral=True)
        return

    attrs = {"username": user, "action": action.name}
    if action.name == "Ban":
        attrs["reason"] = reason.name if reason else "No reason"
        attrs["duration"] = temp.name if temp else "Permanent"

    payload = {"id": str(uuid.uuid4()), "attributes": attrs}
    try:
        requests.post(PYTHON_SERVER_URL, json=payload, timeout=5)
    except Exception as e:
        print("send failed:", e)

    embed = discord.Embed(title=action.name, color=discord.Color.from_rgb(80, 80, 80))
    embed.add_field(name="Successful", value=user, inline=True)
    embed.add_field(name="Reason", value=reason.name if (action.name == "Ban" and reason) else "-", inline=True)
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(TOKEN)
