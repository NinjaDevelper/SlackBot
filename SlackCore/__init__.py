#!/usr/bin/env python
# -*- coding: utf-8 -*-

# RTB 2014-01-03 Rewrite for Webhooks
# Storj Bot Core Classes

# Imports
import os, sys, traceback, json, simplejson, time, re, logging, ssl
import websocket, requests, datetime, cgi, urllib, hashlib

from BaseHTTPServer import BaseHTTPRequestHandler
import SocketServer

from chameleon.zpt.loader import TemplateLoader
from pyslack import SlackClient
from BotInfo import botData
from operator import itemgetter
from datetime import date
from validate_email import validate_email
import textwrap

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
		"add":    	"^(\.add) \<\@([\w]+)\> ?(admin|superuser)?",
		"del":		"^(\.del) \<\@([\w]+)\>",
		"hide":		"^(\.hide) \<\@([\w]+)\>",
		"show":		"^(\.show) \<\@([\w]+)\>",
		"twitter": 	"^(\.twitter) ([\w]+)$",
		"email":    "^(\.email) \<mailto\:([\w+\.-@]+)|[\w+\.-@]+\>$",
		"image":	"^(\.image) ([\w]+)$",
		"name":		"^(\.name) (.*)$",
		"status" : 	"^(\.status) (.*)$",
		"balance" :	"^(\.balance) ([A-Za-z0-9]{25,36})$",
		"list":		"^\.list",
		"markets" :	"^\.markets",
		"melotic" :	"^\.melotic",
		"poloniex" :	"^\.poloniex",
		"alts" : 	"^\.alts",
		"undo" : 	"^\.undo",
		"regen" :  	"^\.regen",
		"ping":		"^\.ping",
		"whoami":	"^\.whoami",
		"help":		"^\.help",
		"lazy":		"^\.lazy"
	}
	
	# User ability level
	userLevel = {
		"none": 0,
		"user": 1,
		"superuser": 2,
		"owner": 3
	}
	
	'''
	# Url regex
	urlFixerSingle = "<((https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?)>"
	urlFixerDouble = "<((https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?)|([^>]+)>"
	'''
	
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
			
		# Compile regex triggers and url regex
		self.triggers = {}
		for key, val in self.hooks.iteritems():
			self.triggers[key] = re.compile(val)
		'''
		BUGBUG This will not work during template generation
		self.urlCheckerSingle = re.compile(self.urlFixerSingle)
		self.urlCheckerDouble = re.compile(self.urlFixerDouble)
		'''

	def SetupJson(self):
		logger = logging.getLogger("SlackBot")
		if os.path.isfile(botData.status_file):
			# It exists, lets read it in.
			status_in = open(botData.status_file, "r")
			data      = status_in.read()
			status_in.close()
			self.botJson = simplejson.loads(data)
		else:
			# Starting over
			self.botJson = {
				"users": {},
				"updates": {},
				"undo": {},
			        "admins": [],
			        "superusers": [],
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
		self.SetupJson() # Needed for comparison checks
		# logger.debug(json.dumps(postData, indent=4))

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
		logger.debug("Request: " + str(request))
		
		if not isinstance(request, basestring):
			if len(request) >= 2:
				trigger  = request[0]
				argument = request[1]
				logger.debug("Trigger: " + trigger)
				logger.debug("Argument: " + argument)
				# Third value for a user class (for .add)
				if trigger == ".add":
					try:
						userClass = request[2]
					except:
						userClass = "admin"
				elif trigger == ".del":
					try:
						if k[2].lower() in ("yes", "true", "t", "1"):
							hideUser = True
						else:
							hideUser = False
					except:
						hideUser = False

				if postData['uLevel'] < 1:
					return "<@" + postData['user_id'] + ">: You are not an authorised user."
				# Status update?
				if trigger == ".status":
					return self.PostStatusUpdate(postData, argument)
				# Is the owner trying to be added or deleted?
				elif trigger == ".add" or trigger == ".del":
					#if str(argument) == str(botData.owner_id and postData['user_id'] == botData.owner_id):
					#	return "<@" + postData['user_id'] + ">: Cannot perform actions on bot owner."
					if trigger == ".add":
						logger.debug("JSON data: " + json.dumps(postData, indent=4))
						logger.debug("User to act on: " + argument)
						logger.debug("Class to set user at: " + userClass)
						return self.PromoteUser(postData, argument, userClass)
					elif trigger == ".del": # Removes from either list
						return self.DemoteUser(postData, argument, hideUser)
				# Show/hide condition?
				elif trigger == ".show" or trigger == ".hide":
					if trigger == ".show":
						return self.ShowUserPosts(postData, argument)
					elif trigger == ".hide":
						return self.HideUserPosts(postData, argument)
				# User details?
				elif trigger == ".name" or trigger == ".image" or trigger == ".email":
					if trigger == ".name":
						return self.UpdateUserInfo(postData, "name", argument)
					elif trigger == ".email":
						return self.UpdateUserInfo(postData, "email", argument)
					elif trigger == ".image":
						return self.UpdateUserInfo(postData, "image", argument)
				elif trigger == ".balance":
					return "Balance for address " + argument + ": " + str(self.GetBalance(argument)) + " SJCX"
				elif trigger == ".twitter":
					self.SetupJson()
					self.botJson['users'][postData['user_id']]['twitter'] = argument
					self.SaveJson()
					return "<@" + postData['user_id'] + ">: Your twitter handle is now '" + argument + "'."
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
			self.OutputTemplate(postData['user_id'])
			return 
		elif request == ".ping":
			return "PONG!"
		elif request == ".whoami":
			return "Hello <@" + postData['user_id'] + ">, your user id is " + postData['user_id'] + "."
		elif request == ".help":
			return self.HelpResponse()
		elif request == ".lazy":
			return self.FindLazyUsers()
		else:
			return "No response to give!"


	def HelpResponse(self):
		return textwrap.dedent(
			"""
			Hello, I'm SlackBot. Standard commands you can use with me are:\n
			.add (username) <superuser> - Authorise a user to post status updates. Include 'superuser' to
			give them the power to add or remove other users from the authorised list.\n
			.del (username) - Revokes status updates from a user.\n
			.show (username) - Show posts from a user on the status page.\n
			.hide (username) - Hide posts from a user on the status page.\n
			.name (name) - Updates name shown for a user added to the bot from the one pulled from Slack.\n
			.image (url) - Updates the image shown for a user added to the bot from the one pulled from Slack.\n
			.email (address) - Updates name shown for a user added to the bot from the one pulled from Slack (not that this is shown normally).\n
			.twitter (name) - Updates the twitter address for a user from the default.\n
			.status (text) - Post a status update! Use whatever text you want, it will be used in the output.\n
			.undo - Didn't mean to post that last status update? This will return it to what you said last.\n
			.regen - Force regeneration of the status page from the template.\n
			.whoami - Tells you your user_id, should you wish to change any 'settings' :)\n
			.list - Lists bot users authorised to post status updates.\n
			\n
			Enjoy!
			"""
		)

	def PostStatusUpdate(self, user, text):
		''' Creates a status update for a user, refreshes template.
		@param user: json dict representing the user data
		@param text: The status text the user wishes to post
		@return: String to send back to the user
		'''
		self.SetupJson()
		user['text'] = text
		user['ts']   = user['timestamp']
		del user['timestamp']
		self.botJson['updates'][user['user_id']] = user
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
		@param user: json dict representing the user data
		@param subject: The user to act on
		@param level: int user level to promote to, 1=user, 2=superuser
		@return: String to send back to the user.
		'''
		logger = logging.getLogger("SlackBot")
		self.SetupJson()
		logger.debug(json.dumps(user, indent=4))
		response = ""
		if level == "superuser":
			if user['uLevel'] >= 3:
				if subject in self.botJson['superusers']:
					return "<@" + user['user_id'] + ">: Action not needed."
				self.botJson['superusers'].append(subject)
				self.SaveJson()
				response += "<@" + user['user_id'] + ">: User <@" + subject + "> added to superusers.\n"
			else:
				return "<@" + user['user_id'] + ">: You are not authorised to add other superusers."
		else:
			if user['uLevel'] >= 2:
				if subject in self.botJson['admins']:
					return "<@" + user['user_id'] + ">: Action not needed."
				self.botJson['admins'].append(subject)
				self.SaveJson()
				response += "<@" + user['user_id'] + ">: User <@" + subject + "> added to authorised users.\n"
			else:
				return "<@" + user['user_id'] + ">: You are not authorised to add other users."

		newUser = {}
		''' Is the rtm api token set up? If not, complain at them.'''
		if not botData.token_id:
			self.botJson['users'][user['user_id']] = {}
			self.SaveJson()
			
			response += "<@" + subject + ">: I cannot access Slack to get your user info so you will need to enter it manually.\n"
			response += "I need your name, email and twitter details at minimum - I'll generate a gravatar address from your "
			response + "email unless you specify it as below.\n"
			response += "You can use the commands .name,.email and .twitter to update your details.\n"
			response += "You can also use .image to force your image to a direct url if Gravatar does not work with your email.\n"
			response += "Example: \".name Slack User\", \".email my.email.address@here.com\", \".image <url\", \".twitter tweeter\".\n"
			return response
		else:
			req = self.client._make_request('users.info', {'user': subject})
			logger.debug(json.dumps(req, indent=4))
			newUser['name']    = req['user']['profile']['real_name']
			newUser['image']   = req['user']['profile']['image_72']
			newUser['email']   = req['user']['profile']['email']
			newUser['twitter'] = "storjproject"
			self.botJson['users'][user['user_id']] = newUser
			self.SaveJson()
		
			response += "<@" + subject + ">: I have set up your profile with what I can gather immediately from Slack.\n"
			response += "If you want, you can use the commands .name,.email and .twitter to update your details.\n"
			response += "You can also use .image to force your image to a direct url if Gravatar does not work with your email.\n"
			response += "Example: \".name Slack User\", \".email my.email.address@here.com\", \".twitter tweeter\".\n"
			return response


	def DemoteUser(self, user, subject, hide):
		''' Demotes a user so they won't be allowed to post updates. Optional hide posts.
		Doesn't matter what level they are, they're gone.
		@param user: json dict representing the user data
		@param subject: The user to act upon
		@param hide: Bool to hide posts by the user at the same time
		@return: String to send back to the user
		'''
		self.SetupJson()
		if subject in self.botJson['admins']:
			self.botJson['admins'].remove(subject)
			self.botJson['updates'].remove(subject)
			self.SaveJson()
			self.OutputTemplate()
			return "<@" + user['user_id'] + ">: User <@" + subject + "> removed."
		elif subject in self.botJson['superusers']:
			self.botJson['superusers'].remove(subject)
			self.botJson['updates'].remove(subject)
			self.SaveJson()
			self.OutputTemplate()
			return "<@" + user['user_id'] + ">: User <@" + subject + "> removed."
		else:
			return "<@" + user['user_id'] + ">: Action not needed."


	def HideUserPosts(self, user, subject):
		''' Hide posts by a user, refreshes template without that users posts.
		@param user: json dict representing the user data
		@param subject: The user to act upon
		@return: String to send back to the user
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
		@param user: json dict representing the user data
		@param subject: The user to act upon
		@return: String to send back to the user
		'''
		self.SetupJson()
		if user['uLevel'] >= 1:
			if subject not in self.botJson['hidden']:
				return "<@" + user['user_id'] + ">: Action not needed."
			self.botJson['hidden'].remove(subject)
			self.SaveJson()
			self.OutputTemplate()
			return "<@" + user['user_id'] + ">: Updates by <@" + subject + "> are now seen.\nTemplate refreshed."


	def UpdateUserInfo(self, user, userValue, text):
		''' Update user information so status updates work properly.
		@param user: json dict representing the user data
		@param userValue: The user information to update
		@param text: The new value - a name, email address or image url.
		@return: String to send back to the user
		'''
		self.SetupJson()
		text = text.replace("'", "").replace("\\", "") # Bit of anti-xss
		if user['user_id'] not in self.botJson['users']:
			self.botJson['users'][user['user_id']] = {}
		if userValue == "name":
			self.botJson['users'][user['user_id']]['name'] = text
			self.SaveJson()
			return "<@" + user['user_id'] + ">: Your name has been updated.\nUse '.regen' to refresh the template."
		elif userValue == "email":
			if validate_email(text) == False:
				return "<@" + user['user_id'] + ">: Invalid email address."	
			gravatar_url = "http://www.gravatar.com/avatar/" + hashlib.md5(text.lower()).hexdigest() + "?"
			gravatar_url += urllib.urlencode({'d':"http://storj.sdo-srv.com/storjlogo.jpg", 's':"72"})
			self.botJson['users'][user['user_id']]['email'] = text
			self.botJson['users'][user['user_id']]['image'] = gravatar_url
			self.SaveJson()
			response  = "<@" + user['user_id'] + ">: Your email address has been updated.\nI also updated the image url "
			response += "with gravatar based on that email. If you would prefer to override that, use \".image <url>\" instead.\n"
			response += "Use \".regen\" to refresh the template."
			return response
		elif userValue == "image":
			self.botJson['users'][user['user_id']]['image'] = text
			self.SaveJson()
			return "<@" + user['user_id'] + ">: Your image url has been updated.\nUse '.regen' to refresh the template."
	
		
	def UndoPost(self, user):
		''' Undo a post a user has made.
		@param user: json dict representing the user data
		@return: String to send back to the user
		'''
		self.SetupJson()
		self.botJson['updates'][user['user_id']] = self.botJson['undo'][user['user_id']]
		self.SaveJson()
		self.OutputTemplate()
		response = "<@" + user['user_id'] + ">: I have undone your last update and refreshed the template."
		return response


	def AdminList(self, user):
		admins = []
		superusers = []
		self.SetupJson()
		for k in self.botJson['admins']:
			try:
				admins.append(self.botJson['users'][k]['name'])
			except:
				pass
		for k in self.botJson['superusers']:
			try:
				superusers.append(self.botJson['users'][k]['name'])
			except:
				pass
			
		adminList = ", ".join(admins)
		superList = ", ".join(superusers)
		return "Approved posters: " + adminList + "\n Administrators: " + superList

	def FindLazyUsers(self):
		self.SetupJson()
		text = ""
		got_any = False
		
		lazyUsers = {
			'name': {},
			'image': {},
			'email': {},
			'twitter': {}
		}
		
		for key, val in self.botJson['users'].iteritems():
			if not self.botJson['users'][key]['name']:
				lazyUsers['name'].append(self.botJson['users'][key])
			if not self.botJson['users'][key]['image']:
				lazyUsers['image'].append(self.botJson['users'][key])
			if not self.botJson['users'][key]['email']:
				lazyUsers['email'].append(self.botJson['users'][key])
			if not self.botJson['users'][key]['twitter']:
				lazyUsers['twitter'].append(self.botJson['users'][key])
		
		for no_info in ['name', 'image', 'email', 'twitter']:
			if len(lazyUsers[no_info]) > 0:
				lazy = []
				text += "Users without " + no_info + " set: "
				for user_id in lazyUsers[no_info]:
					lazy.append("<@" + user_id + ">")
				text += ", ".join(lazy)
				text += "\n"
				got_any = True

		if got_any is True:
			return "Aha!\n" + text
		else:
			return "All users in my system have complete profiles!"




			
		
	def GetBalance(self, address):
		''' Fetch user sjcx balance
		@param address: sjcx address
		@return: balance string
		'''
		test = requests.get("http://api.blockscan.com/api2?module=address&action=balance&asset=SJCX&btc_address=" + address).json()
		if test['status'] == "success":
			return test['data'][0]['balance']
			

	def GetExRate(self, exchange):
		'''Exchange rate fetcher.
		@param exchange: What exchange to fetch data for.
		@return: balance string
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


	def OutputTemplate(self, user_id):
		logger = logging.getLogger("SlackBot")
		self.SetupJson()
		# Two stages, the first is to order the user id by timestamp, then pull in order
		findLatest = {}
		findPosts  = {}
		problems   = False
		
		for key, val in self.botJson['updates'].iteritems():
			findPosts[key] = self.botJson['updates'][key]['ts']
			
		findLatest = sorted(findPosts.items(), key=itemgetter(1), reverse=True)

		tdata = []
		for key, val in findLatest:
			user_id = self.botJson['updates'][key]['user_id']

			# Is this a hidden post?	
			if user_id in self.botJson['hidden']:
				continue
			if user_id not in self.botJson['twitter']:
				self.botJson['users'][user_id]['twitter'] = "storjproject"
			
			text = str(self.botJson['updates'][key]['text'].encode("utf-8"))

			''' Reasons not to continue. We will mark a problem and skip. '''
			if not self.botJson['users'][user_id]['name']:
				problems = True
				continue
			if not self.botJson['users'][user_id]['image']:
				problems = True
				continue
			if not self.botJson['users'][user_id]['twitter']:
				problems = True
				continue
			if not self.botJson['users'][user_id]['email']:
				problems = True
				continue

			'''
			# Does it need a url parsed?
			# Single
			test = self.urlCheckerSingle.match(text)
			if test:
				textUrl = test.group(1)
				logger.debug("Text To Submit: " + text)
				logger.debug("Url Portion: " + textUrl)
				text = self.urlChecker.sub("<a href=\"" + textUrl + "\">" + textUrl + "</a>", text)
			else:
				# Double
				test = self.urlCheckerDouble.match(text)
				if test:
					textUrl = test.group(1)
					textDesc = test.group(2)
					logger.debug("Text To Submit: " + text)
					logger.debug(test.group(0))					
					logger.debug(test.group(1))
					logger.debug(test.group(2))
					logger.debug("Url Portion: " + textUrl)
					logger.debug("Description Portion: " + textDesc)	
					text = self.urlChecker.sub("<a href=\"" + textUrl + "\">" + textDesc + "</a>", strtext)
			'''
					
			tdata.append({
				"text": text,
				"name": self.botJson['users'][user_id]['name'],
				"image": self.botJson['users'][user_id]['image'],
				"twitter": self.botJson['users'][user_id]['twitter'],
				"email": self.botJson['users'][user_id]['email'],
				"ts": datetime.datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')
			})

		pt_loader = TemplateLoader(['html/'], auto_reload=True)
		template  = pt_loader.load('index.template')
		with open(botData.output_file, 'w') as template_out:
			template_out.write(template(users=tdata))
			template_out.close()
			
		if problems is True:
			response  = "<@" + user_id + ">: There was a problem outputting the template, but I did what I can.\n"
			response += self.FindLazyUsers()
			return response
		else:
			return "<@" + user_id + ">: I have refreshed the template."


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
