#!/usr/bin/python

from .Exceptions import *
import logging
import os
import re
class Logger():

	_caller_prefix = "LOGGER"
	_verbose = True
	_logfile = None
	_screenshot_dir = None
	_debug = False # Off by default
	_warning = True
	_driver = None

	@classmethod
	def set_verbose(cls, verbose):
		cls._verbose = verbose

	@classmethod
	def set_logfile(cls, logfile):
		if os.path.isfile(logfile):
			os.remove(logfile)  # Remove the existing log file
		Logger._logfile = logfile

	@classmethod
	def unset_logfile(cls):
		Logger.set_logfile(None)

	@classmethod
	def set_screenshot_dir(cls, dirname):
		Logger._screenshot_dir = dirname

	@classmethod
	def set_driver(cls, driver):
		Logger._driver = driver

	@classmethod
	def set_debug_on(cls):
		Logger._debug = True

	@classmethod
	def set_debug_off(cls): # Call if need to turn debug messages off
		Logger._debug = False

	@classmethod
	def set_warning_on(cls):
		Logger._warning = True

	@classmethod
	def set_warning_off(cls): # Call if need to turn warnings off
		Logger._warning = False

	@classmethod
	def spit(cls, msg, warning=False, debug=False, error=False, exception=False, caller_prefix=""):
		logging.basicConfig(level=logging.DEBUG if Logger._debug else logging.WARNING)
		caller_prefix = f"[{caller_prefix}]" if caller_prefix else ""
		prefix = "[FATAL]" if error else "[DEBUG]" if debug else "[WARNING]" if warning else "[EXCEPTION]" if exception else ""
		logger = logging.getLogger("custom_logger")  # Choose an appropriate logger name
		# if not debug or Logger._debug:
		# 	if (not debug and not warning) or (debug and Logger._debug) or (warning and Logger._warning):
		# 		log_func = logger.error if error else logger.debug if debug else logger.warning if warning else logger.exception if exception else logger.info
		# 		log_func("%s%s%s %s" % (caller_prefix, prefix, msg, TxtColors.ENDC))
		if Logger._logfile:
			log_msg = re.sub(r"\033\[\d+m", "", msg)
			log_handler = logging.FileHandler(Logger._logfile, mode='a')
			log_formatter = logging.Formatter('%(message)s')
			log_handler.setFormatter(log_formatter)
			logger.addHandler(log_handler)
			logger.propagate = False
			logger.setLevel(logging.DEBUG if Logger._debug else logging.WARNING)
			logger.debug("%s%s%s %s" % (caller_prefix, prefix, log_msg, TxtColors.ENDC))
			logger.removeHandler(log_handler)
		else:
			if Logger._verbose:
				txtcolor = TxtColors.FATAL if error else TxtColors.DEBUG if debug else TxtColors.WARNING if warning else "[EXCEPTION]" if exception else TxtColors.OK
				# if not debug or Logger._debug:
				if (not debug and not warning) or (debug and Logger._debug) or (warning and Logger._warning):
					print("%s%s%s %s%s" % (txtcolor, caller_prefix, prefix, msg, TxtColors.ENDC))

	@classmethod
	def screenshot(cls, filename): # No filename extension needed; default to .png
		try:
			Logger._driver.save_screenshot("%s/%s.png" % (Logger._screenshot_dir, filename))
		except Exception as ex: # Catch it, we don't want these to be fatal
			Logger.spit("Failed to save screenshot for: %s" % filename, caller_prefix = Logger._caller_prefix)
			Logger.spit(stringify_exception(ex), caller_prefix = Logger._caller_prefix)

class TxtColors:
	OK = '\033[92m'
	DEBUG = '\033[94m'
	WARNING = "\033[93m"
	FATAL = '\033[91m'
	EXCEPTION = '\033[100m'
	ENDC = '\033[0m'

if __name__ == "__main__":
	Logger.spit("This is a regular message")
	Logger.set_debug_on()
	Logger.spit("DEBUG "*10, debug = True)
	Logger.spit("WARNING "*8, warning = True)
	Logger.spit("ERROR "*10, error = True)