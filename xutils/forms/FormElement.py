#!/usr/bin/python

import re

from collections import OrderedDict
from random import choice, randint
from string import ascii_uppercase, ascii_lowercase
from faker import Faker
from selenium.webdriver.support.select import Select
from typing import Union
from ..Logger import Logger
from ..Exceptions import *
from ..Regexes import Regexes
from ..TextMatching import special_character_replacement
import random
from selenium.webdriver.common.keys import Keys
import time
import os
from googletrans import Translator

''' Wrapper class for Selenium's form input WebElements.
'''
def random_int(min: int = 0, max: int = 9999, step: int = 1) -> int:
	return random.randrange(min, max + 1, step)

def random_digit() -> int:
	return random.randint(0, 9)

def random_digit_not_null() -> int:
	return random.randint(1, 9)


def random_digit_or_empty() -> Union[int, str]:
	if random.randint(0, 1):
		return random.randint(0, 9)
	else:
		return ""

def random_digit_not_null_or_empty() -> Union[int, str]:
	if random.randint(0, 1):
		return random.randint(1, 9)
	else:
		return ""

def _numerify(text: str = "###") -> str:
	_re_hash = re.compile(r"#")
	_re_perc = re.compile(r"%")
	_re_excl = re.compile(r"!")
	_re_at = re.compile(r"@")
	text = _re_hash.sub(lambda x: str(random_digit()), text)
	text = _re_perc.sub(lambda x: str(random_digit_not_null()), text)
	text = _re_excl.sub(lambda x: str(random_digit_or_empty()), text)
	text = _re_at.sub(lambda x: str(random_digit_not_null_or_empty()), text)
	return text

def _gmail():
	return "mymail@gmail.com"  # Depending on the account we are using

def _password():
	return "Mycust0mpassw0rd!"

def _profile_pic():
	return os.path.join(os.path.dirname(os.path.abspath(__file__)), "images/loading_icon/icon.png")

def _area_code():
	return "1"

def _rand_age():
	return randint(21, 65)

def _phone():
	phone_no = _numerify("8#######")
	return phone_no

def _random_numerical_string():
	num_str = _numerify("########")
	return num_str

def _user_name():  # Mix it up a bit so we don't hit a common username
	return Faker().user_name() + Faker().user_name()[:4]

def _user_id():
	num_str = _numerify("################")
	return num_str

def _lname_male():
	# name = FormElement._faker.last_name_male()
	name = choice(ascii_uppercase) + ''.join(choice(ascii_lowercase) for i in range(6))
	return name

def _fname_male():
	# name = FormElement._faker.first_name_male()
	name = choice(ascii_uppercase) + ''.join(choice(ascii_lowercase) for i in range(6))
	return name

def _birthdate():
	year = 0
	while year < 1980 or year > 1997:
		parts = Faker().date().split("-")
		parts.reverse()
		date = "/".join(parts)
		year = int(date.split("/")[-1])
	return date

class FormElement():

	_caller_prefix = "FormElement"

	# Static faker object to fill out values
	_faker = Faker()
	_phone_blacklist_chars = ["x", "-", ".", "(", ")", "+"]
	_DEFAULT_RULE = "1234567890987654321"

	### Rules to fill out inputs, based on their labels/attributes ###
	_text_rules = OrderedDict()
	# Names
	_text_rules[Regexes.EMAIL] = _gmail
	_text_rules[Regexes.FIRST_NAME] = _lname_male
	_text_rules[Regexes.LAST_NAME] = _fname_male
	_text_rules[Regexes.FULL_NAME] = _faker.name_male
	_text_rules[Regexes.USERNAME] = _user_id
	# _text_rules[Regexes.USERNAME] = _gmail # fixme
	_text_rules[Regexes.USERID] = _user_id
	_text_rules[Regexes.NAME_PREFIX] = _faker.prefix_male
	# Password
	_text_rules[Regexes.PASSWORD] = _password
	# Phones
	_text_rules[Regexes.PHONE_AREA] = _area_code
	_text_rules[Regexes.PHONE] = _phone
	# Dates
	_text_rules[Regexes.MONTH] = _faker.month
	_text_rules[Regexes.DAY] = _faker.day_of_month
	_text_rules[Regexes.YEAR] = _faker.year
	_text_rules[Regexes.BIRTHDATE] = _birthdate
	# Age
	_text_rules[Regexes.AGE] = _rand_age
	# Email, profile pics
	# _text_rules[Regexes.FILE] = _profile_pic()
	# Addresses
	_text_rules[Regexes.ZIPCODE] = _faker.zipcode
	_text_rules[Regexes.CITY] = _faker.city
	_text_rules[Regexes.COUNTRY] = _faker.country
	_text_rules[Regexes.STATE] = _faker.state
	_text_rules[Regexes.STREET] = _faker.street_name
	_text_rules[Regexes.BUILDING_NO] = _faker.building_number
	_text_rules[Regexes.ADDRESS] = _faker.street_address
	# SSN etc.
	_text_rules[Regexes.SSN] = _faker.ssn
	# Credit cards
	_text_rules[Regexes.CREDIT_CARD_EXPIRE] = _faker.credit_card_expire
	_text_rules[Regexes.CREDIT_CARD_CVV] = _faker.credit_card_security_code
	_text_rules[Regexes.CREDIT_CARD] = _faker.credit_card_number
	_text_rules[Regexes.ATMPIN] = _random_numerical_string

	# Company stuff
	_text_rules[Regexes.COMPANY_NAME] = _faker.company
	# END SPECIFIC REGEXES - START GENERIC ####
	# _text_rules[Regexes.NUMBER_COARSE] = _faker.numerify
	# _text_rules[Regexes.USERNAME_COARSE] = _user_name

	# Default
	_text_rules[_DEFAULT_RULE] = _faker.pystr
	_text_rules[Regexes.SMS] = _random_numerical_string

	_button_rules = Regexes.BUTTON
	_button_rules_forbidden = Regexes.BUTTON_FORBIDDEN
	# _select_rules = {
	# 	_DEFAULT_RULE: choice
	# }

	def __init__(self, driver, webElement):
		self._driver = driver
		self._web_element = webElement
		self._text = self._driver.get_text(self._web_element)
		self._str, self._str_tokenized = self._gen_element_str()
		self._input_rules = FormElement._text_rules
		self._button_rules = FormElement._button_rules
		self._button_rules_forbidden = FormElement._button_rules_forbidden
		self.translator = Translator()

	''' Get elements' all properties
	'''
	def get_element_str(self, tokenized = False):
		return self._str if not tokenized else self._str_tokenized

	def _gen_element_str(self):
		self._nodetag, self._etype, self._el_src, self._aria_label, self._eplaceholder, self._evalue, self._onclick, self._id, self._name, self._action = self._driver.get_element_property(self._web_element)
		self._autocomplete = self._driver.get_attribute(self._web_element, 'autocomplete')

		elset = [self._evalue, self._eplaceholder, self._name, self._id, self._aria_label, self._nodetag, self._etype, self._el_src, self._onclick, self._action, self._autocomplete] # the order is important, should look at important attributes first
		elset_clean = []
		if self._text is not None and self._text != "":
			elset_clean.append(self._text)
		for el in elset:
			if el is not None and el != "undefined" and el != "":
				elset_clean.append(el)
		return "%s|" % "|".join(elset_clean), elset_clean

	''' Check if the element is required, first by checking if the HTML `required` attribute is set and if not if it is present as a substring
		in the element's code
	'''
	def is_required(self):
		self._required = self._driver.is_required(self._web_element) \
						 or re.search(r"required|\*", self._driver.get_attribute(self._web_element, "outerHTML"), re.IGNORECASE)
		return self._required

	''' Get required length
	'''
	def _get_input_length(self):
		maxlength = self._driver.get_attribute(self._web_element, "maxlength")
		input_size = self._driver.get_property(self._web_element, "size")
		try:
			maxlength = int(maxlength) if maxlength else maxlength
		except ValueError:
			maxlength = None
		try:
			input_size = int(input_size) if input_size else input_size
		except ValueError:
			input_size = None

		if maxlength and maxlength <= 50 and maxlength > 0:
			input_length = maxlength
		elif maxlength is None and input_size and input_size <= 50 and input_size > 0:
			input_length = input_size
		else:
			input_length = 12

		return input_length

	''' Based on the input's type, labels, attributes and/or possible secondary labels, fill it out
	'''
	def fill(self, rule, radio_check = True, numeric_buttons = []):
		value = None
		etype = self._etype
		etag = self._driver.get_tag(self._web_element)
		readonly = self._driver.get_attribute(self._web_element, "readonly")

		if etype in ["hidden", "image", "submit", "reset"]: # skip hidden, buttons etc.
			pass

		elif etag == "select": # multiple choices
			value = self._fill_select()

		elif (etype == "radio" and radio_check) or etype == "checkbox": # checkbox
			self._fill_check()

		# inputs
		elif etag == "textarea" or etag == "input" or etype in ["text", "password", "number", "tel", "search", "email"]:
			inputLength = self._get_input_length()
			if not readonly:
				value = self._fill_text(rule=rule,
										inputLength = inputLength)
			else: # click numeric buttons to fill in
				value = self._fill_text_by_buttons(inputLength = inputLength,
												   numeric_buttons = numeric_buttons)

		# file upload
		elif etype == "file":
			try:
				self._driver.send_keys(self._web_element, _profile_pic())
			except Exception as e:
				Logger.spit("Exception {} when trying to fill out file input".format(e), warning=True, caller_prefix = FormElement._caller_prefix)

		# Date
		elif etype == "date" or etype == "datetime-local":
			value = self._driver.set_value(self._web_element, FormElement._faker.date())
		elif etype == "month":
			value = self._driver.set_value(self._web_element, "-".join(FormElement._faker.date().split("-")[:2]))
		elif etype == "week":
			value = self._driver.set_value(self._web_element, "-W".join(FormElement._faker.date().split("-")[:2]))
		elif etype == "time":
			value = self._driver.set_value(self._web_element, FormElement._faker.time())
		# others
		elif etype == "range":
			value = self._driver.set_value(self._web_element, str(choice(list(range(100)))))
		elif etype == "url":
			value = self._driver.set_value(self._web_element, FormElement._faker.url())

		self._value = value
		return value

	''' Decide pattern to fill out field
	'''
	def _decide_rule_inputs(self):
		etype = self._etype
		etag = self._driver.get_tag(self._web_element)
		fill_rule = None

		if etag == "textarea" or etag == "input" or etype in ["text", "password", "number", "tel", "search", "email"]:
			for lbl in self._str_tokenized:
				#try:
				#	lbl = self.translator.translate(lbl, dest='en').text
				#except:
				#	pass
				for rule in self._input_rules:
					if re.search(rule, lbl, re.IGNORECASE):
						fill_rule = rule
						break
				if fill_rule:
					break

		return fill_rule

	def _decide_input_rule_given_str(self, str_tokenized):
		fill_rule = None
		# try:
		# 	str_tokenized = self.translator.translate(str_tokenized, dest='en').text
		# except:
		# 	pass
		for rule in self._input_rules:
			if rule == FormElement._DEFAULT_RULE:
				continue
			if re.search(rule, str_tokenized, re.IGNORECASE):
				fill_rule = rule
				break
		return fill_rule

	def _decide_button_rule_given_str(self, str_tokenized):
		# try:
		# 	str_tokenized = self.translator.translate(str_tokenized, dest='en').text
		# except:
		# 	pass
		m_forbidden = re.search(self._button_rules_forbidden, str_tokenized, re.IGNORECASE)
		m = re.search(self._button_rules, str_tokenized, re.IGNORECASE)
		if m and m_forbidden is None:
			return True
		return False

	def _clear_text(self):
		try:
			self._driver.send_keys(self._web_element, Keys.CONTROL + "a")
			self._driver.send_keys(self._web_element, Keys.BACKSPACE)
			Logger.spit("Clearing the value for {}".format(self._web_element),
						debug=True, caller_prefix=FormElement._caller_prefix)
		except Exception:
			try:
				self._driver.set_value(self._web_element, "")
				Logger.spit("Clearing the value for {}".format(self._web_element),
							debug=True, caller_prefix=FormElement._caller_prefix)

			except Exception as e:
				Logger.spit("Error {} while clearing the value".format(e),
							warning=True, caller_prefix=FormElement._caller_prefix)

	def _fill_text_by_buttons(self, inputLength, numeric_buttons):
		value = []
		if len(numeric_buttons) == 0:
			return ''
		for _ in range(inputLength):
			ch = random.choice(range(len(numeric_buttons)))
			self._driver.click(numeric_buttons[ch])
			evalue = self._driver.get_text(numeric_buttons[ch])
			value.append(evalue)
		value = ''.join(value)
		return value

	def _fill_text(self, rule, inputLength = 12):

		# if rule is FormElement._DEFAULT_RULE or \
		if rule == FormElement._DEFAULT_RULE or rule == Regexes.SMS or \
			   rule == Regexes.ATMPIN or rule == Regexes.USERID or \
			   rule == Regexes.USERNAME:
			value = self._input_rules[rule]()[:inputLength] # cut by required length

		elif rule == Regexes.CREDIT_CARD_EXPIRE or rule == Regexes.BIRTHDATE or \
				 rule == Regexes.CREDIT_CARD or rule == Regexes.CREDIT_CARD_CVV or \
				 rule == Regexes.SSN: # keyin one by one, this will make sure that the date entered follows the specified format
			value = special_character_replacement(self._input_rules[rule]())
			for v in value:
				try:
					self._driver.send_keys(self._web_element, v)
					time.sleep(0.2) # allow some time lapse
				except Exception as e:
					continue
			return value

		else:
			value = self._input_rules[rule]()

		self._clear_text()
		try:
			self._driver.send_keys(self._web_element, value)  # send_keys use keyboard while set_value doesn't
		except Exception as e:
			Logger.spit("Exception {} when trying to fill out file input".format(e), warning=True,
						caller_prefix=FormElement._caller_prefix)
			value = self._driver.set_value(self._web_element, value)

		return value

	def _fill_check(self):
		self._driver.check_element(self._web_element)

	def _fill_select(self):
		select = Select(self._web_element)
		opts = select.options
		val = None
		idx = -1

		if len(opts) > 1: # If not match, just pick the last choice
			idx = len(opts)-1
			while idx >= 0:
				val = self._driver.get_attribute(opts[idx], "value").strip()
				if (not val) or val == "undefined" or val == "null":
					idx -= 1
				else:
					break

		elif len(opts) > 0:
			idx = 0

		if idx != -1:
			self._driver.set_selected_index(self._web_element, idx)
		return val

	'''Decide pattern for buttons
	'''
	def _decide_rule_buttons(self):
		etext = self._text
		etag = self._driver.get_tag(self._web_element)
		etype = self._etype
		evalue = self._evalue
		esrc = self._driver.get_attribute(self._web_element, "src")

		# Not a submission button
		if etag == 'input' and etype != "submit" and etype != "image" and etype != 'button':
			return False, False
		if etype == 'checkbox':
			return False, False

		# a normal button
		if etype != "image":
			matched_result1 = None
			matched_result2 = None
			matched_result1_bidden = None
			matched_result2_bidden = None

			if etext: # has text
				# try:
				# 	etext = self.translator.translate(etext, dest='en').text
				# except:
				# 	pass
				if '\n' not in etext:  # too long, dont bother
					matched_result1 = re.search(self._button_rules, etext, re.IGNORECASE)
					matched_result1_bidden = re.search(self._button_rules_forbidden, etext, re.IGNORECASE)

			if evalue: # has value
				# try:
				# 	evalue = self.translator.translate(evalue, dest='en').text
				# except:
				# 	pass
				matched_result2 = re.search(self._button_rules, evalue, re.IGNORECASE)
				matched_result2_bidden = re.search(self._button_rules_forbidden, evalue, re.IGNORECASE)

			relaxed_matching = (matched_result1_bidden is None) and (matched_result2_bidden is None)
			strict_matching = (matched_result1 is not None and matched_result1_bidden is None) or (matched_result2 is not None and matched_result2_bidden is None)
			return relaxed_matching, strict_matching

		elif esrc is not None: # a clickable image button
			return True, True

		return False, False

