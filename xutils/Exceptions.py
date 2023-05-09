#!/usr/bin/python

def stringify_exception(e, strip = False):
	exception_str = ""
	try:
		exception_str = str(e)
		if strip: # Only return first line. Useful for webdriver exceptions
			exception_str = exception_str.split("\n")[0]
	except Exception as e:
		exception_str = "Could not stringify exception"
	return exception_str

class XDriverException(Exception):
	_prefix = "[EXCEPTION]"
	def __init__(self, message, caller_prefix = ""):
		message = "%s[%s] %s" % (XDriverException._prefix, caller_prefix, message)
		super(XDriverException, self).__init__(message)

class FrameworkException(Exception):
	_prefix = "[EXCEPTION]"
	def __init__(self, message, caller_prefix = ""):
		message = "%s[%s] %s" % (FrameworkException._prefix, caller_prefix, message)
		super(FrameworkException, self).__init__(message)