import os
import discord
from discord import app_commands
from discord.ext import commands
import threading
from flask import Flask, request, jsonify
import requests
import json
import logging

# ---------------- CONFIG ----------------
TOKEN = os.environ["DISCORD_BOT_TOKEN"]        # Discord bot token from Railway env
GUILD_ID = int(os.environ["GUILD_ID"])        # Your Discord guild ID
PYTHON_SERVER_URL = f"{os.environ['PUBLIC_URL']}/update_payload"  # Railway public URL

# Allowed role names
ALLOWED_ROLES = ["Creator", "Moderator", "Sys"]

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

latest_payload = {}
last_sent_payload = {}

@app.route("/update_payload", methods=["POST"])
def update_payload():
    global latest_payload, last_sent_payload
    try:
        data = request.get_json()
        if data != last_sent_payload:
            latest_payload = data
            last_sent_payload = data.copy()
            print("----- New Payload Received from Discord -----")
            print(data)
            print("---------------------------------------------")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("Error processing payload:", e)
        return jsonify({"status": "error"}), 400

@app.route("/get_payload", methods=["GET"])
def get_payload():
    global latest_payload
    if not latest_payload:
        return "", 204
    payload_to_send = latest_payload.copy()
    latest_payload = {}
    return jsonify(payload_to_send), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))  # Railway uses $PORT
    app.run(host="0.0.0.0", port=port)

# ---------------- ROLE CHECK FUNCTION ----------------
def has_allowed_role(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    user_roles = [role.name for role in interaction.user.roles]
    return any(role in user_roles for role in ALLOWED_ROLES)

# ---------------- DISCORD BOT ----------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
last_sent_payload_bot = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)

# ---------------- /time COMMAND ----------------
@bot.tree.command(name="time", description="Manage time", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User or user ID", amount="Amount like 100,000", action="Action to perform")
@app_commands.choices(action=[
    app_commands.Choice(name="Restore", value="Restore"),
    app_commands.Choice(name="Reset", value="Reset"),
    app_commands.Choice(name="Remove", value="Remove")
])
async def time(interaction: discord.Interaction, user: str, amount: str, action: app_commands.Choice[str]):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    try:
        clean_amount = int(amount.replace(",", ""))
    except ValueError:
        await interaction.response.send_message("Invalid amount!", ephemeral=True)
        return
    payload = {"attributes": {"username": user, "amount": str(clean_amount), "action": action.name}}
    global last_sent_payload_bot
    if payload != last_sent_payload_bot:
        last_sent_payload_bot = json.loads(json.dumps(payload))
        print("----- /time Payload -----")
        print(payload)
        print("------------------------")
        try:
            requests.post(PYTHON_SERVER_URL, json=payload)
        except Exception as e:
            print("Failed to send to Flask server:", e)
    embed = discord.Embed(title=action.name, color=discord.Color.from_rgb(80, 80, 80))
    embed.add_field(name="Successful", value=f"{clean_amount:,}", inline=True)
    embed.add_field(name="User", value=user, inline=True)
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ---------------- /gameban COMMAND ----------------
@bot.tree.command(name="gameban", description="Ban or Unban a player", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User or user ID", action="Ban or Unban", reason="Reason for action", temp="Temporary duration (optional)")
@app_commands.choices(
    action=[app_commands.Choice(name="Ban", value="Ban"), app_commands.Choice(name="Unban", value="Unban")],
    reason=[app_commands.Choice(name="Exploiting", value="Exploiting"), app_commands.Choice(name="Association", value="Association"), app_commands.Choice(name="Blacklisted", value="Blacklisted")],
    temp=[app_commands.Choice(name="1 Day", value="1 Day"), app_commands.Choice(name="7 Days", value="7 Days"), app_commands.Choice(name="30 Days", value="30 Days"), app_commands.Choice(name="3 Months", value="3 Months"), app_commands.Choice(name="1 Year", value="1 Year"), app_commands.Choice(name="Permanent", value="Permanent")]
)
async def gameban(interaction: discord.Interaction, user: str, action: app_commands.Choice[str], reason: app_commands.Choice[str] = None, temp: app_commands.Choice[str] = None):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    duration_value = temp.name if temp else "Permanent"
    payload_attributes = {"username": user, "action": action.name}
    if action.name == "Ban":
        payload_attributes["reason"] = reason.name if reason else "No reason"
        payload_attributes["duration"] = duration_value
    payload = {"attributes": payload_attributes}
    global last_sent_payload_bot
    if payload != last_sent_payload_bot:
        last_sent_payload_bot = json.loads(json.dumps(payload))
        print(f"----- /gameban Payload ({action.name}) -----")
        print(payload)
        print("--------------------------------------------")
        try:
            requests.post(PYTHON_SERVER_URL, json=payload)
        except Exception as e:
            print("Failed to send to Flask server:", e)
    embed = discord.Embed(title=action.name, color=discord.Color.from_rgb(80, 80, 80))
    embed.add_field(name="Successful", value=user, inline=True)
    reason_text = reason.name if (action.name == "Ban" and reason) else "-"
    embed.add_field(name="Reason", value=reason_text, inline=True)
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ---------------- RUN BOTH ----------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(TOKEN)
