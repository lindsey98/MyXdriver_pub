#!/usr/bin/python

import sys
sys.path.insert(0, "..")
import os

from xdriver.xutils.Logger import Logger
from xdriver.xutils.URLUtils import URLUtils
from xdriver.xutils.Regexes import Regexes

import collections
from collections import OrderedDict 

import re
import json
import requests
import mime
import base64
import datetime
from subprocess import call
import pickle as cp

class SecurityAuditor():
	_caller_prefix = "SecurityAuditor"

	_abs_path = os.path.dirname(os.path.abspath(__file__))
	_searching_preload_list = os.path.join(_abs_path, "searching_preloadlist.py")
	_preload_result = os.path.join(_abs_path, "preload_result")

	_colon_delimiter = r"\s*;\s*"

	def __init__(self, driver, url):
		self._driver = driver # XDriver instance
		self._url = url
		self._domain = URLUtils.get_domain(url)
		self._main_domain = URLUtils.get_main_domain(self._url, suffix = True)
		self._scheme = URLUtils.get_scheme(url)
		self._policies = { # Supported headers/policies
			"hsts" : self._evaluate_hsts,
			"csp" : self._evaluate_csp,
			"cors" : self._evaluate_cors,
			"x_content_type_options" : self._evaluate_x_content_type_options,
			"x_xss_protection" : self._evaluate_x_xss_protection,
			"x_frame_options" : self._evaluate_x_frame_options,
			"expect_ct" : self._evaluate_expect_ct,
			"feature_policy" : self._evaluate_feature_policy,
			"referrer_policy" : self._evaluate_referrer_policy

		}
		self._results = {}
		self._flow = None

	def evaluate(self, json_flow = None, policies = {}):
		if json_flow:
			self._flow = json_flow
		else:
			if not self._flow: # Only get the flow once
				self._flow = self._driver.get_redirection_flow(self._url)

		# Make sure we had a response
		if not self._flow or not self._flow[-1].get("response_headers", False):
			return {}

		if not policies:
			Logger.spit("No policies given for evaluation.", warning = True, caller_prefix = SecurityAuditor._caller_prefix)
			return {}

		for policy in policies:
			if policy not in self._policies: # Unknown policy
				Logger.spit("Unsupported policy: %s" % policy, warning = True, caller_prefix = SecurityAuditor._caller_prefix)
				continue
			if not policies[policy]: # Explicitly set to False (really only useful for CORS checking, which requires active tests)
				continue
			self._results[policy] = self._policies[policy]()

		return self._results

	def _evaluate_hsts(self):
		def load(filename):
			with open(filename, 'rb') as fp:
				return cp.load(fp)

		result = OrderedDict()

		# If no HSTS is set anywhere in the redirection, return empty results
		sets_hsts = False
		for flow in self._flow:
			if flow["response_headers"].get("strict-transport-security"):
				sets_hsts = True
				break
		if not sets_hsts: return {}

		Logger.spit("Evaluating HSTS", caller_prefix = SecurityAuditor._caller_prefix)

		for current_flow in self._flow:
			current_url_dict = {
				"enabled" : False,
				"header" : None,
				"max_age" : None,
				"includesubdomains" : False,
				"preload" : False,
				"preloaded" : False,
				"over_https" : False,
				"misconfigurations" : None
			}

			misconfiguration_dict = {
				"malformed" : False,
				"multiple_header" : False,
				"small_max_age_value" : False,
				"over_http" : False,
				"opt_out" : False
			}

			current_url = current_flow.get("url", None)
			domain = URLUtils.strip_scheme(current_url)
			domain = re.sub("/$", "", domain)

			current_location = current_flow["response_headers"].get("location", None)

			misconfiguration_dict["multiple_header"] = True if str(current_flow).lower().count("strict-transport-security") > 1 else misconfiguration_dict["multiple_header"]

			current_hsts = current_flow["response_headers"].get("strict-transport-security", None) if not misconfiguration_dict["multiple_header"] else None

			if not current_hsts:
				current_url_dict["misconfigurations"] = misconfiguration_dict
				result[domain] = current_url_dict
				continue

			current_url_dict["header"] = current_hsts

			current_hsts = current_hsts.lower()

			call("python3 %s %s" % (self._searching_preload_list,domain), shell=True)
			check_preload_list = load(self._preload_result)
			if check_preload_list:
				current_url_dict["preloaded"] = True
				current_url_dict["enabled"] = True

			if current_hsts:
				current_hsts = current_hsts.replace(" ","")

				if re.search(r"max-age=\d+(;|$)",current_hsts):
					if "includeSubdomains" in current_hsts:
						if not re.search(r"includesubdomains(;|$)",current_hsts):
							misconfiguration_dict["malformed"] = True
					
					if "preload" in current_hsts:
						if not re.search(r"preload(;|$)",current_hsts):
							misconfiguration_dict["malformed"] = True

					# current_hsts = current_hsts.encode("utf-8")
					if str(current_hsts).count("max-age") > 1 or str(current_hsts).count("includesubdomains") > 1 or str(current_hsts).count("preload") > 1:
						misconfiguration_dict["malformed"] = True
				else:
					misconfiguration_dict["malformed"] = True

				if not misconfiguration_dict["malformed"]:
					if not current_location:  #check if there is no redirection and current url is over https
						if current_url.startswith("http://"):
							misconfiguration_dict["over_http"] = True
						elif current_url.startswith("https://"):
							current_url_dict["over_https"] = True
					elif current_location.startswith("http://"): #check if it redirects over http
						misconfiguration_dict["over_http"] = True
					elif current_location.startswith("https://"):
						current_url_dict["over_https"] = True

					if "includesubdomains" in current_hsts:
						current_url_dict["includesubdomains"] = True

					if "preload" in current_hsts:
						current_url_dict["preload"] = True

					if "max-age" in current_hsts:
						current_hsts = current_hsts.replace(" ","")
						max_age_field = int(re.findall(r"max-age=\d+",current_hsts)[0].split("=")[1])
						current_url_dict["max_age"] = max_age_field
						if max_age_field <= 86400:
							if max_age_field == 0:
								misconfiguration_dict["opt_out"] = True
							else:
								misconfiguration_dict["small_max_age_value"] = True
							
					if current_url_dict["over_https"] and not misconfiguration_dict["small_max_age_value"] and not misconfiguration_dict["opt_out"]: #check if domain contains valid Hsts
						current_url_dict["enabled"] = True

			if (domain in result) and result[domain]["misconfigurations"]["over_http"]: #check if the domain already exists as dictionary key
				misconfiguration_dict["over_http"] = result[domain]["misconfigurations"]["over_http"]

			current_url_dict["misconfigurations"] = misconfiguration_dict

			result[domain] = current_url_dict

		for domain in list(result.keys()): #check hsts_enable field for sub-domains
			if result[domain]["enabled"] and result[domain]["includesubdomains"]:
				for key in list(result.keys()):
					if key.endswith("." + domain): #check if hey is subdomain of domain
						result[key]["enabled"] = True
		
		return result

	def _evaluate_csp(self):
		result = {
			"enabled" : False,
			"mode" : None,
			"header" : None,
			"bad_practices" : None,
			"policies" : None,
			"misconfigurations" : None,
			"malformed" : False,
			"malformed_directives": None
		}
		
		all_directives = [
			"child-src","connect-src","default-src","font-src","frame-src","img-src","manifest-src","media-src","object-src","prefetch-src","script-src",
			"script-src-elem","script-src-attr","style-src","style-src-elem","style-src-attr","worker-src","base-uri","plugin-types","sandbox","form-action",
			"frame-ancestors","navigate-to","report-uri","report-to","block-all-mixed-content","referrer","require-sri-for","require-trusted-types-for",
			"trusted-types","upgrade-insecure-requests"
		]

		experimental_Api_fields = [
			"prefetch-src","script-src-elem","script-src-attr","style-src-elem","style-src-attr","worker-src","navigate-to",
			"report-to","require-sri-for","require-trusted-types-for","trusted-types"
		]

		directives1 = [ "child-src","connect-src","font-src","frame-src","manifest-src","media-src","object-src","prefetch-src","style-src","worker-src" ]

		directives2 = [ "style-src-elem","style-src-attr" ]

		directives3 = [ "base-uri","form-action","navigate-to","default-src","img-src","script-src","script-src-elem","script-src-attr" ]

		directives4 = [ 
			"frame-ancestors","sandbox","referrer","require-sri-for","trusted-types","upgrade-insecure-requests",
			"block-all-mixed-content","require-trusted-types-for","report-to","report-uri","plugin-types"
		]

		r = self._flow[-1]
		# If no CSP headers, empty result
		if not r["response_headers"].get("content-security-policy", r["response_headers"].get("content-security-policy-report-only")): return {}

		Logger.spit("Evaluating CSP", caller_prefix = SecurityAuditor._caller_prefix)

		current_url = r.get("url", None)

		header = r["response_headers"].get("content-security-policy", None) #ToDo: When there are multiple headers, we must combine them in one csp header
		if not header: #there is not enforce mode ,check for report-only mode
			header = r["response_headers"].get("content-security-policy-report-only", None)
			result["mode"] = "report_only"
		else:
			result["mode"] = "enforcement"

		result["header"] = header.encode('utf-8') if header else None
		if not header: # No header, return empty result
			return {}

		if result["mode"] == "report_only":
			header = header.replace(r"content-security-policy-report-only:", "")
		elif result["mode"] == "enforcement":
			header = header.replace(r"content-security-policy:", "")

		header = header.strip()
		result["header"] = header

		header = header.lower()
		directive_dict = {}
		bad_practices_dict = {}
		header_list = re.split(r";|,",header)

		check_url_over_http = False #these two variables are needed for checking misconfigurations
		check_url_over_https = False

		#Directive iteration
		for header_field in header_list:
			if not header_field: #If it contains space or null
				continue

			header_field = header_field.strip()
			header_field_list = re.split(r"\s",header_field)

			current_directive = header_field_list[0]
			current_dict = {}
			misconfiguration_dict = {}
			fields_list = []
			
			malformed_list = []
			malformed_directives_list = []

			if result["malformed_directives"]:
				malformed_directives_list = result["malformed_directives"]

			if current_directive not in all_directives: #Check if directive is one of the csp directives
				malformed_directives_list.append(current_directive)
				result["malformed_directives"] = malformed_directives_list
				result["malformed"] = True
				continue

			if (current_directive in directives1) or (current_directive in directives2) or (current_directive in directives3):
				entry_syntax = r"^(%s)\s+(.*[^\s])\s*$" % current_directive
				entry_match = re.search(entry_syntax, header_field)
				if entry_match:
					if current_directive in experimental_Api_fields:
						current_dict["experimental_Api"] = True
						
					if len(header_field_list) > 1: #check if there is only one field in header_field. There is at least the directive and one field.
						fields = header_field_list[1::]

						fields_syntax = r"^(\*|\'self\'|\'unsafe-eval\'|\'unsafe-hashes\'|\'unsafe-inline\'|\'none\')$"
						base64_syntax = r"(\'(sha256)\-([A-Za-z0-9///+/=]+)\'|\'(sha384)\-([A-Za-z0-9///+/=]+)\'|\'(sha512)\-([A-Za-z0-9///+/=]+)\')"
						nonce_hash_syntax = r"^(\'nonce\-(.*)\'|\'sha256\-[A-Fa-f0-9]{64}\'|\'sha384\-[A-Fa-f0-9]{96}\'|\'sha512\-[A-Fa-f0-9]{128}\')$"
						fields_of_scheme_source_syntax = r"^(data\:|mediastream\:|blob\:|filesystem\:)$"
						url_syntax = r"^(([a-zA-Z0-9\-\_\.]+|\*)(://))?(?:[a-zA-Z0-9]|(?<!\.)\*|[-_.]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(:\d{2,5}|:\*)?(?:/[^\s]*)?"
						scheme_source_syntax = r"^([a-zA-Z0-9\-\_\.]+)\:$"

						check_wildcard = False
						check_data_scheme = False
						check_http_or_https_uri_scheme = False
						for field in fields:
							if not field:
								continue

							if field in all_directives:
								malformed_list.append(field)
								result["malformed"] = True
								continue

							fields_match = re.search(fields_syntax, field)
							nonce_hash_match = re.search(nonce_hash_syntax, field)
							base64_match = re.search(base64_syntax, field)
							fields_of_scheme_source_match = re.search(fields_of_scheme_source_syntax, field)
							url_match = re.search(url_syntax, field)
							scheme_source_match = re.search(scheme_source_syntax, field)

							if fields_match:
								if fields_match.group(0) == "*":
									check_wildcard = True

								fields_list.append(fields_match.group(0).strip("\'"))
							elif nonce_hash_match:
								fields_list.append(nonce_hash_match.group(0).strip("\'"))
							elif base64_match:
								try:
									base64_decode_value = base64.b64decode(base64_match.group(3))

									if ("sha256" in base64_match.group(0)) and (len(base64_decode_value) == 32):
										fields_list.append(base64_match.group(0).strip("\'"))
									elif ("sha384" in base64_match.group(0)) and (len(base64_decode_value) == 48):
										fields_list.append(base64_match.group(0).strip("\'"))
									elif ("sha512" in base64_match.group(0)) and (len(base64_decode_value) == 64):
										fields_list.append(base64_match.group(0).strip("\'"))
									else:
										malformed_list.append(field)
										result["malformed"] = True
								except Exception as str_except:
									malformed_list.append(field)
									result["malformed"] = True

							elif fields_of_scheme_source_match:
								if fields_of_scheme_source_match.group(0) == "data:":
									check_data_scheme = True
									if current_directive == "script-src" or current_directive == "script-src-elem" or current_directive == "script-src-attr":
										misconfiguration_dict["data_field_enabled_for_script"] = True

								fields_list.append(fields_of_scheme_source_match.group(0))
							elif (current_directive in directives2 or current_directive in directives3) and "\'report-sample\'" in field: #directives2 has one more field than directives1
								fields_list.append(field.strip("\'"))
							elif (current_directive in directives3) and ("strict-dynamic" in field):
								match_dynamic = re.search(r"^(\'strict\-dynamic\')$", field)
								if match_dynamic:
									fields_list.append(match_dynamic.group(0).strip("\'"))
								else:
									malformed_list.append(field)
									result["malformed"] = True
							elif url_match and (url_match.group(0) == field):
								if url_match.group(0).startswith("http://"):
									check_url_over_http = True
								elif url_match.group(0).startswith("https://"):
									check_url_over_https = True
								
								if (not "://" in url_match.group(0)) and (url_match.group(0)!="localhost") and (not "." in url_match.group(0)):
									malformed_list.append(field)
									result["malformed"] = True
								else:
									fields_list.append(url_match.group(0))
							elif scheme_source_match:
								if scheme_source_match.group(0) == "http:" or scheme_source_match.group(0) == "https:": 
									check_http_or_https_uri_scheme = True

								fields_list.append(scheme_source_match.group(0))                        
	
							else:
								malformed_list.append(field)
								result["malformed"] = True

						if check_wildcard or check_http_or_https_uri_scheme or check_data_scheme:
							bad_practices_dict["dangerous_wildcard_or_uri_scheme"] = "dangerous_policy_with_wildcard_or_some_of_uri_scheme(http,https,data)"
							
						if len(fields_list) > 0:
							current_dict["fields"] = fields_list

						if len(malformed_list) > 0:
							current_dict["malformed"] = malformed_list

					else:
						current_dict["malformed"] = True
						result["malformed"] = True
				else:
					current_dict["malformed"] = True
					result["malformed"] = True

			elif current_directive in directives4: #Other directives
				if current_directive == "frame-ancestors":
					entry_syntax = r"^(%s)\s+(.*[^\s])\s*$" % current_directive
					entry_match = re.search(entry_syntax, header_field)
					if entry_match:
						if current_directive in experimental_Api_fields:
							current_dict["experimental_Api"] = True

						if len(header_field_list) > 1:
							fields = header_field_list[1::]

							fields_syntax = r"^(\*|\'self\'|\'none\')$"
							fields_of_scheme_source_syntax = r"^(data\:|mediastream\:|blob\:|filesystem\:)$"
							url_syntax = r"^(([a-zA-Z0-9\-\_\.]+|\*)(://))?(?:[a-zA-Z0-9]|(?<!\.)\*|[-_.]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(:\d{2,5}|:\*)?(?:/[^\s]*)?"
							scheme_source_syntax = r"^([a-zA-Z0-9\-\_\.]+)\:$"

							check_wildcard = False
							check_data_scheme = False
							check_http_or_https_uri_scheme = False
							for field in fields:
								if not field:
									continue

								if field in all_directives:
									malformed_list.append(field)
									result["malformed"] = True
									continue

								fields_match = re.search(fields_syntax, field)
								fields_of_scheme_source_match = re.search(fields_of_scheme_source_syntax, field)
								url_match = re.search(url_syntax, field)
								scheme_source_match = re.search(scheme_source_syntax, field)
									
								if fields_match:
									if fields_match.group(0) == "*":
										check_wildcard = True
									fields_list.append(fields_match.group(0).strip("\'"))
								elif fields_of_scheme_source_match:
									if fields_of_scheme_source_match.group(0) == "data:":
										check_data_scheme = True
									fields_list.append(fields_of_scheme_source_match.group(0))
								elif url_match and (url_match.group(0) == field):
									if url_match.group(0).startswith("http://"):
										current_dict["insecure_due_to_over_http"] = True
										check_url_over_http = True
									elif url_match.group(0).startswith("https://"):
										check_url_over_https = True

									if (not "://" in url_match.group(0)) and (url_match.group(0)!="localhost") and (not "." in url_match.group(0)):
										malformed_list.append(field)
										result["malformed"] = True
									else:
										fields_list.append(url_match.group(0))
								elif scheme_source_match:
									if scheme_source_match.group(0) == "http:" or scheme_source_match.group(0) == "https:": 
										check_http_or_https_uri_scheme = True

									fields_list.append(scheme_source_match.group(0))
								else:
									malformed_list.append(field)
									result["malformed"] = True

							if check_wildcard and (not check_http_or_https_uri_scheme and not check_data_scheme):
								bad_practices_dict["wildcard"] = "dangerous_policy_without_uri_scheme"
							elif (check_http_or_https_uri_scheme or check_data_scheme) and not check_wildcard:
								bad_practices_dict["http_https_data_uri_scheme"] = "dangerous_policy_without_wildcard"

							if len(fields_list) > 0:
								current_dict["fields"] = fields_list

							if len(malformed_list) > 0:
								current_dict["malformed"] = malformed_list
						else:
							current_dict["malformed"] = True
							result["malformed"] = True
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "sandbox":
					directive_values = [
						"allow-downloads-without-user-activation","allow-forms","allow-modals","allow-orientation-lock",
						"allow-pointer-lock","allow-popups","allow-popups-to-escape-sandbox","allow-presentation","allow-same-origin",
						"allow-scripts","allow-storage-access-by-user-activation","allow-top-navigation","allow-top-navigation-by-user-activation"
					]
					syntax = r"^(%s)([a-z\-\s]*)$" % (current_directive)
					match = re.search(syntax, header_field)
					if match:
						sandbox_field_list = re.split(r"\s", match.group(2).strip())
						if len(sandbox_field_list) == 0:
							current_dict["fields"] = None
						else:
							for entry in sandbox_field_list:
								if (entry in directive_values):
									if entry == "allow-downloads-without-user-activation" or entry == "allow-storage-access-by-user-activation":
										current_dict["experimental_Api_value"] = True
									fields_list.append(entry.replace("-","_"))
								else:
									malformed_list.append(entry)
									result["malformed"] = True

							if len(fields_list) > 0:
								current_dict["fields"] = fields_list

							if len(malformed_list) > 0:
								current_dict["malformed"] = malformed_list
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "referrer":
					current_dict["deprecated_directive"] = True
					syntax = r"^(%s)\s(\'no\-referrer\'|\'none\-when\-downgrade\'|\'origin\'|\'origin\-when\-cross\-origin\'|\'origin\-when\-crossorigin\'|\'unsafe\-url\')$" % current_directive
					match = re.search(syntax, header_field)
					if match:
						current_dict["fields"] = match.group(2).strip("\'")
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "require-sri-for":
					current_dict["obselete_directive"] = True
					syntax = r"^(%s)\s+(script|style|script\s+style|style\s+script)\s*$" % current_directive
					match = re.search(syntax, header_field)
					if match:
						current_dict["fields"] = match.group(2)
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "trusted-types":
					current_dict["experimental_Api"] = True
					syntax = r"^(%s)(\s*$|\s+[a-zA-Z0-9\_\-]+\s+[a-zA-Z0-9\_\-]+\s+\'allow\-duplicates\'$|\s+[a-zA-Z0-9\_\-]+$)" % current_directive
					match = re.search(syntax, header_field)
					if match:
						if not match.group(2):
							current_dict["fields"] = None
						else:
							fields = re.split(r"\s", match.group(2).strip())
							if len(fields) == 1:
								current_dict["fields"] = match.group(2)
							elif len(fields) == 3:
								if "allow-duplicates" in match.group(2):
									for entry in fields:
										if "allow-duplicates" in entry:
											entry = entry.strip("\'")
										fields_list.append(entry)
									current_dict["fields"] = fields_list
								else:
									current_dict["malformed"] = True
									result["malformed"] = True
							else:
								current_dict["malformed"] = True
								result["malformed"] = True
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "upgrade-insecure-requests" or current_directive == "block-all-mixed-content": #There aren't fields in these directives
					if re.search(r"^(%s)$" % current_directive, header_field):
						if current_directive == "upgrade-insecure-requests" and current_url.startswith("http://"): #Misconfiguration
							try:
								url_over_https = requests.get("https://%s" % current_url.split("http://"))
								if url_over_https:
									all_header_over_https = str(url_over_https["response_headers"].get("content-security-policy", None))
									if not re.search(r"upgrade-insecure-requests(;|$)", all_header_over_https):
										misconfiguration_dict["upgrade_insecure_requests_over_only_http"] = True
							except Exception as str_except:
								print("Exception in request (upgrade-insecure-requests)")
								current_dict["error_in_request_for_checking_misconfiguration"] = str(str_except)

						current_dict["fields"] = None
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "require-trusted-types-for":
					syntax = r"^(%s)\s+(\'script\')$" % current_directive
					match = re.search(syntax, header_field)
					if match:
						current_dict["fields"] = match.group(2).strip("\'")
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "report-to":
					current_dict["experimental_Api"] = True

					report_to_header = r["response_headers"].get("report-to", None)
					if not report_to_header:
						current_dict["Report-To_header"] = "not_exist_in_response_headers"
					else:
						report_to_header = report_to_header.replace(r"report-to:", "")
						report_to_header = re.split(",",report_to_header)
					
						report_to_fields = re.split(r"\s",header_field)
						if len(report_to_fields) == 2:
							counter_exist_groupname = 0
							for entry_report_to in report_to_header:
								if re.search(r"(\'|\"){0,1}group(\'|\"){0,1}\s*:\s*(\'|\"){0,1}%s(\'|\"){0,1}" % report_to_fields[1], entry_report_to):
									counter_exist_groupname = counter_exist_groupname + 1
						
							if counter_exist_groupname == 0:        
								current_dict["report_to_header"] = "not_exist_groupname_in_header"
							elif counter_exist_groupname > 1:
								current_dict["report_to_header"] = "groupname_exists_many_times_in_header"
							else:
								current_dict["fields"] = report_to_fields[1]

						else:
							current_dict["malformed"] = True
							result["malformed"] = True

				elif current_directive == "report-uri":
					syntax = r"^(%s)\s+(.*)\s*$" % current_directive
					match = re.search(syntax, header_field)
					if match:
						url_syntax = r"^(([a-zA-Z0-9\-\_\.]+|\*)(://))(?:[a-zA-Z0-9]|(?<!\.)\*|[-_.]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(:\d{2,5}|:\*)?(?:/[^\s]*)?"
						fields = match.group(2)
						fields = re.split(r"\s", fields)
						for entry in fields:
							url_match = re.search(url_syntax, entry)
							if "://" in entry:
								if url_match:   
									fields_list.append(entry)
								else:
									malformed_list.append(entry)
									result["malformed"] = True
							else: #it is a path
								fields_list.append(entry)

						if len(fields_list) > 0:        
							current_dict["fields"] = fields_list

						if len(malformed_list) > 0:
								current_dict["malformed"] = malformed_list
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

				elif current_directive == "plugin-types":
					syntax = r"^(%s)\s+([a-zA-Z0-9\s/./+/_///-]*)$" % current_directive
					match = re.search(syntax, header_field)
					if match:
						fields_list = []
						mime_types_list = re.split(r"\s", match.group(2))
						for entry in mime_types_list:
							if mime.Types[entry]:
								fields_list.append(entry)
							else:
								malformed_list.append(entry)
								result["malformed"] = True

						if len(fields_list) > 0:
							current_dict["fields"] = fields_list

						if len(malformed_list) > 0:
							current_dict["malformed"] = malformed_list
					else:
						current_dict["malformed"] = True
						result["malformed"] = True

			if current_directive.replace("-","_") in list(directive_dict.keys()): #check if there is the directive more than one time in header
				misconfiguration_dict["multiple_directive"] = True
			
			if misconfiguration_dict:
				current_dict["misconfigurations"] = misconfiguration_dict
				
			directive_dict[current_directive.replace("-","_")] = current_dict
		#End Directive iteration

		#check general bad_practices
		check_misconf_dict = {
			"not_enabled" : False,
			"fields" : None
		}

		current_dict = {}
		for directive_entry in list(directive_dict.keys()):
			if not check_misconf_dict["not_enabled"] and ("misconfigurations" in list(directive_dict[directive_entry].keys())): #check for enabled due to misconfigurations
				check_misconf_dict["not_enabled"] = True

			tmp_directive_entry = directive_entry.replace("_","-")
			if (tmp_directive_entry in directives1) or (tmp_directive_entry in directives2) or (tmp_directive_entry in directives3): 
				fields_dict = {
					"unsafe_inline" : False,
					"nonce_or_hash" : False,
					"unsafe_eval" : False,
					"strict_dynamic" : False
				}

				if "fields" in directive_dict[directive_entry]:
					for field in directive_dict[directive_entry]["fields"]:
						if "nonce-" in field or "sha256" in field or "sha384" in field or "sha512" in field:
							fields_dict["nonce_or_hash"] = True
						elif field == "unsafe-inline":
							fields_dict["unsafe_inline"] = True
						elif field == "unsafe-eval":
							fields_dict["unsafe_eval"] = True
						elif field == "strict-dynamic":
							fields_dict["strict_dynamic"] = True

					current_dict[directive_entry] = fields_dict
		
		check_misconf_dict["fields"] = current_dict

		#check general misconfigurations/bad_practies
		misconfiguration_dict = {}
		for directive_entry in list(check_misconf_dict["fields"].keys()):
			if (not check_misconf_dict["fields"][directive_entry]["strict_dynamic"]) and (check_misconf_dict["fields"][directive_entry]["unsafe_eval"] or (check_misconf_dict["fields"][directive_entry]["unsafe_inline"] and not check_misconf_dict["fields"][directive_entry]["nonce_or_hash"])):
				misconfiguration_dict["unsafe_%s"%directive_entry] = True

		if not "default_src" in list(check_misconf_dict["fields"].keys()): #bad_practice is to not have default-src or some of script-src,object-src,base-uri
			if not "script_src" in list(check_misconf_dict["fields"].keys()): 
				bad_practices_dict["script_src"] = "directive_is_missing"
			
			if not "object_src" in list(check_misconf_dict["fields"].keys()):
				bad_practices_dict["object_src"] = "directive_is_missing"

			if not "base_uri" in list(check_misconf_dict["fields"].keys()): #base-uri is only for bad practice ,not for the above misconfiguration
				bad_practices_dict["base_uri"] = "directive_is_missing"

		if directive_dict and (not "require_trusted_types_for" in list(directive_dict.keys())): #It is good to have require_trusted_types_for directive for safe csp policy
			bad_practices_dict["require_trusted_types_for"] = "directive_is_missing"

		if check_url_over_http and check_url_over_https and ("block_all_mixed_content" in list(directive_dict.keys())): #it is not normal to have allow http and https and have block_all_mixed_content directive
			bad_practices_dict["block_all_mixed_content"] = "there is url over http ,url over https and block_all_mixed_content"
		#end check general bad_practices

		result["misconfigurations"] = misconfiguration_dict
		result["policies"] = directive_dict
		result["bad_practices"] = bad_practices_dict

		if (len(result["policies"]) == 1) and ("out_of_directives" in result["policies"][list(result["policies"].keys())[0]]): #Check if there is only one directive which is not csp directive   
			check_misconf_dict["not_enabled"] = True

		if not result["malformed"] and not check_misconf_dict["not_enabled"] and not misconfiguration_dict and result["mode"] != "report-only":     
			result["enabled"] = True

		return result

	''' CORS checking requires active testing and takes some time. Be sure to disable it explicitly when evaluating all other policies if you don't need it.
		Kudos to:
		https://www.jianjunchen.com/papers/CORS-USESEC18.pdf
		https://github.com/chenjj/CORScanner '''
	def _evaluate_cors(self):
		Logger.spit("Evaluating CORS...", caller_prefix = SecurityAuditor._caller_prefix)

		def check_cors(origin):
			self._driver.spoof_headers(domain_headers = [{"domain" : ".%s" % self._main_domain, "headers" : {"origin" : origin}}], headers = {"cache-control" : "no-cache"})
			
			flow = self._driver.get_redirection_flow(self._url)
			if not flow or not flow[-1].get("response_headers", False):
				return {}
			
			response = flow[-1] # Interested only in the final response
			if self._main_domain != URLUtils.get_main_domain(response["url"], suffix = True): # Redirects to different domain
				return {}

			acao = response["response_headers"].get("access-control-allow-origin")
			if not acao: # No CORS
				return {"cors" : False, "credentialed" : False, "vulnerable" : False}

			response_origin = "%s://%s" % (URLUtils.get_scheme(acao), URLUtils.get_domain(acao))

			credentialed = response["response_headers"].get("access-control-allow-credentials") == "true"
			
			if origin.lower() == response_origin: # Vulnerable. Also check if credentialed requests are allowed
				return {"cors" : True, "credentialed" : credentialed, "vulnerable" : True}

			return {"cors" : True, "credentialed" : credentialed, "vulnerable" : False}

		cors_results = {
			"cors" : False, # If the domain under evaluation uses CORS
			"misconfiguration" : None, # Misconfiguration type
			"credentialed" : None # Credentialed cross-origin rquests allowed
		}
		
		cors_tests = OrderedDict()
		cors_tests["reflect_origin"] = "%s://evil.com" % self._scheme
		cors_tests["substring_match"] = "%s://abc.%s.evil.com" % (self._scheme, self._domain)
		cors_tests["prefix_match"] = "%s://%s.evil.com" % (self._scheme, self._domain)
		cors_tests["suffix_match"] = "%s://evil%s" % (self._scheme, self._domain)
		cors_tests["trust_null"] = "null"
		# cors_tests["include_match"] = "%s://%s" % (self._scheme, self._domain[1:])
		cors_tests["escape_dot"] = "%s://%s" % (self._scheme, self._domain[::-1].replace(".", "a", 1)[::-1])
		# cors_tests["custom_third_parties"] = ["custom", "domain", "that should", "be", "read", "from file"] # TODO: What it says
		# cors_tests["special_char_bypass"] = ["%s://%s%s.evil.com" % (self._scheme, self._domain, special_char) for special_char in ['_','-','"','{','}','+','^','%60','!','~','`',';','|','&',"'",'(',')','*',',','$','=','+',"%0b"]]
		cors_tests["trust_any_subdomain"] = "%s://evil.%s" % (self._scheme, self._domain)
		cors_tests["https_trust_http"] = "http://%s" % self._domain
		
		for test in cors_tests:
			Logger.spit("%s" % test, debug = True, caller_prefix = SecurityAuditor._caller_prefix)
			if isinstance(cors_tests[test], str):
				res = check_cors(cors_tests[test])
				cors_results["cors"] = res.get("cors", False)
				if not res.get("vulnerable", False): # Move on if not misconfigured
					continue
				cors_results["misconfiguration"] = test # Store it only if a misconfiguration has been found
				cors_results["credentialed"] = res["credentialed"]
			else: # Used only for special char & custom origins test
				for origin in cors_tests[test]:
					res = check_cors(origin)
					cors_results["cors"] = res.get("cors", False)
					if not res.get("vulnerable"): # If we hit a positive, don't check the rest for this test
						continue
					cors_results["misconfiguration"] = test
					cors_results["credentialed"] = res["credentialed"]
					break
			if res.get("vulnerable"): break # Found misconfiguration; done

		return cors_results

	def _evaluate_x_content_type_options(self):
		result = {
			"header" : None,
			"enabled" : False,
			"malformed" : False,
			"multiple_header" : False
		}

		r = self._flow[-1] 
		# Empty result if no header is set
		if not r["response_headers"].get("x-content-type-options"): return {}

		Logger.spit("Evaluating X-Content-Type-Options", caller_prefix = SecurityAuditor._caller_prefix)

		result["multiple_header"] = str(r).lower().count("x-content-type-options") > 1
		header = r["response_headers"].get("x-content-type-options", None) if not result["multiple_header"] else None

		if not header:
			return result
		
		header = header.strip()
		result["header"] = header
		
		if re.search(r"^nosniff;?$", header, re.IGNORECASE):
			result["enabled"] = True
		else:
			result["malformed"] = True

		return result

	def _evaluate_x_xss_protection(self):
		result = {
			"header" : None,
			"enabled" : False,
			"mode" : None,
			"report" : None,
			"malformed" : False,
			"multiple_header" : False
		}

		r = self._flow[-1] # X-XSS-Protection's scope is per-page, so we are interested only in the landing page
		if not r["response_headers"].get("x-xss-protection"): return {} # Empty result if no header

		Logger.spit("Evaluating X-XSS-Protection", caller_prefix = SecurityAuditor._caller_prefix)

		result["multiple_header"] = str(r).lower().count("x-xss-protection") > 1
		header = r["response_headers"].get("x-xss-protection", None) if not result["multiple_header"] else None
		
		if not header:
			return result

		header = header.strip()
		result["header"] = header
		
		enabled_syntax = r"^([01]{1})\s*(;|$)"
		enabled_match = re.match(enabled_syntax, header, re.IGNORECASE)
		result["enabled"] = bool(enabled_match) and enabled_match.group(1) == "1"

		block_syntax = r"\s*mode\s*=\s*block\s*(;|$)"
		result["mode"] = "block" if re.search(block_syntax, header, re.IGNORECASE) else result["mode"]

		report_syntax = r"\s*report\s*=\s*(%s)\s*(;|$)" % Regexes.URL
		report_match = re.search(report_syntax, header, re.IGNORECASE)
		result["report"] = report_match.group(1) if report_match else result["report"]

		if result["enabled"]:
			malformed_syntax = r"^%s(%s|%s|;$|$)" % (enabled_syntax,block_syntax,report_syntax)
			if not re.search(malformed_syntax, header, re.IGNORECASE):
				result["malformed"] = True
		else:
			malformed_syntax = r"^%s(;$|$)" % enabled_syntax
			if not re.search(malformed_syntax, header, re.IGNORECASE):
				result["malformed"] = True

		if result["malformed"]:
			result["enabled"] = False

		return result

	def _evaluate_x_frame_options(self):
		result = {
			"header" : None,
			"enabled" : False,
			"deny" : False, 
			"sameorigin" : False, 
			"allow_from" : None,
			"malformed" : False,
			"multiple_header" : False
		}
		
		r = self._flow[-1]
		if not r["response_headers"].get("x-frame-options"): return {} # Empty result if no header

		Logger.spit("Evaluating X-Frame-Options", caller_prefix = SecurityAuditor._caller_prefix)

		result["multiple_header"] = True if str(r).lower().count("x-frame-options") > 1 else result["multiple_header"]
		header = r["response_headers"].get("x-frame-options", None) if not result["multiple_header"] else None

		if not header:
			return result

		header = header.strip()
		result["header"] = header

		result["deny"] = bool(re.match(r"^deny;?$", header, re.IGNORECASE))

		result["sameorigin"] = bool(re.match(r"^sameorigin;?$", header, re.IGNORECASE))

		allow_from_syntax = r"^allow-from\s+(%s);?$" % Regexes.URL
		allow_from_match = re.search(allow_from_syntax, header, re.IGNORECASE)
		result["allow_from"] = allow_from_match.group(1) if allow_from_match else result["allow_from"]

		if not result["deny"] and not result["sameorigin"] and not result["allow_from"]:
			result["malformed"] = True
		else:
			result["enabled"] = True    

		return result
	
	def _evaluate_expect_ct(self):
		result = {
			"header" : None,
			"enabled" : False,
			"max_age" : None,
			"enforce" : False,
			"report_uri" : None,
			"misconfigurations" : None,
			"malformed" : False
		}

		misconfiguration_dict = {
			"multiple_header" : False,
			"opt_out" : False,
			"max_age" : False,
			"over_http" : False
		}

		r = self._flow[-1]
		if not r["response_headers"].get("expect-ct"): return {} # Empty result if no header

		Logger.spit("Evaluating Expect-CT", caller_prefix = SecurityAuditor._caller_prefix)

		misconfiguration_dict["multiple_header"] = True if str(r).lower().count("expect-ct") > 1 else misconfiguration_dict["multiple_header"]
		
		header = r["response_headers"].get("expect-ct", None) if not misconfiguration_dict["multiple_header"] else None
		if not header:
			result["misconfigurations"] = misconfiguration_dict
			return result

		result["header"] = header

		max_age_syntax = r"max-age\s*=\s*\d+(,|$)"
		max_age_match = re.search(max_age_syntax, header, re.IGNORECASE)
		result["max_age"] = int(max_age_match.group(0).split(",")[0].replace(" ","").split("=")[1]) if max_age_match else result["max_age"]
		if result["max_age"] == 0:
			misconfiguration_dict["opt_out"] = True
		elif (result["max_age"] and result["max_age"] < 0) or not result["max_age"]: #max-age field is obligatory
			misconfiguration_dict["max_age"] = True

		enforce_syntax = r"enforce\s*(,|$)"
		enforce_match = re.search(enforce_syntax, header, re.IGNORECASE)
		result["enforce"] = True if enforce_match else result["enforce"]

		report_uri_syntax = r"report-uri\s*=\s*(\"%s\")(,|$)" % Regexes.URL
		report_uri_match = re.search(report_uri_syntax, header, re.IGNORECASE)
		result["report_uri"] = report_uri_match.group(1) if report_uri_match else result["report_uri"]

		misconfiguration_dict["over_http"] = True if r.get("url", None).startswith("http://") else misconfiguration_dict["over_http"]

		result["misconfigurations"] = misconfiguration_dict

		if ("max-age" in header and not max_age_match) or ("enforce" in header and not enforce_match) or ("report-uri" in header and not report_uri_match):
			result["malformed"] = True

		if not result["malformed"] and not result["misconfigurations"]["opt_out"] and not result["misconfigurations"]["max_age"] and not result["misconfigurations"]["over_http"]:
			result["enabled"] = True

		return result

	def _evaluate_feature_policy(self):
		result = {
			"header" : None,
			"enabled" : False,
			"policies" : None, 
			"malformed" : False,
			"multiple_header" : False
		}

		features = [
			"accelerometer", "ambient-light-sensor", "autoplay", "battery", "camera", "display-capture", "document-domain", "encrypted-media", "execution-while-not-rendered",
			"execution-while-out-of-viewport", "fullscreen", "geolocation", "gyroscope", "layout-animations", "legacy-image-formats", "magnetometer", "microphone", "midi",
			"navigation-override", "oversized-images", "payment", "picture-in-picture", "publickey-credentials", "sync-xhr", "usb", "vr", "wake-lock", "xr-spatial-tracking",
			"speaker", "unoptimized-images", "unsized-media", "vibrate"
		]

		r = self._flow[-1]
		if not r["response_headers"].get("feature-policy"): return {}

		Logger.spit("Evaluating Feature-Policy", caller_prefix = SecurityAuditor._caller_prefix)
		
		result["multiple_header"] = True if str(r).lower().count("feature-policy") > 1 else result["multiple_header"]
		header = r["response_headers"].get("feature-policy", None) if not result["multiple_header"] else None

		if not header:
			return result

		header = header.strip()

		result["header"] = header

		header = header.lower()

		current_policies = {}
		for entry in features:
			if not entry in header:
				continue

			entry = entry.strip()
			
			current_dict = {}

			misconfiguration_dict = {
				"none_field_with_origin" : False,
				"wildcard_field_with_origin" : False,
				"multiple_field" : False
			}
		
			entry_syntax = r"%s\s+(\*|\'none\'|\'self\'|\'src\'|%s)(\s+%s)*\s*(;|$)" % (entry, Regexes.URL, Regexes.URL)
			entry_match = re.search(entry_syntax, header, re.IGNORECASE)
			if entry_match:
				current_list = []
				for item in entry_match.groups():
					if item == ";" or item == None or item == "": #check if item is semicolon or null, then it ignored
						continue

					item = item.strip().strip(";").strip("\'")

					if item == "*": #check if there is * field and it will be followed by origin(s)
						if re.search(r"(\*)\s(%s)+"% Regexes.URL, header, re.IGNORECASE):
							misconfiguration_dict["wildcard_field_with_origin"] = True
					if item == "none": #check if there is none field and it will be followed by origin(s)
						if re.search(r"(\'none\')\s(%s)+"% Regexes.URL, header, re.IGNORECASE):
							misconfiguration_dict["none_field_with_origin"] = True

					current_list.append(item)

				if current_list:
					current_dict["fields"] = current_list

					if entry.replace("-","_") in list(current_policies.keys()):
						misconfiguration_dict["multiple_field"] = True

					if misconfiguration_dict["wildcard_field_with_origin"] or misconfiguration_dict["none_field_with_origin"] or misconfiguration_dict["multiple_field"]:
						current_dict["misconfigurations"] = misconfiguration_dict
				
					current_policies[entry.replace("-","_")] = current_dict
			else:
				result["malformed"] = True
		#End iteration for features
		if current_policies:
			result["policies"] = current_policies

		for entry in header.split(";"): #check if there is at least one field and it is out of features list
			entry = entry.strip()

			if result["malformed"]:
				break

			if re.match(r"^\s*$",entry):
				continue

			if re.split(r'\s',entry)[0] not in features:
				result["malformed"] = True

		if not result["malformed"]:
			check_not_enabled = False
			if result["policies"]:
				for entry in result["policies"]:
					entry = entry.replace("-","_")
					if len(result["policies"][entry]) == 2: #check if exist misconfifuration for entry
						if result["policies"][entry]["misconfigurations"]["none_field_with_origin"] or result["policies"][entry]["misconfigurations"]["wildcard_field_with_origin"]:
							check_not_enabled = True

				if not check_not_enabled:
					result["enabled"] = True
			else:
				result["malformed"] = True

		return result

	def _evaluate_referrer_policy(self):
		result = {
			"header" : None,
			"enabled" : False,
			"no_referrer" : False,
			"no_referrer_when_downgrade" : False,
			"origin" : False,
			"origin_when_cross_origin" : False,
			"same_origin" : False,
			"strict_origin" : False,
			"strict_origin_when_cross_origin" : False,
			"unsafe_url" : False,
			"malformed" : False,
			"multiple_header": False
		}

		policy_fields = [
			"no-referrer",
			"no-referrer-when-downgrade",
			"origin",
			"origin-when-cross-origin",
			"same-origin",
			"strict-origin",
			"strict-origin-when-cross-origin",
			"unsafe-url"
		]
		
		r = self._flow[-1]
		if not r["response_headers"].get("referrer-policy"): return {}

		Logger.spit("Evaluating Referrer-Policy", caller_prefix = SecurityAuditor._caller_prefix)

		result["multiple_header"] = True if str(r).lower().count("referrer-policy") > 1 else result["multiple_header"]
		header = r["response_headers"].get("referrer-policy", None) if not result["multiple_header"] else None

		if not header:
			return result

		header = header.strip()		
		result["header"] = header

		header = header.lower()
		check_all_spaces = False
		for entry in header.split(","):
			if not entry: #check if there are two comma together without field
				continue

			entry = entry.strip()

			check_all_spaces = True
			if entry in policy_fields:
				result[entry.replace("-","_")] = True
			else:
				result["malformed"] = True

		if not result["malformed"]:
			for entry in policy_fields: #check if at least one field has true value. There is header with all fields false but policy is not empty e.g referrer-policy: ,
				if result[entry.replace("-","_")]:
					result["enabled"] = True
					break

		return result