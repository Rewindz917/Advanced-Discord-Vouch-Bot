import discord
from discord.ext import commands
import sqlite3
import asyncio
from datetime import datetime, timedelta
import os
import threading
from flask import Flask, render_template, request, redirect, url_for

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ✅ Define the Flask app (IMPORTANT for Render)
app = Flask(__name__)

# Database setup
conn = sqlite3.connect("vouch_system.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS vouches (
                  user_id INTEGER PRIMARY KEY, 
                  vouches INTEGER DEFAULT 0, 
                  last_vouch TIMESTAMP,
                  reputation_tier TEXT DEFAULT 'Newbie')""")
conn.commit()

# Configurable Settings
VOUCH_CHANNEL_ID = 1334059188963250206  # Replace with actual channel ID
VERIFIED_ROLE_ID = 1336220939632771174  # Role given by verification bot
VOUCH_ROLES = ["Customer ( s )", "Plo1x Modz"]  # Roles that can vouch
COOLDOWN_TIME = 24  # Cooldown in hours
REPUTATION_TIERS = {5: "Beginner", 10: "Intermediate", 20: "Advanced", 50: "Expert"}

# ✅ Web Dashboard Routes
@app.route("/")
def home():
    cursor.execute("SELECT user_id, vouches, reputation_tier FROM vouches ORDER BY vouches DESC")
    vouch_data = cursor.fetchall()
    return render_template("dashboard.html", vouches=vouch_data)

@app.route("/reset_vouch", methods=["POST"])
def reset_vouch():
    user_id = request.form.get("user_id")
    cursor.execute("DELETE FROM vouches WHERE user_id = ?", (user_id,))
    conn.commit()
    return redirect(url_for("home"))

# ✅ Run Flask Dashboard in a Separate Thread
def run_dashboard():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

# Check if a user has permission to vouch
def has_vouch_permission(member):
    return any(role.name in VOUCH_ROLES for role in member.roles)

# Check if a user is verified
def is_verified(member):
    return any(role.id == VERIFIED_ROLE_ID for role in member.roles)

@bot.tree.command()
async def vouch(interaction: discord.Interaction, member: discord.Member):
    """Allows a user to vouch for another user"""
    if not is_verified(interaction.user):
        await interaction.response.send_message("⛔ You must be verified to vouch.", ephemeral=True)
        return

    if not has_vouch_permission(interaction.user):
        await interaction.response.send_message("⛔ You do not have permission to vouch.", ephemeral=True)
        return

    if interaction.channel.id != VOUCH_CHANNEL_ID:
        await interaction.response.send_message("⛔ Vouches can only be given in the designated channel.", ephemeral=True)
        return

    if interaction.user.id == member.id:
        await interaction.response.send_message("⛔ You cannot vouch for yourself!", ephemeral=True)
        return

    cursor.execute("SELECT last_vouch FROM vouches WHERE user_id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    if result and result[0]:
        last_vouch_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_vouch_time < timedelta(hours=COOLDOWN_TIME):
            await interaction.response.send_message("⏳ You need to wait before vouching again.", ephemeral=True)
            return

    cursor.execute("INSERT INTO vouches (user_id, vouches, last_vouch) VALUES (?, 1, ?) "
                   "ON CONFLICT(user_id) DO UPDATE SET vouches = vouches + 1, last_vouch = ?",
                   (member.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

    cursor.execute("SELECT vouches FROM vouches WHERE user_id = ?", (member.id,))
    vouch_count = cursor.fetchone()[0]
    new_tier = "Newbie"
    for count, tier in REPUTATION_TIERS.items():
        if vouch_count >= count:
            new_tier = tier

    cursor.execute("UPDATE vouches SET reputation_tier = ? WHERE user_id = ?", (new_tier, member.id))
    conn.commit()

    await interaction.response.send_message(f"✅ {interaction.user.mention} vouched for {member.mention}! They now have `{vouch_count}` vouches and are `{new_tier}` tier.")

@bot.tree.command()
async def vouch_leaderboard(interaction: discord.Interaction):
    """Displays the top 10 users with the most vouches"""
    cursor.execute("SELECT user_id, vouches FROM vouches ORDER BY vouches DESC LIMIT 10")
    top_users = cursor.fetchall()

    if not top_users:
        await interaction.response.send_message("📊 No vouches recorded yet.")
        return

    leaderboard = "\n".join([f"<@{user_id}> - `{vouches}` vouches" for user_id, vouches in top_users])
    embed = discord.Embed(title="🏆 Vouch Leaderboard", description=leaderboard, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()
    threading.Thread(target=run_dashboard).start()  # Start Flask web dashboard in the background

# ✅ Ensure Flask app runs for Render
if __name__ == "__main__":
    run_dashboard()

import os

import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Get token from Render

if not TOKEN:
    raise ValueError("⚠️ DISCORD_BOT_TOKEN is missing. Set it in Render environment variables.")

bot.run(TOKEN)



