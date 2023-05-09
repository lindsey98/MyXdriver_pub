#!/usr/bin/python

from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

from xdriver.xutils.Logger import Logger
from xdriver.xutils.Exceptions import *
from xdriver.xutils.proxy.ProxyWrapper import ProxyWrapper

from uuid import uuid4
from pyvirtualdisplay import Display
import os
import shutil

from xdriver.XDriver import XDriver

# TODO: Fix page scripts on new documents (see XDriver's `setup_page_scripts`)

class FXDriver(XDriver):
	_caller_prefix = "FXDriver"
	_abs_path = os.path.dirname(os.path.abspath(__file__))
	_exec_path = os.path.join(_abs_path, "config/webdrivers/geckodriver")

	_abs_profiles_path = "/tmp"

	_arg_mappings = {
		"disable_notifications" : ["dom.push.enabled"],
		"disable_cache" : ["browser.cache.disk.enable", "browser.cache.memory.enable", "browser.cache.offline.enable", "network.http.use-cache"]
	}

	_recoverable_crashes = ["decode response from marionette"]

	def __init__(self, **kwargs):
		_firefoxOpts = Options()
		if FXDriver._base_config["browser"]["enabled"]:
			for option in FXDriver._base_config["browser"]:
				if FXDriver._base_config["browser"][option]:
					for arg in FXDriver._arg_mappings.get(option, []):
						_firefoxOpts.set_preference(arg, False)

		if FXDriver._base_config["browser"]["no_ssl_errors"]:
			_firefoxOpts.accept_insecure_certs = True

		# Use readymade profile or generate a new one
		self._profile = FXDriver._base_config["browser"].get("profile")
		if not self._profile:
			self._profile = os.path.join(FXDriver._abs_profiles_path, "xdriver-%s" % str(uuid4()))
			FXDriver._base_config["browser"]["profile"] = self._profile # Will be used if browser is rebooted

		Logger.spit("Setting custom profile to: %s" % self._profile, caller_prefix = FXDriver._caller_prefix)
		if not os.path.exists(self._profile):
			os.mkdir(self._profile) # Firefox needs to have the profile dir already created
			# shutil.copy(FXDriver._default_fxprofile_userjs, self._profile)
		# firefox_profile = FirefoxProfile(self._profile) # This should be uncommented when we fix the profile loading w/ Firefox
		firefox_profile = FirefoxProfile()
		firefox_profile.set_preference("security.enterprise_roots.enabled", True) # Trust system-wide trusted CAs -- Only works in Windows & MacOS

		## Experimental ##
		# _firefoxOpts.set_preference("profile", self._profile)
		# _firefoxOpts.profile = self._profile
		# _firefoxOpts.add_argument("-profile %s" % self._profile)
		# _firefoxOpts.profile(firefox_profile)
		##################

		''' The general proxy order is: internal proxy -> user proxy -> tor
		'''
		self._proxy = None
		if FXDriver._base_config["internal_proxy"]["enabled"]: # In any proxy configuration (e.g. proxy, custom proxy, tor), our internal proxy goes first
			self._proxy = ProxyWrapper(port = FXDriver._base_config["internal_proxy"].get("port", None), strip_media = FXDriver._base_config["internal_proxy"].get("strip_media", False), tor = FXDriver._base_config["tor"], custom_proxy = FXDriver._base_config["proxy"])
			self._proxy_port = self._proxy.get_port()
			firefox_profile.set_preference("network.proxy.type", 1)
			firefox_profile.set_preference("network.proxy.http", FXDriver._base_config["internal_proxy"]["host"])
			firefox_profile.set_preference("network.proxy.http_port", self._proxy_port)
			firefox_profile.set_preference("network.proxy.ssl", FXDriver._base_config["internal_proxy"]["host"])
			firefox_profile.set_preference("network.proxy.ssl_port", self._proxy_port)
			firefox_profile.update_preferences()
		
		if FXDriver._base_config["proxy"]["enabled"] and not FXDriver._base_config["internal_proxy"]["enabled"]: # If no internal proxy is enabled, configure browser to use custom proxy directly
			firefox_profile.set_preference("network.proxy.type", 1)
			firefox_profile.set_preference("network.proxy.http", FXDriver._base_config["proxy"]["host"])
			firefox_profile.set_preference("network.proxy.http_port", FXDriver._base_config["proxy"]["port"])
			firefox_profile.set_preference("network.proxy.ssl", FXDriver._base_config["proxy"]["host"])
			firefox_profile.set_preference("network.proxy.ssl_port", FXDriver._base_config["proxy"]["port"])
		
		if FXDriver._base_config["tor"]["enabled"] and not FXDriver._base_config["proxy"]["enabled"] and not FXDriver._base_config["internal_proxy"]["enabled"]: # Route everything directly through TOR (no intermmediate proxy)
			firefox_profile.set_preference("network.proxy.type", 1)
			firefox_profile.set_preference("network.proxy.socks_version", 5)
			firefox_profile.set_preference("network.proxy.socks", FXDriver._base_config["tor"]["host"])
			firefox_profile.set_preference("network.proxy.socks_port", FXDriver._base_config["tor"]["port"])


		os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':0') # By default output instance to the environment `DISPLAY` (can be already set)
		self._virtual_display = None
		if FXDriver._base_config["browser"]["headless"]: # If both `virtual` and `headless` are given, `headless` will prevail
			_firefoxOpts.headless = True
		elif FXDriver._base_config["browser"]["virtual"]: # Start virtual display, if instructed
			self._virtual_display = Display(visible = 0, size = (1920, 1080))
			self._virtual_display.start()

		super(FXDriver, self).__init__(executable_path = FXDriver._exec_path, firefox_profile = firefox_profile, options = _firefoxOpts, **kwargs) # Launch!
		if FXDriver._base_config["browser"]["maximized"]:
			self.maximize_window() # Maximize after launch; no command line arg like Chrome

	def quit(self, **kwargs):
		os.remove("geckodriver.log")
		super(FXDriver, self).quit(**kwargs)