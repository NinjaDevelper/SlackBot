#!/usr/bin/env python
# -*- coding: utf-8 -*-

# RTB 2014-01-03 Rewrite for Webhooks
# Storj Bot Core Classes

# Imports
import os, sys, traceback, json, time, re, logging, ssl
import websocket, requests, datetime, cgi

from BaseHTTPServer import BaseHTTPRequestHandler
import SocketServer

from chameleon.zpt.loader import TemplateLoader
from pyslack import SlackClient
from BotInfo import botData
from operator import itemgetter

class PostHandler(BaseHTTPRequestHandler):

	def setup(self):
		self.connection = self.request
		self.rfile = self.connection.makefile('rb', self.rbufsize)
		self.wfile = self.connection.makefile('wb', self.wbufsize)
        
	def do_POST(self):
		reqvars = ['token', 'team_id', 'channel_id', 'channel_name',
			   'timestamp', 'user_id', 'user_name', 'text',
			   'trigger_word']

		try:
			logger = logging.getLogger("SlackBot")
			logger.debug("Got POST data...")
			form = cgi.FieldStorage(
			    fp=self.rfile, 
			    headers=self.headers,
			    environ={'REQUEST_METHOD':'POST',
				     'CONTENT_TYPE':self.headers['Content-Type'],
				     })

			self.send_response(200)
			self.send_header("Content-type", "text/html")
			self.end_headers()
		except:
			traceback.print_exc(file=sys.stdout)
			
		# Test we got everything
		jsonData = {}
		for field in form.keys():
			jsonData[field] = form[field].value.strip()
		
		for idx, val in enumerate(reqvars):
			if val not in jsonData:
				response = "Incorrect data. Please try again!"
				self.wfile.write(response)
				return

		rtm      = SlackRTM(False) # Init without socket
		response = rtm.Parse(jsonData)
		logger.debug(response)
		self.wfile.write(json.dumps({"text": response}))
		return

	def finish(self):
		if not self.wfile.closed:
			self.wfile.flush()
		self.wfile.close()
		self.rfile.close()


class SlackRTM(object):

	# Messages we understand and parse
	hooks = {
		"status" : 	"^(\.status) (.*)$",
		"balance" :	"^(\.balance) ([A-Za-z0-9]{25,36})$",
		"twitter" : 	"^(\.twitter) ([\w]+)$",
		"add":    	"^(\.add) \<\@([\w]+)\>",
		"del":		"^(\.del) \<\@([\w]+)\>",
		"hide":		"^(\.hide) \<\@([\w]+)\>",
		"show":		"^(\.show) \<\@([\w]+)\>",
		"list":		"^\.list",
		"markets" :	"^\.markets",
		"melotic" :	"^\.melotic",
		"poloniex" :	"^\.poloniex",
		"alts" : 	"^\.alts",
		"undo" : 	"^\.undo",
		"regen" :  	"^\.regen"
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
			        "admins": [],
			        "hidden": []
			}
		return 0
		

	def SaveJson(self):
		with open(botData.status_file, 'w') as status_out:
			json.dump(self.botJson, status_out)
			status_out.close()
		return 0

			
	def Parse(self, jsonData):
		logger = logging.getLogger("SlackBot")

		# Verify Token
		if jsonData['token'] != botData.hook_token:
			return "Token from Slack does not match ours, ignoring."
			
		logger.debug("Looking through hooks for a match...")
		for key, val in self.triggers.iteritems():
			test = self.triggers[key].match(jsonData['text'])
			if test:
				logger.debug("Got a match with: " + self.hooks[key])
				return self._Process(re.findall(self.triggers[key], jsonData['text']), jsonData)

			
	def _Process(self, matchData, jsonData):
		logger = logging.getLogger("SlackBot")

		# Clear out some old data
		try:
			del jsonData['token']
			del jsonData['trigger_word']
			del jsonData['team_id']
			del jsonData['channel_name']
			del jsonData['user_name']
		except:
			pass
		
		isOwner = False
		isAdmin = False
		
		if self.IsAdmin(jsonData['user_id']) == True:
			isAdmin = True
		if jsonData['user_id'] == botData.owner_id:
			isOwner = True
		
		k = matchData[0]
		# Is it a multi-item index? i.e. two values
		if not isinstance(k, basestring):
			if len(k) == 2:
				trigger  = k[0]
				argument = k[1]
			
			if trigger == ".balance":
				balance = str(self.GetBalance(argument))
				return "Balance for address " + v + ": " + balance + " SJCX"
			elif trigger == ".twitter":
				self.SetupJson()
				self.botJson['twitter'][jsonData['user_id']] = argument
				self.SaveJson()
				return "<@" + jsonData['user_id'] + ">: Your twitter handle is now '" + argument + "'."
			elif trigger == ".status":
				self.SetupJson()
				self.updateStatus(matchData, jsonData)
				self.SaveJson()
				self.outputTemplate()
				return "<@" + jsonData['user_id'] + ">: Status update accepted, template updated."
			elif trigger == ".add" or trigger == ".del" or trigger == ".show" or trigger == ".hide":
				if isAdmin == False and isOwner == False:
					return "<@" + jsonData['user_id'] + ">: You are not a registered bot user."
				# Is the owner trying to be added or deleted?
				if trigger == ".add" or trigger == ".del":
					if str(argument) == str(botData.owner_id):
						return "<@" + jsonData['user_id'] + ">: Cannot perform actions on bot owner."
					self.SetupJson()
					if trigger == ".add":
						if argument in jsonData['admins']:
							return "<@" + jsonData['user_id'] + ">: Action not needed."
						self.botJson['admins'].append(argument)
						self.SaveJson()
						return "<@" + jsonData['user_id'] + ">: User <@" + argument + "> added."
					elif trigger == ".del":
						if argument not in jsonData['admins']:
							return "<@" + jsonData['user_id'] + ">: Action not needed."
						self.botJson['admins'].remove(argument)
						self.SaveJson()
						return "<@" + jsonData['user_id'] + ">: User <@" + argument + "> removed."
				elif trigger == ".show" or trigger == ".hide":
					self.SetupJson()
					if trigger == ".hide":
						if argument in jsonData['hidden']:
							return "<@" + jsonData['user_id'] + ">: Action not needed."
						self.botJson['hidden'].append(argument)
						self.SaveJson()
						self.outputTemplate()
						return "<@" + jsonData['user_id'] + ">: Posts by <@" + argument + "> are now hidden.\nTemplate refreshed."
					if trigger == ".show":
						if argument not in jsonData['hidden']:
							return "<@" + jsonData['user_id'] + ">: Action not needed."
						self.botJson['hidden'].remove(argument)
						self.SaveJson()
						self.outputTemplate()
						return "<@" + jsonData['user_id'] + ">: Updates by <@" + argument + "> are now seen.\nTemplate refreshed."
			else:
				return "No response to give!"
		elif k == ".list":
			admins = []
			for k in jsonData['admins']:
				admins.append("<@" + k + ">")
			final = ", ".join(admins)
			return "Approved posters: " + final
		elif k == ".markets":
			response  = "Melotic SJCX/BTC: " + str(self.GetExRate("melotic")) + "\n"
			response += "Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex")) + "\n"
			response += "Alts.trade SJCX/BTC: " + str(self.GetExRate("alts"))
			return response
		elif k == ".melotic":
			return "Melotic SJCX/BTC: " + str(self.GetExRate("melotic"))
		elif k == ".poloniex":
			return "Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex"))
		elif k == ".alts":
			return "Alts.trade SJCX/BTC: " + str(self.GetExRate("alts"))
		elif k == ".undo":
			self.SetupJson()
			self.botJson['updates'][jsonData['user_id']] = self.botJson['undo'][jsonData['user_id']]
			self.SaveJson()
			self.OutputTemplate()
			response = "<@" + jsonData['user_id'] + ">: I have undone your last update and refreshed the template."
			return response
		elif k == ".regen":
			self.SetupJson()
			self.OutputTemplate()
			return "<@" + jsonData['user_id'] + ">: I have refreshed the template."
		else:
			return "No response to give!"


	def GetUser(self, user_id):
		req = self.client._make_request('users.info', {'user': user_id})
		self.botJson['users'][req['user']['id']] = req['user']
		return True

			
	def AddStatusPost(self, matchData, jsonData):
		# Here jsonData has been passed from the parser
		self.botJson['last_match'] = jsonData
		jsonData['text'] = matchData[0][1] # Only the last part
		if jsonData['user_id'] in self.botJson['updates']:		
			try:
				test = self.botJson['users'][jsonData['user_id']]
			except:
				self.GetUser(jsonData['user_id'])
				time.sleep(botData.sleep_time)
			if jsonData['user_id'] in self.botJson['undo']:
				old = self.botJson['updates'][jsonData['user_id']]
				self.botJson['undo'][jsonData['user_id']] = old # Copy before replace
				self.botJson['updates'][jsonData['user_id']] = jsonData # Update this user with latest post
			else:
				self.botJson['undo'][m['user']] = jsonData # Set them both to the same to start
				self.botJson['updates'][m['user']] = jsonData
							
			
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
		elif exchange == "alts":
			rate = requests.get("https://alts.trade/rest_api/ticker/SJCX/BTC", verify=False).json()
			return rate['result']['last']
		

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


