#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Storj Bot for Slack (with other functions)

# Imports
import os
import sys
import time
import threading
import json

from SlackCore import SlackInteractor
from SlackCore import SlackRTM
from BotInfo import botData

reload(sys)
sys.setdefaultencoding("utf-8")

def RTMRunner():
	rtm    = SlackRTM()
	while True:
		rtm.ActivityCheck()

def ClientRunner():
	client = SlackInteractor()
	client.SetupJson()
	client.CheckMessages(100)
	client.SaveJson()
	while True:
		if client.CheckMessages(10) > 0:
			client.SaveJson()
			print "Time to output new template..."
			client.OutputTemplate()
			client.newEntries = 0
			time.sleep(30)
		else:
			# print "No new template needed."
			client.CheckRefresh()
			time.sleep(10)

def doTemplate():
	client = SlackInteractor()
	client.SetupJson()
	print "Outputting new template..."
	client.OutputTemplate()
	print "... done."
	sys.exit()

def doRun():
	print "Starting SlackBot..."
	a = threading.Thread(target=ClientRunner)
	a.daemon=True
	a.start()

	time.sleep(5)

	b = threading.Thread(target=RTMRunner)
	b.daemon=True
	b.start()

	while True:
		time.sleep(1) # Do nothing

def doDump():
	status_in = open(botData.status_file, "r")
	botJson   = json.load(status_in)
	status_in.close()

	print json.dumps(botJson, indent=4)

def doTest():
	print "Testing..."
	rtm    = SlackRTM(False)
	data = {
		'type': 'message',
		'text': '.undo',
		'user': 'U02FSFYNG'
	}
	print rtm.MessageParser(data)

	
args = len(sys.argv)
if args > 1:
	arg = sys.argv[1]
	if arg == "template":
		doTemplate()
	elif arg == "dump":
		doDump()
	elif arg == "test":
		doTest()
	else:
		doRun()
else:
	doRun()
	
'''

U02FSFYNG

'''

