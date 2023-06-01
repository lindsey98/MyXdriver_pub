#!/usr/bin/python

# from selenium.webdriver import ChromeOptions
from seleniumwire.webdriver import ChromeOptions
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from xdriver.xutils.Logger import Logger
from xdriver.xutils.Exceptions import *
from xdriver.xutils.proxy.ProxyWrapper import ProxyWrapper
from uuid import uuid4
from pyvirtualdisplay import Display
import os
import json
import time
from xdriver.XDriver import XDriver


class CXDriver(XDriver):
	_caller_prefix = "CXDriver"
	_abs_path = os.path.dirname(os.path.abspath(__file__))
	_exec_path = os.path.join(_abs_path, "config/webdrivers/chromedriver")

	_abs_profiles_path = "/tmp"

	_arg_mappings = {
		"no_ssl_errors" : ["--ignore-certificate-errors"],
		"disable_notifications" : ["--disable-notifications"],
		"maximized" : ["--start-maximized"],
		"no_default_browser_check" : ["--no-default-browser-check"],
		"disable_cache" : ["--disk-cache-dir=/dev/null", "--disk-cache-size=1"],
		"headless" : ["--headless"],
		"no_blink_feature": ["--disable-blink-features=AutomationControlled"],
	}

	_recoverable_crashes = ["chrome not reachable", "page crash",
							"cannot determine loading status", "Message: unknown error"]

	def __init__(self, **kwargs):
		_white_lists = {}
		with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config/webdrivers/lang.txt")) as langf:
			for i in langf.readlines():
				i = i.strip()
				text = i.split(' ')
				_white_lists[text[1]] = 'en'
		prefs = {
			"translate": {"enabled": True},
			"translate_whitelists": _white_lists,
			"download_restrictions": 3,
			"download.prompt_for_download": False,
			"download.default_directory": "trash/",
		}

		_chromeOpts = ChromeOptions()
		## Experimental ## -- Solves "session deleted because of page crash" errors

		_chromeOpts.add_argument("--no-sandbox")
		_chromeOpts.add_argument("--disable-dev-shm-usage")
		_chromeOpts.add_argument('--disable-gpu')
		_chromeOpts.add_argument("--enable-logging=stderr --v=1")
		_chromeOpts.add_argument('--disable-site-isolation-trials')
		# TODO: replace with your own user-agent
		_chromeOpts.add_argument(
			"user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36")
		# _chromeOpts.add_argument(
		# 	"user-agent=user-agent={}".format(configs.user_agent))

		_chromeOpts.set_capability('unhandledPromptBehavior', 'dismiss')  # dismiss
		_chromeOpts.set_capability('pageLoadStrategy', 'eager')
		_chromeOpts.add_argument("--log-level=2")
		_chromeOpts.add_argument("--window-size=1920,1080")  # fix screenshot size
		_chromeOpts.add_argument("--lang=en")

		_chromeOpts.add_experimental_option("prefs", prefs)
		_chromeOpts.add_experimental_option('useAutomationExtension', False)
		_chromeOpts.add_experimental_option("excludeSwitches", ["enable-automation"])
		_chromeOpts.add_argument("--disable-blink-features=AutomationControlled")

		_capabilities = DesiredCapabilities.CHROME
		_capabilities["goog:loggingPrefs"] = {"performance": "ALL"}  # chromedriver 75+
		_capabilities["unexpectedAlertBehaviour"] = "dismiss"  # handle alert
		_capabilities["pageLoadStrategy"] = "eager"  # eager mode #FIXME: set eager mode, may load partial webpage

		#################
		if CXDriver._base_config["browser"]["enabled"]:
			for option in CXDriver._base_config["browser"]:
				if CXDriver._base_config["browser"][option]:
					for arg in CXDriver._arg_mappings.get(option, []):
						_chromeOpts.add_argument(arg)

		# Use readymade profile or generate a new one
		self._profile = CXDriver._base_config["browser"].get("profile")
		if not self._profile:
			self._profile = os.path.join(self._abs_profiles_path, "xdriver-%s" % str(uuid4()))
			CXDriver._base_config["browser"]["profile"] = self._profile # Will be used if browser is rebooted
			# os.makedirs(self._profile, exist_ok=True)

		Logger.spit("Setting custom profile to: %s" % self._profile, caller_prefix = CXDriver._caller_prefix)
		_chromeOpts.add_argument("--user-data-dir=%s" % self._profile)

		''' The general proxy order is: internal proxy -> user proxy -> tor
		'''
		self._proxy = None
		if CXDriver._base_config["internal_proxy"]["enabled"]: # In any proxy configuration (e.g. proxy, custom proxy, tor), our internal proxy goes first
			self._proxy = ProxyWrapper(port = CXDriver._base_config["internal_proxy"].get("port", None), strip_media = CXDriver._base_config["internal_proxy"].get("strip_media", False), tor = CXDriver._base_config["tor"], custom_proxy = CXDriver._base_config["proxy"])
			self._proxy_port = self._proxy.get_port()
			_chromeOpts.add_argument("--proxy-server=%s://%s:%s" % (CXDriver._base_config["internal_proxy"]["scheme"], CXDriver._base_config["internal_proxy"]["host"], self._proxy_port))

		if CXDriver._base_config["proxy"]["enabled"] and not CXDriver._base_config["internal_proxy"]["enabled"]: # If no internal proxy is enabled, configure browser to use custom proxy directly
			_chromeOpts.add_argument("--proxy-server=%s://%s:%s" % (CXDriver._base_config["proxy"]["scheme"], CXDriver._base_config["proxy"]["host"], CXDriver._base_config["proxy"]["port"]))

		if CXDriver._base_config["tor"]["enabled"] and not CXDriver._base_config["proxy"]["enabled"] and not CXDriver._base_config["internal_proxy"]["enabled"]: # Route everything directly through TOR (no intermmediate proxy)
			_chromeOpts.add_argument("--proxy-server=%s://%s:%s" % (CXDriver._base_config["tor"]["scheme"], CXDriver._base_config["tor"]["host"], CXDriver._base_config["tor"]["port"]))

		os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':0') # By default output instance to the environment `DISPLAY` (can be already set)
		self._virtual_display = None
		if not CXDriver._base_config["browser"]["headless"] and CXDriver._base_config["browser"]["virtual"]: # Start virtual display, if instructed and only if not headless
			self._virtual_display = Display(visible = False, size = (1920, 1080))
			self._virtual_display.start()

		super(CXDriver, self).__init__(executable_path = self._exec_path, chrome_options = _chromeOpts, desired_capabilities=_capabilities, **kwargs) # Launch!

		self.add_script(CXDriver._base_config["xdriver"]["scripts"]) # Add scripts to be evaluated on each new document

	# Kudos: https://stackoverflow.com/a/47298910 + black widow (https://www.cse.chalmers.se/research/group/security/black-widow/)
	def send(self, cmd, params={}):
		resource = "/session/%s/chromium/send_command_and_get_result" % self.session_id
		url = self.command_executor._url + resource
		body = json.dumps({'cmd': cmd, 'params': params})
		response = self.command_executor._request('POST', url, body)

	def add_script(self, script):
		self.send("Page.addScriptToEvaluateOnNewDocument", {"source": script})

	def _switch_to_window(self, window_handle):
		super(CXDriver, self)._switch_to_window(window_handle)
		self.add_script(CXDriver._base_config["xdriver"]["scripts"]) # Page.addScriptToEvaluateOnNewDocument does *not* run on new windows -- Workaround to fix this
		self.refresh()