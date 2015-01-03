#!/usr/bin/env python
# -*- coding: utf-8 -*-

# RTB 2014-01-03 Rewrite for Webhooks
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

from BaseHTTPServer import BaseHTTPRequestHandler
import cgi
from SocketServer import ThreadingMixIn

from chameleon.zpt.loader import TemplateLoader
from pyslack import SlackClient
from BotInfo import botData
from operator import itemgetter

class Thread(threading.Thread):
    def __init__(self, t, *args):
        threading.Thread.__init__(self, target=t, args=args)
        self.start()

lock = threading.Lock()

# based on http://pymotw.com/2/BaseHTTPServer/

class PostHandler(BaseHTTPRequestHandler):
    
    def do_POST(self):
    	global rtm
        form = cgi.FieldStorage(
            fp=self.rfile, 
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        self.send_response(200)
        self.end_headers()

	# Send it onto our parser
	rtm      = SlackRTM(False) # Init without socket
	response = rtm.parse(form)
	if len(response) > 0:
		self.wfile.write(response)
	return


class SlackRTM(object):

	# Messages we understand and parse
	hooks = {
		"markets" : "^\.markets",
		"melotic" : "^\.melotic",
		"poloniex" : "^\.poloniex",
		"balance" : "^\.balance ([A-Za-z0-9]{25,36})$",
		"twitter" : "^\.twitter ([\w]+)$",
		"undo" : "^\.undo",
		"regen" : "^\.regen"
	}
	
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
			
		# Compile regex triggers
		self.triggers = {}
		for key, val in self.hooks.iteritems():
			self.triggers[key] = re.compile(val)


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
			                },
			                "admins": []
				}
		return 0


	def SaveJson(self):
		global lock
		with lock:
			with open(botData.status_file, 'w') as status_out:
				json.dump(self.botJson, status_out)
				status_out.close()
		return 0

			
	def Parse(self, form):
		# Turn it into json
		jsonData = {}
		for field in form.keys():
			jsonData[field] = form[field].value.strip()
			
		# Verify Token
		if jsonData['token'] != botData.hook_token:
			return "Token from Slack does not match ours, ignoring."
			
		for key, val in self.triggers.iteritems():
			test = self.triggers[key].match(jsonData['text'])
			if test:
				self._Process(re.findall(self.triggers[key], jsonData['text']), jsonData)

			
	def _Process(self, matchData, jsonData):
		response = ""

		# Ok, lets go through our list...
		if len(matchData) == 1:
			# Pretty simple
			k = matchData[0]
			if k == ".markets":
				response  = "Melotic SJCX/BTC: " + str(self.GetExRate("melotic")) + "\n"
				response += "Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex"))
			elif k == ".melotic":
				response  = "Melotic SJCX/BTC: " + str(self.GetExRate("melotic"))
			elif k == ".poloniex":
				response  = "Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex"))
			elif k == ".undo":
				self.SetupJson()
				self.botJson['updates'][jsonData['user_id']] = self.botJson['undo'][jsonData['user_id']]
				self.SaveJson()
				self.OutputTemplate()
				response = "<@" + jsonData['user_id'] + ">: I have undone your last update and refreshed the template."
			elif k == ".regen":
				self.SetupJson()
				self.OutputTemplate()
				response = "<@" + jsonData['user_id'] + ">: I have refreshed the template."
			
			if len(response) > 0:
				return response
			else:
				return "No response to give!"
				
		elif len(matchData) == 2:
			# Two arguments, ok! Balance or twitter.
			k = matchData[0]
			v = matchData[1]
			
			if k == ".balance":
				balance = str(self.GetBalance(v))
				response = "Balance for address " + v + ": " + balance + " SJCX"
			elif k == ".twitter":
				self.SetupJson()
				self.botJson['twitter'][jsonData['user_if']] = v
				self.SaveJson()
				response = "<@" + jsonData['user_id'] + ">: Your twitter handle is now '" + v + "'."
				
			if len(response) > 0:
				return response
			else:
				return "No response to give!"

		else:
			return "No response to give!"
							
			
	def IsAdmin(self, user):
		self.SetupJson()
		if user in self.botJson['admins']:
			return True
		else:
			return False
		
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



