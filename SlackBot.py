#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Storj Bot for Slack (with other functions)

# Imports
import os, sys, time, socket
import ssl, logging, json
import threading

import BaseHTTPServer
import SocketServer

from BotInfo import botData
from SlackCore import SlackRTM
from SlackCore import PostHandler

reload(sys)
sys.setdefaultencoding("utf-8")

logger = logging.getLogger('SlackBot')
logger.setLevel(logging.DEBUG)
ch = logging.FileHandler(botData.log_file, 'a', None, False)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("Initializing...")

server        = BaseHTTPServer.HTTPServer((botData.listen_ip, botData.listen_port), PostHandler)
server.socket = ssl.wrap_socket (sock=server.socket, certfile=botData.ssl_cert_file, 
                keyfile=botData.ssl_key_file, server_side=True, ca_certs="data/ca.crt")
                
print 'Starting server, use <Ctrl-C> to stop'

try:
	server.serve_forever()
except KeyboardInterrupt:
        server.server_close()
print "Server Stopped - %s:%s" % (botData.listen_ip, botData.listen_port)


