from discord.ext import commands, tasks
from datetime import datetime
from dataclasses import dataclass
from textwrap import wrap

import imaplib
import email
import discord
import os

from email.header import decode_header

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = 1391742724666822798
MAX_SESSION_TIME_MINUTES = 2
CHECK_EMAIL_WAIT = 2
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
imap_server = "imap.migadu.com"
smtp_server = "smtp.migadu.com"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event 
async def on_ready():
    print("Hello bot ready")
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send("Activated at " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@tasks.loop(minutes=CHECK_EMAIL_WAIT)
async def task_poll_inbox():

    channel = bot.get_channel(CHANNEL_ID)
    print(f"Reading inbox of {EMAIL_USERNAME}")

    # create an IMAP4 class with SSL and authenticate
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(EMAIL_USERNAME, EMAIL_PASSWORD)

    status, messages = mail.select("INBOX")
    # get unseen messages
    (retcode, messages) = mail.search(None, '(UNSEEN)')
    if retcode == 'OK':
        for idx, num in enumerate(messages[0].split()):
            typ, data = mail.fetch(num,'(RFC822)')
            for response_part in data:
                if isinstance(response_part, tuple):
                    original = email.message_from_string(response_part[1].decode('utf-8'))
                    received = original['Received']
                    received = received.split(";")[-1]

                    print(original['From'])
                    print(original['Subject'])
                    print(f"Received: {received}")
                    await channel.send(f"{"=" * 30} Message {idx+1} of {str(len(messages[0].split()))} {"=" * 30}")
                    await channel.send(f"**FROM:** {original['From']}\n**SUBJECT:** {original['Subject']} \n**RECEIVED:** {received}")
                    if original.is_multipart():
                        # iterate over email parts
                        for part in original.walk():
                            # extract content type of email
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            try:
                                # get the email body
                                body = part.get_payload(decode=True).decode()
                            except:
                                pass
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                # print text/plain emails and skip attachments
                                print(wrap(body, width=3900))
                                await channel.send("**BODY**:")
                                for line in wrap(body, width=3900):
                                    await channel.send(line)
                            elif "attachment" in content_disposition:
                                # download attachment
                                print("attachment case")
                    else:
                        # extract content type of email
                        content_type = original.get_content_type()
                        # get the email body
                        body = original.get_payload(decode=True).decode()
                        if content_type == "text/plain":
                            # print only text email parts
                            print(body)
                            await channel.send("**BODY**:")
                            for line in wrap(body, width=3900):
                                await channel.send(line)
                        if content_type == "text/html":
                            print("html case")  
                    print("="*100)
                    await channel.send("="*71)

                    # mark the mail as seen so it doesn't come up again
                    typ, data = mail.store(num,'+FLAGS','\\Seen')

    print("Login complete, # of new messages: " + str(len(messages[0].split())))
   
    # close the connection and logout
    mail.close()
    mail.logout()
    print("end of this iteration")

@bot.command()
async def st(ctx):
    task_poll_inbox.start()
    await ctx.send(f"Polling for emails every {CHECK_EMAIL_WAIT} minutes")

@bot.command()
async def is_running(ctx):
    await ctx.send(f"Inbox polling task *{'is' if task_poll_inbox.is_running() else 'isn\'t'}* running")

bot.run(BOT_TOKEN)