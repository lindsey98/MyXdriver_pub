#!/usr/bin/python

import sys
sys.path.insert(0, "..")

from time import sleep
import os

from xdriver.browsers.CXDriver import CXDriver

''' Opera inherits from Chrome. Same in Selenium
'''
class OXDriver(CXDriver):
	_caller_prefix = "OXDriver"
	_abs_path = os.path.dirname(os.path.abspath(__file__))
	_exec_path = os.path.join(_abs_path, "config/webdrivers/operadriver")

	_profiles_path = os.path.join(_abs_path, "config/opera_profiles/")
	_abs_profiles_path = os.path.join(_abs_path, _profiles_path)

	def __init__(self, **kwargs):
		super(OXDriver, self).__init__(**kwargs)

	''' Enable Opera built-in VPN
		TODO: In progress; cannot automate it yet
	'''
	def enable_vpn(self):
		return False; # Remove when ready

		self.get("opera://settings/privacy")
		sleep(2)
		vpn_button = self.find_element_by_id("opera-vpn")
		self.click(vpn_button)
		s = input("Go..")