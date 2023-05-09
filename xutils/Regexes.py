#!/usr/bin/python

from collections import OrderedDict

class Regexes():
	# e-mail
	EMAIL = r"(e(\-|_|\s)*)?mail(?!(\-|\_|\s)*(password|passwd|pass word|passcode|passwort))"

	# password
	PASSWORD = "password|passwd|pass word|passcode|passwort"
	# username
	USERNAME = "(u(s(e)?r)?|nick|display|profile)(\-|_|\s)*name"
	USERID = "^((u(s(e)?r)?|nick|display|profile|customer)(\-|_|\s)*)?id|identifi(ant|er)?|access(\-|_|\s)*code|account"

	# misc identifiers
	FULL_NAME = "full(\-|_|\s)?(name|nm|nom)|(celé jméno)"
	FIRST_NAME = "(f(irst|ore)?|m(iddle)?|pre)(\-|_|\s)*(name|nm|nom)"
	LAST_NAME = "(l(ast|st)?|s(u)?(r)?)(\-|_|\s)*(name|nm|nom)"
	NAME_PREFIX = "prefix"

	# Phones
	PHONE_AREA = "phone(\-|_|\s)*area|area(\-|_|\s)*code|phone(\-|_|\s)*(pfx|prefix|prfx)"
	PHONE = "mobile|phone|telephone|tel"

	# Dates
	MONTH = "month"
	DAY = "day"
	YEAR = "year"
	BIRTHDATE = "date|dob|birthdate|birthday|date(\-|_|\s)*of(\-|_|\s)*birth"

	# gender
	AGE = "(\-|_|\s)+age(\-|_|\s)+"
	GENDER = "gender|sex"

	# profile pics
	# FILE = "photo|picture"
	SMS = 'sms'

	# Addresses
	ADDRESS = "address"
	ZIPCODE = "(post(al)?|zip)(\-|_|\s)*(code|no|num)?"
	CITY = "city|town|location"
	COUNTRY = "countr"
	STATE = "stat|province"
	STREET = "street"
	BUILDING_NO = "(building|bldng|flat|apartment|apt|home|house)(\-|_|\s)*(num|no)"
	# SSN etc.
	SSN = "(ssn|vat|social(\-|_|\s)*sec(urity)?(\-|_|\s)*(num|no)?)"

	# Credit cards
	CREDIT_CARD = "(xxxx xxxx xxxx xxxx)|(0000 0000 0000 0000)|(Número de tarjeta)|(Číslo karty)|(cc(\-|_|\s)*(no|num))|(card(\-|_|\s)*(no|num))|(credit(\-|_|\s)*(no|num|card))|(card$)"
	CREDIT_CARD_EXPIRE = "expire|expiration|expiry|expdate|((cc|card|credit)(\-|_|\s)*date)|^exp$"
	CREDIT_CARD_CVV = "(sec(urity)?(\-|_|\s)*)?(cvv|csc|cvn)"
	ATMPIN = "atmpin|pin"

	# Company stuff
	COMPANY_NAME = "company|organi(z|s)ation|institut(e|ion)"
	#### END SPECIFIC REGEXES - START GENERIC ####
	# NUMBER_COARSE = "num|code"
	USERNAME_COARSE = "us(e)?r|login"

	OTHER_FORM = "link|search"

	SSO_SIGNUP_BUTTONS = "((create|register|make)|(new))\s*(new\s*)?(user|account|profile)"

	VERIFY_ACCOUNT = "((verify|activate)(\syour)?\s(account|e(-|\s)*mail|info))|((verification|activation) (e(-|\s)*mail|message|link|code|number))"
	VERIFIED_ACCOUNT = "(user(-|\s))?(account|profile)\s+(was|is|has)?(been)?(verified|activated|attivo)|(verification|activation)\s+(was|is|has)(been)?\s+(completed|done|successful)?"
	VERIFY_VERBS = "verify|activate"

	IDENTIFIERS = "%s|%s|%s|%s|%s" % (FULL_NAME, FIRST_NAME, LAST_NAME, USERNAME, EMAIL)
	IDENTIFIERS_NO_EMAIL = "%s|%s|%s|%s" % (FULL_NAME, FIRST_NAME, LAST_NAME, USERNAME)

	SUBMIT = "submit"
	LOGIN = "(log|sign)([^0-9a-zA-Z]|\s)*(in|on)|authenticat(e|ion)|/(my([^0-9a-zA-Z]|\s)*)?(user|account|profile|dashboard)"
	SIGNUP = "sign([^0-9a-zA-Z]|\s)*up|regist(er|ration)?|(create|new)([^0-9a-zA-Z]|\s)*(new([^0-9a-zA-Z]|\s)*)?(acc(ount)?|us(e)?r|prof(ile)?)|(forg(et|ot)|reset)([^0-9a-zA-Z]|\s)*((my|the)([^0-9a-zA-Z]|\s)*)?(acc(ount)?|us(e)?r|prof(ile)?|password)"
	SSO = "[^0-9a-zA-Z]+sso[^0-9a-zA-Z]+|oauth|openid"
	AUTH = "%s|%s|%s|%s|%s|auth|(new|existing)([^0-9a-zA-Z]|\s)*(us(e)?r|acc(ount)?)|account|connect|profile|dashboard|next" % (LOGIN, SIGNUP, SSO, SUBMIT, VERIFY_VERBS)
	LOGOUT = "(log|sign)(-|_|\s)*(out|off)"
	BUTTON = "suivant|make([^0-9a-zA-Z]|\s)*payment|^OK$|go([^0-9a-zA-Z]|\s)*(in)?to|sign([^0-9a-zA-Z]|\s)*in(?! with| via| using)|log([^0-9a-zA-Z]|\s)*in(?! with| via| using)|log([^0-9a-zA-Z]|\s)*on(?! with| via| using)|verify(?! with| via| using)|verification|submit(?! with| via| using)|ent(er|rar|rer|rance|ra)(?! with| via| using)|acces(o|sar|s)(?! with| via| using)|continu(er|ar)?(?! with| via| using)|connect(er)?(?! with| via| using)|next|confirm|sign([^0-9a-zA-Z]|\s)*on(?! with| via| using)|complete|valid(er|ate)(?! with| via| using)|securipass|登入|登录|登錄|登録|签到|iniciar([^0-9a-zA-Z]|\s)*sesión|identifier|ログインする|サインアップ|ログイン|로그인|시작하기|войти|вход|accedered|gabung|masuk|girişi|Giriş|เข้าสู่ระบบ|Přihlásit|mein([^0-9a-zA-Z]|\s)*konto|anmelden|ingresa|accedi|мой([^0-9a-zA-Z]|\s)*профиль|حسابي|administrer|cadastre-se|είσοδος|accessibilité|accéder|zaloguj|đăng([^0-9a-zA-Z]|\s)*nhập|weitermachen|bestätigen|zověřit|ověřit|weiter"
	BUTTON_FORBIDDEN = "guest|here we go|seek|looking for|explore|save|clear|wipe off|(^[0-9]+$)|(^x$)|close|search|(sign|log|verify|submit|ent(er|rar|rer|rance|ra)|acces(o|sar|s)|continu(er|ar)?)?.*(github|microsoft|facebook|google|twitter|linkedin|instagram|line)|keep([^0-9a-zA-Z]|\s)*me([^0-9a-zA-Z]|\s)*(signed|logged)([^0-9a-zA-Z]|\s)*(in|on)|having([^0-9a-zA-Z]|\s)*trouble|remember|subscribe|send([^0-9a-zA-Z]|\s)*me([^0-9a-zA-Z]|\s)*(message|(e)?mail|newsletter|update)|follow([^0-9a-zA-Z]|\s)*us|新規会員|%s" % SIGNUP
	CREDENTIAL_TAKING_KEYWORDS = "log(g)?([^0-9a-zA-Z]|\s)*in(n)?|log([^0-9a-zA-Z]|\s)*on|sign([^0-9a-zA-Z]|\s)*in|sign([^0-9a-zA-Z]|\s)*on|submit|(my|personal)([^0-9a-zA-Z]|\s)*(account|area)|come([^0-9a-zA-Z]|\s)*in|check([^0-9a-zA-Z]|\s)*in|customer([^0-9a-zA-Z]|\s)*centre|登入|登录|登錄|登録|iniciar([^0-9a-zA-Z]|\s)*sesión|identifier|(ログインする)|(サインアップ)|(ログイン)|(로그인)|(시작하기)|(войти)|(вход)|(accedered)|(gabung)|(masuk)|(girişi)|(Giriş)|(وارد)|(عضویت)|(acceso)|(acessar)|(entrar )|(เข้าสู่ระบบ)|(Přihlásit)|(mein konto)|(anmelden)|(me connecter)|(ingresa)|(accedi)|(мой профиль)|(حسابي)|(administrer)|(next)|(entre )|(cadastre-se)|(είσοδος)|(entrance)|(start now)|(accessibilité)|(accéder)|(zaloguj)|(đăng nhập)|weitermachen|bestätigen|zověřit|ověřit"
	PROFILE = "account|profile|dashboard|settings"

	CAPTCHA = "(re)?captcha"
	CONSENT = "consent|gdp"
	COOKIES_CONSENT = "agree|accept"

	URL = "(?:(?:https?|ftp)://)(?:\S+(?::\S*)?@)?(?:(?!10(?:\.\d{1,3}){3})(?!127(?:\.\d{1,3}){3})(?!169\.254(?:\.\d{1,3}){2})(?!192\.168(?:\.\d{1,3}){2})(?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))|(?:(?:[a-z\\x{00a1}\-\\x{ffff}0-9]+-?)*[a-z\\x{00a1}\-\\x{ffff}0-9]+)(?:\.(?:[a-z\\x{00a1}\-\\x{ffff}0-9]+-?)*[a-z\\x{00a1}\-\\x{ffff}0-9]+)*(?:\.(?:[a-z\\x{00a1}\-\\x{ffff}]{2,})))(?::\d{2,5})?(?:/[^\s]*)?"

	TIME = "([0-9]:){1,2}[0-9]"
	TIME_SCRIPT = "setHours|setMinutes|setSeconds"

	# try again error
	ERROR_TRY_AGAIN = ["try again|login failed|error logging in|login error|retry"]

	# username incorrect/not exist error
	ERROR_INCORRECT = ["(invalid|wrong|incorrect|unknown|no).*(id|credential|login|input|password|account|user(name)?|e(\-|_|\s)?mail|information|(pass)?code|(user([^0-9a-zA-Z]|\s)*)?id)(s)?",
						"(do(es)?|did)([^0-9a-zA-Z]|\s)*not match(([^0-9a-zA-Z]|\s)*our records)?",
						"limited access|verification failed|not registered|does not exist|access denied|coundn't find|you entered([^0-9a-zA-Z]|\s)*(isn't|doesn't)|(please)?([^0-9a-zA-Z]|\s)*enter a valid",
					   "(account|password|user(name)?|e(\-|_|\s)?mail|credentials|sms|code)([^0-9a-zA-Z]|\s)*(provided|given|input([^0-9a-zA-Z]|\s)*)?((is incorrect)|(are incorrect)|(isn't right)|(isn't correct)|(doesn't exist)|(does not exist)|(not valid)|(is invalid)|(not recognized)|(were not found))",
					    "(SMS-Code Fehler)|(SMS kód je neplatný)",
					   "code incorrectly|no user found|username already taken",
					   "(cannot|can't) be used|not allowed|must (contain|follow|specify)"
					   "captcha was not answered correctly"
					   ]

	# connection error
	ERROR_CONNECTION = ["connecting([^0-9a-zA-Z]|\s)*(to)?([^0-9a-zA-Z]|\s)*(mail)?([^0-9a-zA-Z]|\s)*server|connection is lost",
						# "(operation|page)([^0-9a-zA-Z]|\s)*((counldn't)|(could not)|cannot|(can not))([^0-9a-zA-Z]|\s)*be([^0-9a-zA-Z]|\s)*(completed|found)",
						# 'not found|forbidden|403|404|500|no permission|don\'t have permission'
						]

	# File related
	ERROR_FILE = ["processing([^0-9a-zA-Z]|\s)*(your)?([^0-9a-zA-Z]|\s)*download",
				  "file not found"]

	# anti-bot
	ERROR_BOT = ["(not a human)|captcha|(verify you are a human)|(press & hold)"]

class RegexesOriginal():
	# e-mail
	EMAIL = r"e(\-|_|\s)*mail"
	# misc identifiers
	FULL_NAME = r"full(\-|_|\s)*name"
	FIRST_NAME = r"(f(irst|ore)?|m(iddle)?)(\-|_|\s)*name"
	LAST_NAME = r"(l(ast|st)?|s(u)?(r)?)(\-|_|\s)*name"
	USERNAME = r"(u(s(e)?r)?|nick|display|profile)(\-|_|\s)*name"
	NAME_PREFIX = r"prefix"
	# password
	PASSWORD = "password|passwd"
	# Phones
	PHONE_AREA = r"phone(\-|_|\s)*area|area(\-|_|\s)*code|phone(\-|_|\s)*(pfx|prefix|prfx)"
	PHONE = r"(mobile|cell|tel|phone)"
	# Dates
	MONTH = r"month"
	DAY = r"day"
	YEAR = r"year"
	BIRTHDATE = r"birthdate|birthday|date(\-|_|\s)*of(\-|_|\s)*birth"
	# gender
	AGE = r"(\-|_|\s)+age(\-|_|\s)+"
	GENDER = r"gender|sex"
	# profile pics
	FILE = "photo|picture"
	# Addresses
	ADDRESS = r"addr"
	ZIPCODE = r"(post(al)?|zip)(\-|_|\s)*(code|no|num)"
	CITY = r"city|town|location"
	COUNTRY = r"country"
	STATE = r"state|province"
	STREET = r"street"
	BUILDING_NO = r"(building|bldng|flat|apartment|apt|home|house)(\-|_|\s)*(num|no)"
	# SSN etc.
	SSN = r"(ssn|vat|social(\-|_|\s)*sec(urity)?(\-|_|\s)*(num|no)?)"
	# Credit cards
	CREDIT_CARD = r"card(\-|_|\s)*(no|num)|credit(\-|_|\s)*(no|num|card)"
	CREDIT_CARD_EXPIRE = r"expire|expiration"
	CREDIT_CARD_CVV = r"sec(urity)?(\-|_|\s)*(no|num|cvv|code)"
	# Company stuff
	COMPANY_NAME = r"company|organi(z|s)ation|institut(e|ion)"
	#### END SPECIFIC REGEXES - START GENERIC ####
	NUMBER_COARSE = r"num|code"
	USERNAME_COARSE = r"us(e)?r|login"

	OTHER_FORM = r"link|search"

	SSO_SIGNUP_BUTTONS = r"((create|register|make)|(new))\s*(new\s*)?(user|account|profile)"

	VERIFY_ACCOUNT = r"((verify|activate)(\syour)?\s(account|e(-|\s)*mail|info))|((verification|activation) (e(-|\s)*mail|message|link|code|number))"
	VERIFIED_ACCOUNT = r"(user(-|\s))?(account|profile)\s+(was|is|has)?(been)?(verified|activated|attivo)|(verification|activation)\s+(was|is|has)(been)?\s+(completed|done|successful)?"
	VERIFY_VERBS = r"verify|activate"

	# IDENTIFIERS = r"%s|%s|%s|%s|%s" % (FULL_NAME, FIRST_NAME, LAST_NAME, USERNAME, EMAIL)
	IDENTIFIERS = r"%s|%s|%s|%s|%s" % (FULL_NAME, FIRST_NAME, LAST_NAME, USERNAME, EMAIL)
	IDENTIFIERS_NO_EMAIL = r"%s|%s|%s|%s" % (FULL_NAME, FIRST_NAME, LAST_NAME, USERNAME)

	SUBMIT = r"submit"
	LOGIN = r"(log|sign)([^0-9a-zA-Z]|\s)*(in|on)|authenticat(e|ion)|/(my([^0-9a-zA-Z]|\s)*)?(user|account|profile|dashboard)"
	SIGNUP = r"sign([^0-9a-zA-Z]|\s)*up|regist(er|ration)?|(create|new)([^0-9a-zA-Z]|\s)*(new([^0-9a-zA-Z]|\s)*)?(acc(ount)?|us(e)?r|prof(ile)?)"
	SSO = r"[^0-9a-zA-Z]+sso[^0-9a-zA-Z]+|oauth|openid"
	AUTH = r"%s|%s|%s|auth|(new|existing)([^0-9a-zA-Z]|\s)*(us(e)?r|acc(ount)?)|account|connect|profile|dashboard" % (LOGIN, SIGNUP, SSO)
	LOGOUT = r"(log|sign)(-|_|\s)*(out|off)"

	PROFILE = r"account|profile|dashboard|settings"

	CAPTCHA = r"(re)?captcha"
	CONSENT = r"consent|gdpr"
	COOKIES_CONSENT = r"agree|accept"

	URL = r"(?:(?:https?|ftp)://)(?:\S+(?::\S*)?@)?(?:(?!10(?:\.\d{1,3}){3})(?!127(?:\.\d{1,3}){3})(?!169\.254(?:\.\d{1,3}){2})(?!192\.168(?:\.\d{1,3}){2})(?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))|(?:(?:[a-z\\x{00a1}\-\\x{ffff}0-9]+-?)*[a-z\\x{00a1}\-\\x{ffff}0-9]+)(?:\.(?:[a-z\\x{00a1}\-\\x{ffff}0-9]+-?)*[a-z\\x{00a1}\-\\x{ffff}0-9]+)*(?:\.(?:[a-z\\x{00a1}\-\\x{ffff}]{2,})))(?::\d{2,5})?(?:/[^\s]*)?"

if __name__ == "__main__":
	import re
	# print bool(re.search(Regexes.URL, "http://127.0.0.1"))

	s = "1; mode=block; report=http://139.91.70.121"
	r = "([0|1])\s*(\s*;\s*mode\s*=\s*block)?(\s*;\s*report\s*=\s*%s)?" % Regexes.URL
	# r = "([0|1])\s*(\s*;\s*mode\s*=\s*block)?(\s*;\s*report\s*=\s*.*)?"

	m = re.match(r, s, re.IGNORECASE)
	print(m)
	if m:
		print(m.group(0))
		print(m.group(1))
		print(m.group(2))
		print(m.group(3))
		print(m.groups())