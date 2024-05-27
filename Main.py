import aiosqlite

import discord
from discord.ext import commands, tasks

import os
import re
import json
import asyncio

import numpy as np
from PIL import Image
from io import BytesIO

import aiohttp
import tensorflow
from keras.models import load_model


TOKEN = "BOT TOKEN"

SETTINGS_FILE = "Settings.txt"

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="+", intents=intents)
bot.remove_command("help")

loaded_model = load_model("model.h5", compile=False)


with open("classes.json", "r") as f:
    classes = json.load(f)

with open("pokemon", "r", encoding="utf8") as file:
    pokemon_list = file.read()


@bot.event
async def on_ready():

    await bot.change_presence(status=discord.Status.online)
    print("------- Logged In As : {0.user}".format(bot))
    bot.db = await aiosqlite.connect("pokemon.db")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS pokies (command str)")
    print("------- Pokemon Table Created -------")
    print("------- Model Loaded ----------------")
    await bot.db.commit()


class MyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=30)
        button = discord.ui.Button(
            label="Invite The BOT",
            style=discord.ButtonStyle.url,
            url="https://discord.com/api/oauth2/authorize?client_id=1068062135772528690&permissions=8&scope=bot",
        )
        self.add_item(button)


class Settings(discord.ui.View):

    @discord.ui.button(
        label="Enable AutoHint",
        style=discord.ButtonStyle.green,
        custom_id="enable_autohint",
    )
    async def enable_autohint(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):

        await interaction.message.delete()
        await enableautohint(interaction)

    @discord.ui.button(
        label="Disable AutoHint",
        style=discord.ButtonStyle.red,
        custom_id="disable_autohint",
    )
    async def disable_autohint(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):

        await interaction.message.delete()
        await disableautohint(interaction)


def solve(message):
    hint = []
    for i in range(15, len(message) - 1):
        if message[i] != "\\":
            hint.append(message[i])
    hint_string = ""
    for i in hint:
        hint_string += i
    hint_replaced = hint_string.replace("_", ".")
    return re.findall("^" + hint_replaced + "$", pokemon_list, re.MULTILINE)


def get_target_servers():
    try:
        with open(SETTINGS_FILE, "r") as file:
            servers = [int(line.strip()) for line in file.readlines()]
        return servers
    except FileNotFoundError:
        return []


def add_server_id(server_id):
    servers = get_target_servers()
    if server_id not in servers:
        servers.append(server_id)
        with open(SETTINGS_FILE, "w") as file:
            file.write("\n".join(map(str, servers)))


def remove_server_id(server_id):
    servers = get_target_servers()
    if server_id in servers:
        servers.remove(server_id)
        with open(SETTINGS_FILE, "w") as file:
            file.write("\n".join(map(str, servers)))


async def preprocess_image(image):
    image = image.resize((64, 64))
    image = np.array(image)
    image = image / 255.0
    image = np.expand_dims(image, axis=0)
    return image


async def create_embed(name, confidence):
    embed = discord.Embed(
        title=f"Pokemon : {name}",
        description=f"Confidence : {confidence:.2f} %",
    )
    return embed


async def identify(message: discord.Message):
    c = await bot.loop.run_in_executor(None, solve, message.content)
    ch = message.channel
    if not len(c):

        embed = discord.Embed(title="Couldn't Find The Pokemon")
        await message.channel.send(embed=embed)

    else:
        for i in c:

            confidence = "100"

            embed = await create_embed(i.capitalize(), confidence)
            await message.channel.send(embed=embed, view=MyView())


async def enableautohint(interaction):

    server_id = interaction.guild.id

    if server_id not in get_target_servers():
        add_server_id(server_id)

        embed = discord.Embed(
            title="AutoHint Enabled", description="AutoHint Enabled For The Server"
        )

        await interaction.response.send_message(embed=embed)

    else:

        embed = discord.Embed(
            title="Error", description="AutoHint Is Already Enabled In The Server"
        )

        await interaction.response.send_message(embed=embed)


async def disableautohint(interaction):

    server_id = interaction.guild.id

    if server_id not in get_target_servers():
        add_server_id(server_id)

        embed = discord.Embed(
            title="AutoHint Disabled", description="AutoHint Disabled For The Server"
        )

        await interaction.response.send_message(embed=embed)

    else:
        embed = discord.Embed(
            title="Error", description="AutoHint Is Already Disabled In The Server"
        )

        await interaction.response.send_message(embed=embed)


@bot.event
async def on_message(message):

    while not hasattr(bot, "db"):
        await asyncio.sleep(1.0)

    channel = message.channel

    if message.guild.id not in get_target_servers():
        if message.author.id == 716390085896962058:
            if len(message.embeds) > 0:
                embed = message.embeds[0]
                if "appeared!" in embed.title:

                    cur = await bot.db.execute("SELECT command from pokies")
                    res = await cur.fetchone()
                    if res is None or res[0] != "hold":
                        if embed.image:
                            url = embed.image.url
                            async with aiohttp.ClientSession() as session:
                                async with session.get(url=url) as resp:
                                    if resp.status == 200:
                                        content = await resp.read()
                                        image_data = BytesIO(content)
                                        image = Image.open(image_data)
                            preprocessed_image = await preprocess_image(image)
                            predictions = loaded_model.predict(preprocessed_image)
                            confidence = np.max(predictions) * 100
                            classes_x = np.argmax(predictions, axis=1)
                            name = list(classes.keys())[classes_x[0]]
                            embed = await create_embed(name.capitalize(), confidence)
                            await message.channel.send(embed=embed, view=MyView())

        elif "wrong" in message.content:
            await asyncio.sleep(1)
            embed = discord.Embed(
                title="Pokemon Name Error",
                description="Please Use <@!716390085896962058> Hint",
            )
            await message.channel.send(embed=embed)

        elif "The pokémon is" in message.content:
            await asyncio.sleep(1)
            await identify(message)

        elif "Ouch" in message.content:
            await message.delete()
            async with message.channel.typing():
                await asyncio.sleep(2.0)

            await message.channel.send("Stopped Auto Hinting")
            cur = await bot.db.execute("SELECT command from pokies")
            res = await cur.fetchone()
            if res is None:
                await bot.db.execute(
                    "INSERT OR IGNORE INTO pokies (command) VALUES (?)", ("hold",)
                )
            else:
                await bot.db.execute("UPDATE pokies SET command = ?", ("hold",))
            await bot.db.commit()

    await bot.process_commands(message)


@bot.command(name="settings", description="Displays Bot Settings For The Servers")
async def settings(message):

    if message.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Settings", description="Settings Of Poke Hint AI BOT"
        )
        embed.add_field(
            name="Enable Autohint", value="Enable Auto AI Hinting", inline=False
        )
        embed.add_field(
            name="Disable Autohint", value="Disable Auto AI Hinting", inline=False
        )

        await message.respond(embed=embed, view=Settings())

    else:
        embed = discord.Embed(
            title="Permission Denied",
            description="You Need Administrator Permission To Run The Command",
        )

        await message.respond(embed=embed)


@bot.command(name="predict", description="Predicts The Pokemon In The Image")
async def predict(ctx):

    message = ctx.message.reference.resolved

    if message.author.id == 716390085896962058:
        if len(message.embeds) > 0:
            embed = message.embeds[0]
            if "appeared!" in embed.title:

                cur = await bot.db.execute("SELECT command from pokies")
                res = await cur.fetchone()
                if res is None or res[0] != "hold":
                    if embed.image:
                        url = embed.image.url
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url=url) as resp:
                                if resp.status == 200:
                                    content = await resp.read()
                                    image_data = BytesIO(content)
                                    image = Image.open(image_data)

                        preprocessed_image = await preprocess_image(image)
                        predictions = loaded_model.predict(preprocessed_image)
                        confidence = np.max(predictions) * 100
                        classes_x = np.argmax(predictions, axis=1)
                        name = list(classes.keys())[classes_x[0]]

                        embed = await create_embed(name.capitalize(), confidence)
                        await message.channel.send(embed=embed)


bot.run(TOKEN)
