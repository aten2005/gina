import discord
from discord.ext import commands
from lib.taskmanager import ComposioAgent
from dotenv import load_dotenv
import json
import os


load_dotenv()
# msg_cache=[]

def load_db():
    with open("db.json","r") as f:
        user_database=json.load(f)
        return user_database
    
def save_db(curr_database):
    with open("db.json","w") as f:
        json.dump(curr_database,f)

user_database = load_db()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix=None, intents=intents)
# Dictionary to store user-specific ComposioAgent instances
user_agents = {}

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # if len(msg_cache)<20:
    #     msg_cache.append([message.author.name,message.content])
    # else:
    #     msg_cache.pop(0)
    #     msg_cache.append([message.author.name,message.content])
    # print(msg_cache)

    if bot.user.mentioned_in(message):
        command = message.content.replace(f"@{bot.user.name}", "").strip()
        user_id = str(message.author.id)
        discord_channel = message.channel
        
        # Check if the user is in the mock database
        if user_id not in user_database:
            #Create new account
            entity_id = "gina_"+user_id
            user_database[user_id] = entity_id
            save_db(user_database)
            embed = discord.Embed(description="Check private message for instructions", color=0x00FF00)
            await discord_channel.send(embed=embed)
        else:
            entity_id = str(user_database[user_id])

        # Proceed with ComposioAgent
        if entity_id not in user_agents:
            user_agents[entity_id] = ComposioAgent(entity_id, discord_channel, bot=bot)

        agent = user_agents[entity_id]
        if not await agent.connect(message.author):
            embed = discord.Embed(title="Connection Failed", description="Failed to connect to Composio services.", color=0xFF0000)
            await message.reply(embed=embed)
            return

        if res := await agent.doTask(command):
            await message.reply(res)
        else:
            embed = discord.Embed(title="Task Failed", description="Failed to complete the task.", color=0xFF0000)
            await message.reply(embed=embed)
            
bot.run(os.environ["DISCORD_BOT_TOKEN"])