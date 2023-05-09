#!/usr/bin/python

from ..Logger import Logger
from ..Exceptions import *
from ..URLUtils import URLUtils

import os
import subprocess
import signal
import socket

from random import choice
from time import sleep, time
from uuid import uuid4
from copy import deepcopy
import pickle as cp

class ProxyWrapper():

	_caller_prefix = "ProxyWrapper"
	
	_abs_path = os.path.dirname(os.path.abspath(__file__))

	_port_range = list(range(9000, 60000))

	_proxy_intercomm_dir = "/tmp"
	_proxy_intercomm_file = None
	_proxy_port = None # Will be set when bootstrapped

	_mitm_bin = os.path.join(_abs_path, "mitm/mitmdump")
	_mitm_script = os.path.join(_abs_path, "MITMProxy.py")

	_base_config = {
		"force_cookies" : { # Useful to force cookies on the wire. This can be done to avoid sending out persistent cookies (even though they will be present in the browser)
			# Each rule should be a dict of type {'domain' : 'example.com', 'cookies' : 'A=1; B=2'}. The `domain` field follows the cookie-domain notation,
			# e.g. 'example.com' will send the cookies only to that domain (host-only), while '.example.com' will also send the cookies to any subdomains of example.com
			# The `cookies` field should be a valid cookie string that will be set in each HTTP request's "Cookie" header towards `domain`
			"enabled" : False,
			"rules" : []
		},
		"redirection_mode" : { # Extract redirection flow from a given starting URL (e.g. http://example.com -> https://example.com -> https://www.example.com). Headers included
			"enabled" : False,
			"url" : None, # Starting URL
			"flow" : None # Results. Will be filled by the mitmdump subprocess
		},
		"spoofing_mode" : { # Spoof any header. If the header exists, it will be replaced with the spoofed one
			"enabled" : False,
			"headers" : {}, # Dictionary of the form: {"origin" : "abc.com", "user-agent" : "whatever"}. These will be spoofed for all requests
			"domain_headers" : [] # Domain-specific rules. Similar as the `force_cookies` mode rules. E.g. {"domain" : "abc.com", "headers" : {"x-header" : "blah"}"}
		}
	}

	@classmethod
	def _get_free_port(cls):
		while True:
			chosen_port = choice(ProxyWrapper._port_range)
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			try:
				s.bind(('localhost', chosen_port))
				return chosen_port, s
			except (OSError, socket.error) as e:
				if e.errno == 98: # Port is used
					continue
				raise # Raise anything else
		raise Exception("Not available ports in range [%s,%s)" % (ProxyWrapper._port_range[0], ProxyWrapper._port_range[-1]))

	def __init__(self, port = None, strip_media = False, mitm_script = None, tor = {"enabled" : False}, custom_proxy = {"enabled" : False}):
		self._proxy_intercomm_file = os.path.join(ProxyWrapper._abs_path, ProxyWrapper._proxy_intercomm_dir, "xdriver_proxy-%s" % str(uuid4())) # Unique ID used for inter-process comm between ProxyWrapper and the mitmproxy subprocess

		self._proxy_port, sock = (port, None) if port else ProxyWrapper._get_free_port()
		Logger.spit("Reserved port %s" % self._proxy_port, caller_prefix = ProxyWrapper._caller_prefix)

		self.dump_config(config = ProxyWrapper._base_config)
		self._proxy_config = self.load_config()

		# Close socket holding the port directly before launching the proxy
		if sock:
			sock.close()

		if custom_proxy["enabled"]: # Route everything through user defined proxy
			proc = subprocess.Popen([ProxyWrapper._mitm_bin, "-s", "%s %s %s" % (ProxyWrapper._mitm_script if not mitm_script else mitm_script, self._proxy_intercomm_file, int(strip_media)), "-p", str(self._proxy_port), "--insecure", "--quiet", "-U", "%s://%s:%s" % (custom_proxy["scheme"], custom_proxy["host"], custom_proxy["port"])])
		else:
			proc = subprocess.Popen([ProxyWrapper._mitm_bin, "-s", "%s %s %s" % (ProxyWrapper._mitm_script if not mitm_script else mitm_script, self._proxy_intercomm_file, int(strip_media)), "-p", str(self._proxy_port), "--insecure", "--quiet"])

		sleep(2)
		retcode = proc.poll() # Just to make sure
		if retcode: # No exit code, no prob
			raise FrameworkException("Proxy could not boot.", caller_prefix = ProxyWrapper._caller_prefix)

	def set_port(self, port):
		self._proxy_port = port
	def get_port(self):
		return self._proxy_port

	def get_intercomm_file(self):
		return self._proxy_intercomm_file

	def load_config(self):
		while True:
			try:
				with open(self._proxy_intercomm_file, 'rb') as fp: return cp.load(fp)
			except EOFError: continue
	def dump_config(self, config = None):
		# If proxy settings/modes have been passed before bootstrap
		if self._proxy_intercomm_file:
			with open(self._proxy_intercomm_file, 'wb') as wfp:
				cp.dump(config if config else self._proxy_config, wfp)
	
	def force_cookies(self, rules = {}, enabled = True):
		self._proxy_config["force_cookies"]["enabled"] = enabled
		self._proxy_config["force_cookies"]["rules"] = rules
		self.dump_config()

	def redirection_mode(self, url):
		self._proxy_config["redirection_mode"]["enabled"] = True
		self._proxy_config["redirection_mode"]["url"] = url if url.startswith("http://") or url.startswith("https://") else "%s%s" % ("http://", url)
		self._proxy_config["redirection_mode"]["flow"] = []
		self._proxy_config["redirection_mode"]["domain"] = URLUtils.get_domain(url)
		self.dump_config()

	def get_redirection_flow(self): # Consume the stored redirection flow
		config = self.load_config()
		flow = config["redirection_mode"]["flow"]

		self._proxy_config["redirection_mode"]["enabled"] = False
		self.dump_config()
		return flow

	def spoof_headers(self, headers = {}, domain_headers = {}, reset = False, enabled = True):
		self._proxy_config["spoofing_mode"]["enabled"] = True
		if reset:
			self._proxy_config["spoofing_mode"]["headers"] = headers
			self._proxy_config["spoofing_mode"]["domain_headers"] = domain_headers
		else:
			self._proxy_config["spoofing_mode"]["headers"].update(headers)
			self._proxy_config["spoofing_mode"]["domain_headers"].extend(domain_headers)
		self.dump_config()

	def remove_config(self):
		os.remove(self._proxy_intercomm_file)
