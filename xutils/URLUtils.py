#!/usr/bin/python

import urllib.parse
import tldextract as tld

# Necessary to make tldextract shut up about a debug level log
from tldextract.tldextract import LOG
import logging
logging.basicConfig(level=logging.CRITICAL)

class URLUtils():

	''' Get the given URL's domain (sub-domains included).
	'''
	@classmethod
	def get_domain(cls, url, strip_www = False, strip_port = True):
		if url is None:
			return None
		domain = urllib.parse.urlparse(url).netloc
		domain = domain.split(":")[0] if strip_port else domain
		return domain if not strip_www else domain.replace("www.", "")

	@classmethod
	def get_main_domain(cls, url, suffix = False):
		if url is None:
			return None
		ret = tld.extract(url)
		return ret.domain if not suffix else ret.domain + "." + ret.suffix

	@classmethod
	def get_full_domain(cls, url):
		if url is None:
			return None
		ret = tld.extract(url)
		if ret.subdomain:
			return "%s.%s.%s" % (ret.subdomain, ret.domain, ret.suffix)
		else:
			return "%s.%s" % (ret.domain, ret.suffix)

	@classmethod
	def get_subdomain(cls, url):
		if url is None:
			return None
		ret = tld.extract(url)
		return ret.subdomain

	@classmethod
	def get_path(cls, url, full_path = False):
		if url is None:
			return None
		path = urllib.parse.urlparse(url).path
		return path if not full_path else "%s?%s" % (path, URLUtils.get_query(url))

	@classmethod
	def get_query(clas, url):
		return urllib.parse.urlparse(url).query if url else None

	@classmethod
	def get_scheme(cls, url):
		return urllib.parse.urlparse(url).scheme if url else None

	@classmethod
	def join(cls, domain, path):
		return "%s%s" % (domain, path) if domain.endswith("/") or path.startswith("/") else "%s/%s"% (domain, path)

	@classmethod
	def join_scheme(cls, scheme, url):
		return scheme+"://"+url

	@classmethod
	def strip_scheme(cls, url):
		if url is None:
			return None
		scheme = URLUtils.get_scheme(url)
		return url.replace(scheme+"://", "")

	@classmethod
	def main_url(cls, url):
		domain = URLUtils.get_domain(url)
		path = URLUtils.get_path(url)
		scheme = URLUtils.get_scheme(url)
		return URLUtils.join_scheme(scheme, URLUtils.join(domain, path))

if __name__ == "__main__":
	url = "https://www.asjas.com:80/dakjejea.php"
	print(URLUtils.get_scheme(url))
	# print URLUtils.get_scheme(url)