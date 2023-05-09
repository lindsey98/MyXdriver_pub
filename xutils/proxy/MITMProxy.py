#!/usr/bin/python

import sys
# sys.path.extend([
#     '/usr/lib/python3/dist-packages',
#     '/usr/lib/python35.zip',
#     '/usr/lib/python3.8',
#     '/usr/lib/python3.8/plat-x86_64-linux-gnu',
#     '/usr/lib/python3.8/lib-dynload',
#     '/usr/local/lib/python3.8/dist-packages'])

# from torrequest import TorRequest
from mitmproxy.script import concurrent
from mitmproxy import http
from time import time
from urllib.parse import urlparse, quote

import os
import re
import _pickle

def load(filename):
	with open(filename, 'rb') as fp:
		return _pickle.load(fp)
def dump(obj, filename):
	with open(filename, 'wb') as wfp:
		_pickle.dump(obj, wfp, protocol = 2)

if len(sys.argv) < 1:
	print("[!] Need proxy intercomm filename")
	sys.exit(1)
_proxy_intercomm_file = sys.argv[1]
_strip_media = int(sys.argv[2])

_forbidden_suffixes = r"\.(mp3|wav|wma|ogg|mkv|zip|tar|xz|rar|z|deb|bin|iso|csv|tsv|dat|txt|log|sql|xml|sql|mdb|apk|bat|bin|exe|jar|wsf|fnt|fon|otf|ttf|ai|bmp|gif|ico|jp(e)?g|png|ps|psd|svg|tif|tiff|cer|rss|key|odp|pps|ppt|pptx|c|class|cpp|cs|h|java|sh|swift|vb|odf|xlr|xls|xlsx|bak|cab|cfg|cpl|cur|dll|dmp|drv|icns|ini|lnk|msi|sys|tmp|3g2|3gp|avi|flv|h264|m4v|mov|mp4|mp(e)?g|rm|swf|vob|wmv|doc(x)?|odt|pdf|rtf|tex|txt|wks|wps|wpd)$"

_seen_urls = set()

def fetch_config():
	while True:
		try:
			config = load(_proxy_intercomm_file)
			return config
		except EOFError as e:
			continue

def dump_config(config):
	dump(config, _proxy_intercomm_file)

''' Capture each request and operate according to the current mode of operation.
	It is mandatory that FOR EACH request the config is loaded, so we are in sync with the framework.
	Sounds expensive, but I/O to a small file.
	Cookie-mode: Simply set the req's Cookie header to the config's current cookie string, for the specified domain
	Redirection mode: Given a starting URL, extract its redirection flow along with each pair of request/response headers '''

@concurrent
def request(flow):
	if _strip_media and re.search(_forbidden_suffixes, flow.request.url, re.IGNORECASE): # Return custom responses for all those suffixes (e.g. we don't want to spend time on images and misc files)
		flow.response = http.HTTPResponse.make(200, b"Hello World")
		return

	config = fetch_config()
	request_url = flow.request.url

	if config["force_cookies"]["enabled"]:
		req_domain = urlparse(request_url).netloc
		rules = config["force_cookies"]["rules"]
		
		cookie_header = ""
		for rule in rules:
			if rule["domain"] == req_domain or (rule["domain"].startswith(".") and ((req_domain.endswith(rule["domain"]) or req_domain == rule["domain"][1:]))):
				cookie_header += "%s%s" % (";" if cookie_header else "", str(rule["cookies"]))

		if cookie_header:
			flow.request.headers["Cookie"] = cookie_header

	if config["spoofing_mode"]["enabled"]:
		req_domain = urlparse(request_url).netloc
		for header, value in list(config["spoofing_mode"]["headers"].items()):
			flow.request.headers[header] = value

		for domain_rule in config["spoofing_mode"]["domain_headers"]:
			domain = domain_rule["domain"]
			headers = domain_rule["headers"]

			if domain == req_domain or (domain.startswith(".") and ((req_domain.endswith(domain) or req_domain == domain[1:]))):
				for header, value in list(headers.items()):
					flow.request.headers[header] = value

	if config["redirection_mode"]["enabled"]:
		global _seen_urls # Some websites might send async requests to the same resource (e.g. everhome.de) which is part of the flow. We need only one of them
		if not config["redirection_mode"]["flow"]: # On a new redirection flow, reset the known URLs
			_seen_urls = set()
		cur_url = config["redirection_mode"]["url"]
		if cur_url not in _seen_urls and (re.match("%s/?$" % re.escape(cur_url), request_url) or re.match("%s/?$" % re.escape(re.sub("^http://", "https://", cur_url)), request_url)):
			# The `upgraded` field is just to notify that an HTTP request was upgraded to HTTPS. Might not be necessary
			config["redirection_mode"]["flow"].append({"url" : request_url, "request_headers" : dict(flow.request.headers), "upgraded" : urlparse(cur_url).scheme == "http" and urlparse(request_url).scheme == "https"})
			_seen_urls.add(cur_url)
			dump_config(config)

@concurrent
def response(flow):
	config = fetch_config()

	request_url = flow.request.url

	if config["redirection_mode"]["enabled"]:
		cur_url = config["redirection_mode"]["url"]

		match = re.match("((%s)|(%s))/?$" % (re.escape(cur_url), re.escape(re.sub("^http://", "https://", cur_url))), request_url)
		
		if re.match("%s/?$" % re.escape(cur_url), request_url) or re.match("%s/?$" % re.escape(re.sub("^http://", "https://", cur_url)), request_url):
			try: config["redirection_mode"]["flow"][-1]["response_headers"] = dict({k.lower() : v for k,v in list(flow.response.headers.items())}) # Lower-case all header names
			except Exception as e: print(("---------> %s" % request_url))
			config["redirection_mode"]["flow"][-1]["status_code"] = flow.response.status_code

			loc = flow.response.headers.get("location", "").strip()
			if loc:
				scheme = urlparse(cur_url).scheme
				domain = urlparse(cur_url).netloc
				new_redirect = None

				if re.search(r"^http(s)?://", loc, re.IGNORECASE): # truly absolute
					new_redirect = loc
				elif loc.startswith("//"): # Inherits scheme from triggering request, stll absolute URL
					new_redirect = "%s:%s" % (scheme, loc)
				elif config["redirection_mode"]["domain"] in loc.split("/")[0]: # Absolute, without scheme, but the domain should be before any path (e.g. /login.php?redirect=`domain`)
					new_redirect = "%s://%s" % (scheme, loc)
				else: # Relative
					new_redirect = "%s://%s%s%s" % (scheme, domain, "/" if loc.startswith("/") else "", loc)

				new_redirect = new_redirect.replace(":443", "").replace(":80", "") # Chrome removes the default ports
				if not urlparse(new_redirect).path and urlparse(new_redirect).query: # Chrome adds a '/' right before the query, if it is missing and there is no path
					new_redirect = new_redirect.replace('?', '/?')

				new_redirect = new_redirect.split("#")[0] # Chrome drops the fragment in the Location header

				config["redirection_mode"]["url"] = new_redirect

			dump_config(config)

