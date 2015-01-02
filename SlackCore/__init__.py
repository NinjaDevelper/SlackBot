#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Storj Bot Core Classes

# Imports
import os
import sys
import traceback
import json
import time
import re
import logging
import ssl
import websocket
import requests
import datetime
import threading

from chameleon.zpt.loader import TemplateLoader
from pyslack import SlackClient
from BotInfo import botData
from operator import itemgetter

class Thread(threading.Thread):
    def __init__(self, t, *args):
        threading.Thread.__init__(self, target=t, args=args)
        self.start()

lock = threading.Lock()

class SlackRTM(object):

	# Messages we understand and parse
	updateCheck   = re.compile("^(\<\@(" + botData.user_id + ")\>\:?(.*))")
	marketsCheck  = re.compile("^\.markets$")
	meloticCheck  = re.compile("^\.melotic$")
	poloniexCheck = re.compile("^\.poloniex")
	balanceCheck  = re.compile("^\.balance ([A-Za-z0-9]{25,36})$")
	twitterCheck  = re.compile("^\.twitter ([\w]+)$")
	undoCheck     = re.compile("^\.undo")
	regenCheck    = re.compile("^\.regen")
	
	sendId = 0

	def __init__(self, connect=True):
		# Lets get set up
		botPass = {}
		if connect is True:
			self.client = SlackClient(botData.token_id)
			req         = self.client._make_request('rtm.start', {})
			socket_url  = req['url']
			self.ws     = websocket.WebSocket()
			self.ws.connect(socket_url)
		else:
			self.ws     = websocket.WebSocket()

	# These exist in SlackInteractor
	def SetupJson(self):
		global lock
		#lock = thread.allocate_lock()
		with lock:
			if os.path.isfile(botData.status_file):
				# It exists, lets read it in.
				status_in    = open(botData.status_file, "r")
				self.botJson = json.load(status_in)
				status_in.close()
			else:
				# Starting over
				self.botJson = {
				        "users": {},
				        "updates": [],
				        "twitter": {},
				        "last_match": {},
			        	"last": {
			                    "text": "",
			                    "ts": "0",
			                    "user": ""
			                }
				}
		return 0

	def SaveJson(self):
		global lock
		with lock:
			with open(botData.status_file, 'w') as status_out:
				json.dump(self.botJson, status_out)
				status_out.close()
		return 0

		
	def SendChannelMessage(self, text):
		self.sendId += 1
		print "Response: " + text
		try:
			self.ws.send(json.dumps({
				"id": self.sendId,
				"type": "message",
				"channel": botData.channel_id,
				"text": text
			}))
			return self.ws.recv()
		except:
			print "Exception in user code:"
			print '-'*60
			traceback.print_exc(file=sys.stdout)
			print '-'*60
		
	def ActivityCheck(self):
		try:
			data = self.ws.recv()
			if len(data) > 0:
				print data
				self.MessageParser(json.loads(data))
		except TypeError:
			return # Ignore these!
		except:
			return # Ignore these

	def MessageParser(self, data):
		global botPass
		if data['type'] == "message":
			try:
				updateTest   = self.updateCheck.match(data['text'])
				marketsTest  = self.marketsCheck.match(data['text'])
				meloticTest  = self.meloticCheck.match(data['text'])
				poloniexTest = self.poloniexCheck.match(data['text'])
				balanceTest  = self.balanceCheck.match(data['text'])
				twitterTest  = self.twitterCheck.match(data['text'])
				undoTest     = self.undoCheck.match(data['text'])
				regenTest    = self.regenCheck.match(data['text'])
				
				if updateTest:
					self.SendChannelMessage("<@" + data['user'] + ">: Acknowledged.")
					# Check to see if Twitter account is set.
					self.SetupJson()
					if data['user'] not in self.botJson['twitter']:
						self.SendChannelMessage("<@" + data['user'] + ">: Set your twitter handle or no templates will be updated.")
						self.SendChannelMessage("<@" + data['user'] + ">: Use .twitter <handle> .")
				elif meloticTest:
					self.SendChannelMessage("Melotic SJCX/BTC: " + str(self.GetExRate("melotic")))
				elif poloniexTest:
					self.SendChannelMessage("Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex")))
				elif marketsTest:
					self.SendChannelMessage("Melotic SJCX/BTC: " + str(self.GetExRate("melotic")))
					self.SendChannelMessage("Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex")))
				elif balanceTest:
					addr = balanceTest.group(1)
					self.SendChannelMessage("Balance for address " + addr + ": " + 
					str(self.GetBalance(addr)) + " SJCX")
				elif twitterTest:
					twitAddr = twitterTest.group(1)
					self.SetupJson()
					self.botJson['twitter'][data['user']] = twitAddr
					self.SaveJson()
					self.SendChannelMessage("<@" + data['user'] + ">: Your twitter handle is now '" + twitAddr + "'.")
				elif undoTest:
					self.SetupJson()
					print "Current update contains: " + self.botJson['updates'][data['user']]['text']
					print "Previous update contains: " + self.botJson['undo'][data['user']]['text']
					self.botJson['updates'][data['user']] = self.botJson['undo'][data['user']]
					print "Current update now contains: " + self.botJson['updates'][data['user']]['text']
					self.botJson['parseTemplate'] = True
					self.SaveJson()
					self.SendChannelMessage("<@" + data['user'] + ">: I have undone your last update and requested a template refresh.")
				elif regenTest:
					self.SetupJson()
					self.botJson['parseTemplate'] = True
					self.SaveJson()
					self.SendChannelMessage("<@" + data['user'] + ">: Template refresh requested.")				
			except:
				print "Exception in user code:"
				print '-'*60
				traceback.print_exc(file=sys.stdout)
				print '-'*60

	def GetBalance(self, address):
		test = requests.get("http://api.blockscan.com/api2?module=address&action=balance&asset=SJCX&btc_address=" + address).json()
		if test['status'] == "success":
			return test['data'][0]['balance']

	def GetExRate(self, exchange):
		if exchange == "melotic":
			rate = requests.get("https://www.melotic.com/api/markets/sjcx-btc/ticker", verify=False).json()
			return rate['latest_price']
		elif exchange == "poloniex":
			rate = requests.get("https://poloniex.com/public?command=returnTicker", verify=False).json()
			return rate['BTC_SJCX']['last']




class SlackInteractor(object):
	botJson     = {}
	newEntries  = 0
	fileMod     = 0

	def __init__(self):
		self.searchRegex = re.compile("^(\<\@" + botData.user_id + "\>\:?(.*))")
		self.client      = SlackClient(botData.token_id)
		if os.path.isfile(botData.status_file):
			self.fileMod     = time.ctime(os.path.getmtime(botData.status_file))

	def GetUser(self, user_id):
		req = self.client._make_request('users.info', {'user': user_id})
		self.botJson['users'][req['user']['id']] = req['user']
		return 0

	def GetHistory(self, count):
		return self.client._make_request('channels.history', {'channel': botData.channel_id, 'count': count})

	def SetupJson(self):
		global lock
		#lock = thread.allocate_lock()
		with lock:
			if os.path.isfile(botData.status_file):
				# It exists, lets read it in.
				status_in    = open(botData.status_file, "r")
				self.botJson = json.load(status_in)
				status_in.close()
			else:
				# Starting over
				self.botJson = {
				        "users": {},
				        "updates": [],
				        "twitter": {},
				        "last_match": {},
			        	"last": {
			                    "text": "",
			                    "ts": "0",
			                    "user": ""
			                }
				}
		return 0

	def SaveJson(self):
		global lock
		with lock:
			with open(botData.status_file, 'w') as status_out:
				json.dump(self.botJson, status_out)
				status_out.close()
		return 0

	def CheckRefresh(self):
		if 'parseTemplate' in self.botJson:
			if self.botJson['parseTemplate'] is True:
				try:
					#del self.botJson['parseTemplate']
					self.botJson['parseTemplate'] = False
				except:
					pass
				print "Generating new template..."
				self.OutputTemplate()
				self.SaveJson()

	def CheckMessages(self, count):
		if not os.path.isfile(botData.status_file):
			return # Quit out for now
		if self.fileMod != time.ctime(os.path.getmtime(botData.status_file)):
			self.SetupJson() # Refresh, its changed
		history = self.GetHistory(count)

		self.storeTs    = 0 # Latest Timestamp Stuff
		self.newEntries = 0 # Reset for run

		# Iterate through quick and see if the timestamp is newer than the one saved
		for m in history['messages']:
		        if self.storeTs == 0:
				self.storeTs = m['ts']
		        matchTest = self.searchRegex.match(m['text'])
		        if matchTest:
	        	        self.botJson['last_match'] = m
	        	        m['text'] = matchTest.group(2).strip() # Only the last part
			        if m['user'] in self.botJson['updates']:
			        	if m['ts'] <= self.botJson['updates'][m['user']]['ts']:
			                	continue
				self.newEntries += 1
                		try:
					test = self.botJson['users'][m['user']]
		                except:
		                        self.GetUser(m['user'])
		                        time.sleep(botData.sleep_time)
		                if m['user'] in self.botJson['undo']:
				        old = self.botJson['updates'][m['user']]
				        self.botJson['undo'][m['user']] = old # Copy before replace
				        self.botJson['updates'][m['user']] = m # Update this user with latest post
				else:
					self.botJson['undo'][m['user']] = m # Set them both to the same to start
					self.botJson['updates'][m['user']] = m
					

		if self.botJson['last']['ts'] < self.storeTs:
			self.botJson['last']['ts'] = self.storeTs # Update to latest timestamp
		if self.newEntries > 0:
			self.SaveJson()
			return 1
		else:
			return 0
		
	def OutputTemplate(self):
		# Two stages, the first is to order the user id by timestamp, then pull in order
		findLatest = {}
		findPosts  = {}
		
		for key, val in self.botJson['updates'].iteritems():
			findPosts[key] = self.botJson['updates'][key]['ts']
		findLatest = sorted(findPosts.items(), key=itemgetter(1), reverse=True)

		tdata = []
		for key, val in findLatest:
			if self.botJson['updates'][key]['user'] not in self.botJson['twitter']:
				dick = self.botJson['users'][self.botJson['updates'][key]['user']]['profile']['real_name']
				print "Cannot process entry for " + dick + ", does not have twitter account set up."
				# return -1 # Break out early, user does not have a twitter account set up
				continue
			twitter = "https://twitter.com/" + self.botJson['twitter'][self.botJson['updates'][key]['user']]
			tdata.append({
				"text": str(self.botJson['updates'][key]['text'].encode("utf-8")),
				"name": self.botJson['users'][self.botJson['updates'][key]['user']]['profile']['real_name'],
				"image": self.botJson['users'][self.botJson['updates'][key]['user']]['profile']['image_72'],
				"twitter": twitter,
				"email": self.botJson['users'][self.botJson['updates'][key]['user']]['profile']['email'],
				"ts": datetime.datetime.fromtimestamp(float(self.botJson['updates'][key]['ts'])).strftime('%Y-%m-%d %H:%M:%S')
			})

			pt_loader = TemplateLoader(['/var/www/html/'], auto_reload=True)
			template  = pt_loader.load('index.template')
			with open(botData.output_file, 'w') as template_out:
				template_out.write(template(users=tdata))
				template_out.close()
		
		
