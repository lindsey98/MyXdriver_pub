#!/usr/bin/python

from .Exceptions import *

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
	def spit(cls, msg, warning = False, debug = False, error = False, exception = False, caller_prefix = ""):
		caller_prefix = "[%s]" % caller_prefix if caller_prefix else ""
		prefix = "[FATAL]" if error else "[DEBUG]" if debug else "[WARNING]" if warning else "[EXCEPTION]" if exception else ""
		txtcolor = TxtColors.FATAL if error else TxtColors.DEBUG if debug else TxtColors.WARNING if warning else "[EXCEPTION]" if exception else TxtColors.OK
		if Logger._verbose:
			# if not debug or Logger._debug:
			if (not debug and not warning) or (debug and Logger._debug) or (warning and Logger._warning):
				print("%s%s%s %s%s" % (txtcolor, caller_prefix, prefix, msg, TxtColors.ENDC))
		if Logger._logfile:
			with open(Logger._logfile, "a") as wfp:
				wfp.write("%s%s%s %s%s\n" % (txtcolor, caller_prefix, prefix, msg, TxtColors.ENDC))

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