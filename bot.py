import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from collections import namedtuple
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
VADER = SentimentIntensityAnalyzer()
#To get sentiment for a sentence: VADER.polarity_scores(sentence)["compound"]

#Load Enviroment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN') #Identifies the user (the bot)

intents = discord.Intents.default()
intents.members = True
command_prefix = "!"
bot = commands.Bot(command_prefix=command_prefix, intents=intents)

##Global Parameters


#A dictionary mapping guilds -> dictionaries, which in turm map
# users -> (avg, pos, neg, n)
#    where: avg is the average compound sentiment of that use,r
#           pos is the total positive sentiment of that user,
#           neg is the total negative sentiment of that user, and
#           n is the number of messages sent by that user.
class SentimentTuple:
    def __init__(self,avg=0,pos=0,neg=0,n=0):
        self.avg,self.pos,self.neg,self.n=avg,pos,neg,n
    def __iter__(self):
        return iter((self.avg,self.pos,self.neg,self.n))

bot.sent_dicts = {} #this will be read from the drive during on_ready

#directory for files containing sentiment dictionaries
file_dir = "sent_dicts/"

#When a message is sent, if its sentiment is less than this, reply with the sentiment
bot.lower_bound = -1

#When a message is sent, if its sentiment is higher  than this, reply with the sentiment
bot.upper_bound = 1

##Commands

@bot.command(name="report",
             help="List the stored sentiment information for each user")
async def report_command(ctx):
    msg = "Sentiment information for each user:\n"
    for user,(avg,pos,neg,n) in bot.sent_dicts[ctx.guild].items():
        msg += (f"{user.name}:\n"
               f"\tAverage sentiment: {avg}\n"
               f"\tNumber of messages recorded: {n}\n")
    await ctx.send(msg)

@bot.command(name="shutdown",
              help="save sentiment data and disconnect the bot")
async def shutdown_command(ctx):
    print("Saving...")
    write_sent_dicts()
    print("Exiting...")
    await bot.logout()

@bot.command(name="save",
             help="save sentiment data")
async def save_command(ctx):
    print("Saving...")
    write_sent_dicts()

@bot.command(name="set-lower-bound",
             help=("When a message is sent, "
                   "if its sentiment is less than the lower bound, "
                   "the bot will reply with the sentiment."))
async def set_lower_bound_command(ctx,arg):
    try:
        bot.lower_bound = int(arg)
    except ValueError:
        await ctx.send("Error: You must provide a number to set the bound")

@bot.command(name="set-upper-bound",
             help=("When a message is sent, "
                   "if its sentiment is higher than the upper bound, "
                   "the bot will reply with the sentiment."))
async def set_upper_bound_command(ctx,arg):
    try:
        bot.upper_bound = int(arg)
    except ValueError:
        await ctx.send("Error: You must provide a number to set the bound")

##Tasks

#A task to save the sentiment dictionaries every 30min
#Not used in current version
async def save_cycle_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        write_sent_dicts()
        await asyncio.sleep(30*60)

##Events 

#What to do when you connect
@bot.event
async def on_ready():
    print("bot:\n",bot,end="\n"*2)
    print(f"{bot.user} is connected to the following guilds:")
    for guild in bot.guilds:
          print(f"\t{guild.name}(id: {guild.id})")

    #Uncomment below to enable auto-save
    #bot.loop.create_task(save_cycle_task())
    read_sent_dicts()




#Run this function every time a message is recived 
@bot.event
async def on_message(msg):
    text = msg.content
   
    #Ignore messages from yourself 
    if msg.author==bot.user:
        return
 
    #Ignore commands to this bot
    if text[:len(command_prefix)]==command_prefix:
        await bot.process_commands(msg)
        return

    #Get sentiment
    sent = VADER.polarity_scores(msg.content)
    compound, pos, neg = sent["compound"],sent["pos"],sent["neg"]

    #If this is a new user, add an entry for them
    if msg.author not in bot.sent_dicts[msg.guild]:
        bot.sent_dicts[msg.guild][msg.author] = SentimentTuple(0,0,0,0)

    #Update sentiment
    bot.sent_dicts[msg.guild][msg.author].n += 1
    bot.sent_dicts[msg.guild][msg.author].pos += pos
    bot.sent_dicts[msg.guild][msg.author].neg += neg
    n = bot.sent_dicts[msg.guild][msg.author].n
    avg = bot.sent_dicts[msg.guild][msg.author].avg
    bot.sent_dicts[msg.guild][msg.author].avg += (compound-avg)/n


    #If the sentiment exceeds bounds, comment on it
    if compound <= bot.lower_bound or compound >= bot.upper_bound:
        to_send = f"{msg.author.name}'s message has a sentiment of {compound}"
        await msg.channel.send(to_send)


def write_sent_dicts():
    for guild,sent_dict in bot.sent_dicts.items():
        with open(file_dir+str(guild.id),"w") as fp:
            for user,(avg,pos,neg,n) in sent_dict.items():
                fp.write(f"{user.id} {avg} {pos} {neg} {n}\n")

def read_sent_dicts():
    #For all sentiment dictionary files
    for fn in os.listdir(file_dir):
        #The filename is the guild id
        guild_id = int(fn)

        #Find the guild using the id
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild is None:
            print("Could not find guild w/ id",guild_id)
            continue

        bot.sent_dicts[guild] = {}
        
        #Read each dictionary entry
        with open(file_dir+fn) as fp:
            for line in fp:
                parts = line.split(" ")
                if len(parts) != 5:
                    print(f"Invalid line: \'{line}\'")
                    continue
                user_id = int(parts[0])
                avg,pos,neg,n = map(lambda x:float(x), parts[1:5])

                #Find the user using their id
                #user = discord.utils.get(guild.members+[guild.owner],id=user_id)
                user = guild.get_member(user_id)
                if user is None:
                    print("Could not find user w/ id",user_id)
                    print(guild.members)
                    continue

                #Add the dictionary entry
                bot.sent_dicts[guild][user] = SentimentTuple(avg,pos,neg,n)

    #Initialze entries for every guild not found in files
    for guild in set(bot.guilds)-bot.sent_dicts.keys():
        bot.sent_dicts[guild] = {} 
        

bot.run(TOKEN)

