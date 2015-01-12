#!/usr/bin/env python
# -*- coding: utf-8 -*-

# RTB 2014-01-03 Rewrite for Webhooks
# Storj Bot Core Classes

# Imports
import os, sys, traceback, json, simplejson, time, re, logging, ssl
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
		postData = {}
		for field in form.keys():
			postData[field] = form[field].value.strip()
		
		for idx, val in enumerate(reqvars):
			if val not in postData:
				response = "Incorrect data. Please try again!"
				self.wfile.write(response)
				return

		rtm      = SlackResponder(False) # Init without socket
		response = rtm.Parse(postData)
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
		"superuser": 2,
		"owner": 3
	}
	
	
	def __init__(self, connect=True):
		# Lets get set up
		botPass = {}
		self.client = SlackClient(botData.token_id)
		if connect is True:
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
		logger = logging.getLogger("SlackBot")
		if os.path.isfile(botData.status_file):
			# It exists, lets read it in.
			status_in = open(botData.status_file, "r")
			data      = status_in.read()
			status_in.close()
			logger.debug("Length: " + str(len(data)) + " characters.")
			self.botJson = simplejson.loads(data)
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
		return
		

	def SaveJson(self):
		with open(botData.status_file, 'w') as status_out:
			json.dump(self.botJson, status_out)
			status_out.close()
		return


	def Parse(self, postData):
		''' Parses a (should be) matching request of the bot
		: param postData: dict from the post sent to the bot from Slack
		: return: String containing response for the user:
		'''
		logger = logging.getLogger("SlackBot")
		logger.debug("User ID: " + postData['user_id'])

		# Verify Token
		if postData['token'] != botData.hook_token:
			logger.debug("Token from Slack does not match ours, ignoring.")
			return
			
		logger.debug("Looking through hooks for a match...")
		for key, val in self.triggers.iteritems():
			test = self.triggers[key].match(postData['text'])
			if test:
				logger.debug("Got a match with: " + self.hooks[key])
				return self._Process(postData, re.findall(self.triggers[key], postData['text']))
		# Still here? Very unlikely
		return "Huh?"

			
	def _Process(self, postData, matchText):
		logger = logging.getLogger("SlackBot")
		self.SetupJson()

		try:
			del postData['token'], postData['trigger_word'], postData['team_id']
			del postData['channel_name'], postData['user_name']
		except:
			pass

		if   postData['user_id'] == botData.owner_id:
			postData['uLevel'] = self.userLevel['owner'] # 3
		elif postData['user_id'] in self.botJson['superusers']:
			postData['uLevel'] = self.userLevel['superuser'] # 2
		elif postData['user_id'] in self.botJson['admins']:
			postData['uLevel'] = self.userLevel['user'] # 1
		else:
			postData['uLevel'] = self.userLevel['none'] # 0
		
		request = matchText[0]
		
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
				elif trigger == ".del":
					try:
						if k[2].lower() in ("yes", "true", "t", "1"):
							hideUser = True
						else:
							hideUser = False
					except:
						hideUser = False

				if trigger == ".balance":
					return "Balance for address " + argument + ": " + str(self.GetBalance(argument)) + " SJCX"
				elif trigger == ".twitter":
					self.SetupJson()
					self.botJson['twitter'][postData['user_id']] = argument
					self.SaveJson()
					return "<@" + jpostData['user_id'] + ">: Your twitter handle is now '" + argument + "'."
				elif trigger == ".status" or trigger == ".add" or trigger == ".del" or trigger == ".show" or trigger == ".hide":
					if postData['uLevel'] < 1:
						return "<@" + postData['user_id'] + ">: You are not an authorised user."
					# Status update?
					if trigger == ".status":
						return self.PostStatusUpdate(postData, argument)
					# Is the owner trying to be added or deleted?
					elif trigger == ".add" or trigger == ".del":
						if str(argument) == str(botData.owner_id):
							return "<@" + jsonData['user_id'] + ">: Cannot perform actions on bot owner."
						if trigger == ".add":
							return self.PromoteUser(postData, argument, userClass)
						elif trigger == ".del": # Removes from either list
							return self.DemoteUser(postData, argument, hideUser)
					elif trigger == ".show" or trigger == ".hide":
							if trigger == ".show":
								return self.ShowUserPosts(postData, argument)
							elif trigger == ".hide":
								return self.HideUserPosts(postData, argument)
				else:
					return "No response to give!"
		elif request == ".list":
			return self.AdminList(postData)
		elif request == ".markets":
			response  = "Melotic SJCX/BTC: " + str(self.GetExRate("melotic")) + "\n"
			response += "Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex")) + "\n"
			response += "Alts.trade SJCX/BTC: " + str(self.GetExRate("alts"))
			return response
		elif request == ".melotic":
			return "Melotic SJCX/BTC: " + str(self.GetExRate("melotic"))
		elif request == ".poloniex":
			return "Poloniex SJCX/BTC: " + str(self.GetExRate("poloniex"))
		elif request == ".alts":
			return "Alts.trade SJCX/BTC: " + str(self.GetExRate("alts"))
		elif request == ".undo":
			return self.UndoPost(postData)
		elif request == ".regen":
			self.OutputTemplate()
			return "<@" + postData['user_id'] + ">: I have refreshed the template."
		else:
			return "No response to give!"


	def PostStatusUpdate(self, user, text):
		''' Creates a status update for a user, refreshes template.
		:param user: json dict representing the user data
		:param text: The status text the user wishes to post
		:return: String to send back to the user
		'''
		self.SetupJson()
		user['text'] = text
		user['ts']   = user['timestamp']
		del user['timestamp']
		self.botJson['updates'][user['user_id']] = user
		try:
			test = self.botJson['users'][user['user_id']]
		except:
			self.GetUser(user['user_id'])
			time.sleep(botData.sleep_time)
		if user['user_id'] in self.botJson['undo']:
			old = self.botJson['updates'][user['user_id']]
			self.botJson['undo'][user['user_id']] = old # Copy before replace
			self.botJson['updates'][user['user_id']] = user # Update this user with latest post
		else:
			self.botJson['undo'][user['user_id']] = user # Set them both to the same to start
			self.botJson['updates'][user['user_id']] = user
		self.SaveJson()
		self.OutputTemplate()
		return "<@" + user['user_id'] + ">: Status update accepted, template updated."


	def PromoteUser(self, user, subject, level):
		''' Promotes a user to a higher level so they can post updates, or at
		superuser level they can promote other users to update posting level.
		:param user: json dict representing the user data
		:param subject: The user to act on
		:param level: int user level to promote to, 1=user, 2=superuser
		:return: String to send back to the user.
		'''
		self.SetupJson()
		if level == "superusers":
			if user['uLevel'] >= 3:
				if subject in self.botJson['superusers']:
					return "<@" + user['user_id'] + ">: Action not needed."
				self.botJson['superusers'].append(subject)
				self.SaveJson()
				return "<@" + user['user_id'] + ">: User <@" + subject + "> added to superusers."
			else:
				return "<@" + user['user_id'] + ">: You are not authorised to add other superusers."
		else:
			if user['uLevel'] >= 2:
				if subject in self.botJson['admins']:
					return "<@" + user['user_id'] + ">: Action not needed."
				self.botJson['admins'].append(subject)
				self.SaveJson()
				return "<@" + user['user_id'] + ">: User <@" + subject + "> added to authorised users."
			else:
				return "<@" + user['user_id'] + ">: You are not authorised to add other users."

			
	def DemoteUser(self, user, subject, hide):
		''' Demotes a user so they won't be allowed to post updates. Optional hide posts.
		Doesn't matter what level they are, they're gone.
		:param user: json dict representing the user data
		:param subject: The user to act upon
		:param hide: Bool to hide posts by the user at the same time
		:return: String to send back to the user
		'''
		self.SetupJson()
		if subject in self.botJson['admins']:
			self.botJson['admins'].remove(subject)
			self.SaveJson()
			return "<@" + user['user_id'] + ">: User <@" + subject + "> removed."
		elif subject in self.botJson['superusers']:
			self.botJson['superusers'].remove(subject)
			self.SaveJson()
			return "<@" + user['user_id'] + ">: User <@" + subject + "> removed."
		else:
			return "<@" + user['user_id'] + ">: Action not needed."


	def HideUserPosts(self, user, subject):
		''' Hide posts by a user, refreshes template without that users posts.
		:param user: json dict representing the user data
		:param subject: The user to act upon
		:return: String to send back to the user
		''' 
		self.SetupJson()
		if user['uLevel'] >= 1:
			if subject in self.botJson['hidden']:
				return "<@" + user['user_id'] + ">: Action not needed."
			self.botJson['hidden'].append(subject)
			self.SaveJson()
			self.OutputTemplate()
			return "<@" + user['user_id'] + ">: Posts by <@" + subject + "> are now hidden.\nTemplate refreshed."

	
	def ShowUserPosts(self, user, subject):
		''' Show posts by a user, refreshes template with that users posts.
		:param user: json dict representing the user data
		:param subject: The user to act upon
		:return: String to send back to the user
		'''
		self.SetupJson()
		if user['uLevel'] >= 1:
			if subject not in self.botJson['hidden']:
				return "<@" + user['user_id'] + ">: Action not needed."
			self.botJson['hidden'].remove(subject)
			self.SaveJson()
			self.OutputTemplate()
			return "<@" + user['user_id'] + ">: Updates by <@" + subject + "> are now seen.\nTemplate refreshed."

		
	def UndoPost(self, user):
		''' Undo a post a user has made.
		:param user: json dict representing the user data
		:return: String to send back to the user
		'''
		self.SetupJson()
		self.botJson['updates'][user['user_id']] = self.botJson['undo'][user['user_id']]
		self.SaveJson()
		self.OutputTemplate()
		response = "<@" + user['user_id'] + ">: I have undone your last update and refreshed the template."
		return response

	def AdminList(self, user):
		admins = []
		self.SetupJson()
		for k in self.botJson['admins']:
			admins.append("<@" + k + ">")
		final = ", ".join(admins)
		return "Approved posters: " + final

	def GetUser(self, user_id):
		''' Fetch user information
		:param user_id: user id to fetch info for
		:return: bool True
		'''
		req = self.client._make_request('users.info', {'user': user_id})
		self.botJson['users'][req['user']['id']] = req['user']
		return True
		
		
	def GetBalance(self, address):
		''' Fetch user sjcx balance
		:param address: sjcx address
		:return: balance string
		'''
		test = requests.get("http://api.blockscan.com/api2?module=address&action=balance&asset=SJCX&btc_address=" + address).json()
		if test['status'] == "success":
			return test['data'][0]['balance']
			

	def GetExRate(self, exchange):
		'''Exchange rate fetcher.
		:param exchange: What exchange to fetch data for.
		:return: balance string
		'''
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
		self.SetupJson()
		# Two stages, the first is to order the user id by timestamp, then pull in order
		findLatest = {}
		findPosts  = {}
		
		for key, val in self.botJson['updates'].iteritems():
			try:
				findPosts[key] = self.botJson['updates'][key]['ts']
			except:
				findPosts[key] = self.botJson['updates'][key]['timestamp']
			
		findLatest = sorted(findPosts.items(), key=itemgetter(1), reverse=True)

		tdata = []
		for key, val in findLatest:
			try:
				# Old system
				user_id = self.botJson['updates'][key]['user']
			except:
				# New system
				user_id = self.botJson['updates'][key]['user_id']
				
			try:
				ts      = self.botJson['updates'][user_id]['ts']
			except:
				ts      = self.botJson['updates'][user_id]['timestamp']

						
			# Is this a hidden post?	
			if user_id in self.botJson['hidden']:
				continue
			if user_id not in self.botJson['twitter']:
				dick = self.botJson['users'][user_id]['profile']['real_name']
				print "Cannot process entry for " + dick + ", does not have twitter account set up."
				continue
			twitter = "https://twitter.com/" + self.botJson['twitter'][user_id]
			
			tdata.append({
				"text": str(self.botJson['updates'][key]['text'].encode("utf-8")),
				"name": self.botJson['users'][user_id]['profile']['real_name'],
				"image": self.botJson['users'][user_id]['profile']['image_72'],
				"twitter": twitter,
				"email": self.botJson['users'][user_id]['profile']['email'],
				"ts": datetime.datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')
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
		
		
		
		
		
		
		
		
	



