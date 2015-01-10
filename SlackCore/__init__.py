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
from datetime import date

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

		rtm      = SlackResponder(False) # Init without socket
		response = rtm.Parse(jsonData)
		logger.debug(response)
		self.wfile.write(json.dumps({"text": response}))
		return

	def finish(self):
		if not self.wfile.closed:
			self.wfile.flush()
		self.wfile.close()
		self.rfile.close()


class SlackResponder(object):

	# Messages we understand and parse
	hooks = {
		"status" : 	"^(\.status) (.*)$",
		"balance" :	"^(\.balance) ([A-Za-z0-9]{25,36})$",
		"twitter" : 	"^(\.twitter) ([\w]+)$",
		"add":    	"^(\.add) \<\@([\w]+)\> ?(admin|superuser)?",
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
	
	# User ability level
	userLevel = {
		"none": 0,
		"user": 1,
		"superuser": 2
		"owner": 3
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
				"undo": {},
			        "admins": [botData.owner_id],
			        "superusers": [botData.owner_id],
			        "hidden": []
			}
		return 0
		

	def SaveJson(self):
		with open(botData.status_file, 'w') as status_out:
			json.dump(self.botJson, status_out)
			status_out.close()
		return 0


	def PromoteUser(self, user=userJson, subject=argument, level=userLevel):
		''' Promotes a user to a higher level so they can post updates, or at
		superuser level they can promote other users to update posting level.
		:param user: json dict representing the user data
		:param subject: The user to act on
		:param level: int user level to promote to, 1=user, 2=superuser
		:return: String to send back to the user.
		'''
			
	def DemoteUser(self, data=userJson, subject=argument, hide=False):
		''' Demotes a user so they won't be allowed to post updates. Optional hide posts.
		Doesn't matter what level they are, they're gone.
		:param subject: The user to act upon
		:param hide: Bool to hide posts by the user at the same time
		:return: String to send back to the user
		'''
		
	def HideUserPosts(self, user=userJson, subject=argument):
		''' Hide posts by a user, refreshes template without that users posts.
		:param user: json dict representing the user data
		:param subject: The user to act upon
		:return: String to send back to the user
		''' 
	
	def ShowUserPosts(self, user=userJson, subject=argument):
		''' Show posts by a user, refreshes template with that users posts.
		:param user: json dict representing the user data
		:param subject: The user to act upon
		:return: String to send back to the user
		'''
		
	def PostStatusUpdate(self, user=userJson, text=argument):
		''' Creates a status update for a user, refreshes template.
		:param user: json dict representing the user data
		:param text: The status text the user wishes to post
		:return: String to send back to the user
		'''


			
	def Parse(self, jsonData):
		logger = logging.getLogger("SlackBot")

		# Verify Token
		if jsonData['token'] != botData.hook_token:
			logger.debug("Token from Slack does not match ours, ignoring.")
			return
			
		logger.debug("Looking through hooks for a match...")
		for key, val in self.triggers.iteritems():
			test = self.triggers[key].match(jsonData['text'])
			if test:
				logger.debug("Got a match with: " + self.hooks[key])
				return self._Process(re.findall(self.triggers[key], jsonData['text']), jsonData)
		# Still here?
		return "Huh?"

			
	def _Process(self, matchData, jsonData):
		logger = logging.getLogger("SlackBot")
		self.SetupJson() # Read it in now just in case

		# Clear out some old data
		try:
			del jsonData['token'], jsonData['trigger_word'], jsonData['team_id']
			del jsonData['channel_name'], jsonData['user_name']
		except:
			pass

		if jsonData['user_id'] == botData.owner_id:
			uLevel = this.userLevel['owner'] # 3
		elif jsonData['user_id'] in self.botJson['superusers']:
			uLevel = this.userLevel['superuser'] # 2
		elif jsonData['user_id'] in self.botJson['admins']:
			uLevel = this.userLevel['user'] # 1
		else:
			uLevel = this.userLevel['none'] # 0
		
		request = matchData[0]
		
		# k = matchData[0]
		# Is it a multi-item index? i.e. two values
		if not isinstance(request, basestring):
			if len(request) == 2:
				trigger  = request[0]
				argument = request[1]
				# Third value for a user class (for .add)
				if trigger == ".add":
					try:
						userClass = k[2]
					except:
						userClass = ""
				
				if trigger == ".balance":
					balance = 
					return "Balance for address " + argument + ": " + str(self.GetBalance(argument)) + " SJCX"
				elif trigger == ".twitter":
					self.SetupJson()
					self.botJson['twitter'][jsonData['user_id']] = argument
					self.SaveJson()
					return "<@" + jsonData['user_id'] + ">: Your twitter handle is now '" + argument + "'."
				elif trigger == ".status" or trigger == ".add" or trigger == ".del" or trigger == ".show" or trigger == ".hide":
					if uLevel == 0:
						return "<@" + jsonData['user_id'] + ">: You are not an authorised user."
					# Status update?
					if trigger == ".status":
						self.SetupJson()
						self.updateStatus(matchData, jsonData)
						self.SaveJson()
						self.outputTemplate()
						return "<@" + jsonData['user_id'] + ">: Status update accepted, template updated."

					# Is the owner trying to be added or deleted?
					if trigger == ".add" or trigger == ".del":
						if str(argument) == str(botData.owner_id):
							return "<@" + jsonData['user_id'] + ">: Cannot perform actions on bot owner."
						self.SetupJson()
						if trigger == ".add":
							if userClass == "superusers":
								if isOwner == True:
									if argument in jsonData['superusers']:
										return "<@" + jsonData['user_id'] + ">: Action not needed."
									self.botJson['superusers'].append(argument)
									self.SaveJson()
									return "<@" + jsonData['user_id'] + ">: User <@" + argument + "> added to superusers."
								else:
									return "<@" + jsonData['user_id'] + ">: You are not authorised to add other superusers."
							else:
								if isSuper == True:
									if argument in jsonData['admins']:
										return "<@" + jsonData['user_id'] + ">: Action not needed."
									self.botJson['admins'].append(argument)
									self.SaveJson()
									return "<@" + jsonData['user_id'] + ">: User <@" + argument + "> added to authorised users."
								else:
									return "<@" + jsonData['user_id'] + ">: You are not authorised to add other users."
						elif trigger == ".del": # Removes from either list
							if argument in jsonData['admins']:
								self.botJson['admins'].remove(argument)
								self.SaveJson()
								return "<@" + jsonData['user_id'] + ">: User <@" + argument + "> removed."
							elif argument in jsonData['superusers']:
								self.botJson['superusers'].remove(argument)
								self.SaveJson()
								return "<@" + jsonData['user_id'] + ">: User <@" + argument + "> removed."
							else:
								return "<@" + jsonData['user_id'] + ">: Action not needed."

					elif trigger == ".show" or trigger == ".hide":
						if isAdmin == True:
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

# Processing

# userJson
# botJson


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
			# Is this a hidden post?
			if self.botJson['updates'][key]['user'] in self.botJson['hidden']:
				continue
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

			pt_loader = TemplateLoader(['html/'], auto_reload=True)
			template  = pt_loader.load('index.template')
			with open(botData.output_file, 'w') as template_out:
				template_out.write(template(users=tdata))
				template_out.close()


# Backup System
class SlackBackup(object):
	def __init__(self):
		if botData.backup_path == "":
			return # No Need
		bPath = botData.backup_path
		if bPath[-1] == "/": # Is there a trailing slash?
			bPath = bPath[:-1]
			
		t = date.today()
		suffix = t.strftime("%Y-%m-%d")
		backupFile = bPath + "/" + botData.status_file + "." + suffix
		
		if os.path.isfile(backupFile): # Does it exist already?
			return
			
		fileIn  = open(botData.status_file, "r")
		fileOut = open(backupFile, "w")
		goIn = fileIn.read()
		fileOut.write(goIn)
		fileIn.close()
		fileOut.close()
		
		# All done!
		
		
		
		
		
		
		
		
	



