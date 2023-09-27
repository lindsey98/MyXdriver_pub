#!/usr/bin/python
import logging
from selenium.webdriver.remote.remote_connection import LOGGER

LOGGER.setLevel(logging.WARNING)
import selenium.common.exceptions
from selenium.webdriver.remote.webdriver import WebDriver
# from selenium.webdriver import Chrome, Firefox
from selenium.webdriver import Firefox
from seleniumwire.webdriver import Chrome
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.command import Command
from selenium.common.exceptions import *
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from xdriver.xutils.URLUtils import URLUtils
from xdriver.xutils.Logger import Logger
from xdriver.xutils.Regexes import Regexes
from xdriver.xutils.Exceptions import *
from xdriver.xutils.proxy.ProxyWrapper import ProxyWrapper
from xdriver.security.SecurityAuditor import SecurityAuditor
from xdriver.xutils.TextMatching import *
from xdriver.xutils.forms import Form
from xdriver.xutils.forms import FormOriginal

from time import time, sleep
import re
import os
import json
import psutil
import signal
import shutil
from uuid import uuid4
from copy import deepcopy
import urllib
from datetime import datetime
from PIL import Image
import io
import base64
import numpy as np
import json
import os
import tempfile
from functools import reduce

CHROME = "chrome"
OPERA = "opera"
FIREFOX = "firefox"


class XDriver(Chrome, Firefox):
    _caller_prefix = "XDriver"
    _forbidden_paths = ["/", "/home", "~/Desktop"]  # Poor method, but if you do it you deserve it

    _abs_path = os.path.dirname(os.path.abspath(__file__))
    _abs_profiles_path = "/tmp"

    _compatible_browsers = [
        CHROME,
        FIREFOX,
        OPERA
    ]

    _browser_instance_type = None

    ''' A regex of blacklisted suffixes that we might not want to consider, e.g. during a crawl
    '''
    _forbidden_suffixes = r"\.(mp3|wav|wma|ogg|mkv|zip|tar|xz|rar|z|deb|bin|iso|csv|tsv|dat|txt|css|log|sql|xml|sql|mdb|apk|bat|bin|exe|jar|wsf|fnt|fon|otf|ttf|ai|bmp|gif|ico|jp(e)?g|png|ps|psd|svg|tif|tiff|cer|rss|key|odp|pps|ppt|pptx|c|class|cpp|cs|h|java|sh|swift|vb|odf|xlr|xls|xlsx|bak|cab|cfg|cpl|cur|dll|dmp|drv|icns|ini|lnk|msi|sys|tmp|3g2|3gp|avi|flv|h264|m4v|mov|mp4|mp(e)?g|rm|swf|vob|wmv|doc(x)?|odt|rtf|tex|txt|wks|wps|wpd)$"

    ''' Configuration options for XDriver. Should always be set before booting the browser.
        For anything that is `enabled : True` and no other specific changes are made, XDriver's defaults will be used '''
    _base_config = {
        "browser": {
            # High-level browser options. These will be translated to actual browser-specific options by the selected subclass
            "enabled": True, # If False, don't use any command line arguments in browser (other than proxy/tor stuff, if enabled)
            "no_ssl_errors": True,  # Supress browser-level SSL errors
            "disable_notifications": True,  # Disable push notifications
            "maximized": True,  # Start browser window maximized
            "no_default_browser_check": True,  # Prevent popup to make browser the default (if this is a fresh instance)
            "disable_cache": True,  # Disable all possible levels of cache
            "profile": None,  # Use specific profile. If None, a temporary new one will be generated
            "headless": True,  # Start headless
            "virtual": False,  # Use vrtual display
            "vpn": False,  # Opera built-in VPN -- Not currently supported
            "no_blink_feature": True
        },
        "proxy": {  # User custom proxy
            "enabled": False,
            "scheme": "http",
            "host": "127.0.0.1",
            "port": None,  # This is required
        },
        "internal_proxy": {
            # This is for the proxy used for internal functionality (e.g. extract redirection flows, security policy evaluation etc.). No methods are exposed to control this,
            # so if you mess with this, make sure you know what you're doing
            "enabled": False,
            "scheme": "http",
            "host": "127.0.0.1",
            "port": None,  # If None and proxy is enabled, the port will be reserved dynamically
            "strip_media": True
        },
        "tor": {
            "enabled": False,
            "scheme": "socks5",
            "host": "127.0.0.1",
            "port": 9050,
            "ctrl_port": 9051
        },
        "security": {
            # If you plan to evaluate security policies / response headers, this should be enabled. "internal_proxy" will be enabled automatically
            "enabled": False,
        },
        "xdriver": {  # High-level XDriver/Selenium specific options
            "max_retries": 3,  # How many times to retry an operation by default, before giving up
            "timeout": 10,  # Page load timeout in seconds
            "heartbeat_url": "http://google.com",
            # Used when booting the browser for a dummy request, to make sure everything works. Choose something that is generally responsive.
            "max_boot_retries": 3,
            "scripts": "",
            "scripts_after_load": ""
        }
    }

    _all_children_proc = set()
    _subprocesses = set(["mitmdump",
                         "Xvfb"])  # XDriver's subprocesses (depending on configuration). Browser process will be handled by undelrying Selenium code

    _scripts_file = os.path.join(_abs_path, "js/scripts.js")  # Main JS lib needed by XDriver
    with open(_scripts_file, "r") as fp:
        _base_config["xdriver"]["scripts"] += fp.read()
    _original_config = deepcopy(
        _base_config)  # Maintain a stable copy of the default, base config to use after setting up individual instances

    @classmethod
    def get_config(cls):
        return cls._base_config

    @classmethod
    def set_config(cls, config):  # Set XDriver config directly, if you don't want to call a bunch of methods
        cls._base_config.update(
            config)  # Update the config (not complete overwrite). We want to maintain the main structure and only pass the user defined options

    @classmethod
    def restore_base_config(cls):
        XDriver._base_config = deepcopy(XDriver._original_config)

    @classmethod
    def _set_config_enabled(cls, feature, enabled):
        if feature not in cls._base_config:
            raise XDriverException("Unknown configuration option: %s" % feature, caller_prefix=XDriver._caller_prefix)
        cls._base_config[feature]["enabled"] = enabled
        if not enabled:  # IF disabling the feature, we need to turn off all options
            for option in cls._base_config[feature]:
                cls._base_config[feature][option] = False

    @classmethod
    def _set_config_options(cls, feature, **kwargs):
        cls._set_config_enabled(feature, True)
        for param in kwargs:  # Only update with given values. If any of them is not provided, use the default
            if param in cls._base_config[feature]: cls._base_config[feature][param] = kwargs[param]

    @classmethod
    def enable_browser_args(cls, **kwargs):
        cls._set_config_options("browser", **kwargs)

    @classmethod
    def enable_internal_proxy(cls, **kwargs):
        cls._set_config_options("internal_proxy", **kwargs)

    @classmethod
    def enable_proxy(cls, **kwargs):
        cls._set_config_options("proxy", **kwargs)

    @classmethod
    def enable_tor(cls, **kwargs):
        cls._set_config_options("tor", **kwargs)

    @classmethod
    def enable_security_checks(cls, **kwargs):
        cls._set_config_options("security", **kwargs)
        cls._set_config_enabled("internal_proxy", True)  # Internal proxy must be enabled for security checks

    @classmethod
    def disable_browser_args(cls):
        cls._set_config_enabled("browser", False)

    @classmethod
    def disable_internal_proxy(cls):
        cls._set_config_enabled("internal_proxy", False)

    @classmethod
    def disable_proxy(cls):
        cls._set_config_enabled("proxy", False)

    @classmethod
    def disable_tor(cls):
        cls._set_config_enabled("tor", False)

    @classmethod
    def disable_security_checks(cls):
        cls._set_config_enabled("security", False)
        cls._set_config_enabled("internal_proxy", False)

    @classmethod
    def set_verbose(cls, verbose=True):
        Logger.set_verbose(verbose)

    @classmethod
    def set_timeout(cls, timeout):
        cls._base_config["xdriver"]["timeout"] = timeout

    @classmethod
    def set_max_retries(cls, max_retries):
        cls._base_config["xdriver"]["max_retries"] = max_retries

    @classmethod
    def set_heartbeat_url(cls, heartbeat_url):
        cls._base_config["xdriver"]["heartbeat_url"] = heartbeat_url

    @classmethod
    def set_headless(cls):
        cls._base_config["browser"]["headless"] = True

    ''' Load the list of JS files (absolute paths), to be evaluated on each new document (before anything else)
    '''

    @classmethod
    def set_scripts(cls, scripts_list):
        for script in scripts_list:
            with open(script, "r") as fp:
                XDriver._base_config["xdriver"]["scripts"] += "\n\n" + fp.read()  # Append JS

    ''' Load the list of JS files (absolute paths), to be evaluated on each new document (after loading the page)
    '''

    @classmethod
    def set_scripts_after_load(cls, scripts_list):
        for script in scripts_list:
            with open(script, "r") as fp:
                XDriver._base_config["xdriver"]["scripts_after_load"] += "\n\n" + fp.read()  # Append JS

    @classmethod
    def boot(cls, **kwargs):
        for arg in kwargs:
            if kwargs[arg] and arg in XDriver._compatible_browsers:
                XDriver._browser_instance_type = arg
                break
        if not XDriver._browser_instance_type:
            raise XDriverException("Need to specify a browser [%s = True]" % "|".join(XDriver._compatible_browsers),
                                   caller_prefix=XDriver._caller_prefix)

        if XDriver._base_config["tor"]["enabled"] and XDriver._base_config["proxy"]["enabled"]:
            Logger.spit(
                "Custom proxy and TOR are both enabled. You must configure your proxy to route everything through your TOR endpoint.",
                warning=True, caller_prefix=XDriver._caller_prefix)
        elif XDriver._base_config["tor"]["enabled"] and XDriver._base_config["security"]["enabled"]:
            Logger.spit("TOR and internal proxy are both enabled. Not implemented yet; TOR will be disabled.",
                        warning=True, caller_prefix=XDriver._caller_prefix)
            XDriver.disable_tor()

        from xdriver.browsers.CXDriver import CXDriver
        from xdriver.browsers.FXDriver import FXDriver
        from xdriver.browsers.OXDriver import OXDriver

        if XDriver._base_config["browser"]["enabled"] and XDriver._base_config["browser"]["vpn"]:
            if XDriver._browser_instance_type != OPERA:
                Logger.spit(
                    "Built-in VPN is only supported by Opera. You are using: %s" % XDriver._browser_instance_type,
                    warning=True, caller_prefix=XDriver._caller_prefix)
                XDriver._base_config["browser"]["vpn"] = False  # disable it
            else:
                Logger.spit("Opera's built-in VPN is not currently supported", warning=True,
                            caller_prefix=XDriver._caller_prefix)

        constructor = None
        if XDriver._browser_instance_type == CHROME:
            constructor = CXDriver
        elif XDriver._browser_instance_type == FIREFOX:
            constructor = FXDriver
        elif XDriver._browser_instance_type == OPERA:
            constructor = OXDriver

        boot_retries = 0
        while boot_retries < XDriver._base_config["xdriver"]["max_boot_retries"]:
            try:
                driver = constructor(refs=kwargs.pop("refs", {}), redirects=kwargs.pop("redirects", {}),
                                     retries=kwargs.pop("retries", {}))
                driver._config = deepcopy(XDriver._base_config)  # Keep used config for reboots and crash recoveries
            except Exception as e:
                Logger.spit("Error while starting XDriver.", error=True, caller_prefix=XDriver._caller_prefix)
                print(e)
                raise
                boot_retries += 1
                if boot_retries < XDriver._base_config["xdriver"]["max_boot_retries"]:
                    Logger.spit("Retrying..", caller_prefix=XDriver._caller_prefix)
                    continue
                XDriver.restore_base_config()
                return False  # Max retries exceeded, abort

            Logger.spit("Browser booted!", caller_prefix=XDriver._caller_prefix)
            XDriver.restore_base_config()  # Restore base config so other instances can be created and configured (differently)

            if driver._config["browser"]["vpn"]:
                driver.enable_vpn()

            XDriver._browser_instance_type = None  # Reset
            stealth(driver,
                    languages=["en-US", "en"],
                    vendor="Google Inc.",
                    platform="Linux",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True
                    )
            return driver

    def __init__(self, *args, **kwargs):
        ''' A dictionary used to store key value pairs of the form: "<WebElement Object>" : (method, *args, **kwargs, element_idx, return_length).
        Whenever a 'find_element_by_*' method is called, the final 'find_element(...)' equivalent will be stored as the value (with its args
        and possible kwargs), together with the reference of the WebElement to be returned (if found) as the key. If a StaleElementReferenceException
        or NoSuchElementException is later raised on that specific element, XDriver will re-invoke that method and try to refetch the element in question.

        Same applies for 'find_elements_by_*' methods, but in this case the underlying 'find_elements(...)' will also simulate a 'find_element_by_xpath'
        on each element in the returned list (which is what will be stored in this dict). This way, upon a StaleElementReferenceException, the stale object
        will be restored with the correct instance, otherwise, if we stored the whole list of elements and the actual 'find_elements' method, in case the
        returned list of elements does not match the length of the previously returned list, the exception should be raised, since we woudln't be sure about which
        element is the correct one. '''
        self._REFS = kwargs.get("refs", {})

        ''' A dictionary used to store key value pairs of the form: "http://example.com" : <WebElement Object>.
            Whenever a `get` method is invoked, the given URL will be stored as the key and the landing page's <html> WebElement will be stored as the value.
            The caller can then ask if the driver has been redirected from the specified URL and the stored WebElement will be checked for staleness.
            If the landing URL differs from the given URL, it will also be stored a a separate entry  '''
        self._REDIRECTS = kwargs.get("redirects", {})

        ''' Retry mode for invoked operations. Each method should have its own counter so they don't get mixed up
        '''
        self._RETRIES = kwargs.get("retries", {})

        self._browser_type = XDriver._browser_instance_type

        from xdriver.browsers.CXDriver import CXDriver  # Limited scope imports
        from xdriver.browsers.FXDriver import FXDriver
        from xdriver.browsers.OXDriver import OXDriver

        if isinstance(self, CXDriver) or isinstance(self, OXDriver):  # Chrome, Opera
            # os.chmod(kwargs.get("executable_path"), 0o755)
            Chrome.__init__(self,
                            ChromeDriverManager().install(), # install latest version
                            # executable_path=kwargs.get("executable_path"),
                            chrome_options=kwargs.get("chrome_options"),
                            desired_capabilities=kwargs.get("desired_capabilities"))

        elif isinstance(self, FXDriver):  # Firefox
            Firefox.__init__(self, executable_path=kwargs.get("executable_path"),
                             firefox_profile=kwargs.get("firefox_profile"), options=kwargs.get("options"))

        self._children_proc = set([child for child in psutil.Process(os.getpid()).children(recursive=True) if
                                   child not in XDriver._all_children_proc])  # Used later to clean exit
        XDriver._all_children_proc = XDriver._all_children_proc.union(self._children_proc)

    def get_profile(self):
        return self._profile

    def force_cookies(self, rules={}, enabled=True):
        if not self._proxy:
            raise XDriverException("Cannot force cookies. \"internal_proxy\" option must be enabled.",
                                   caller_prefix=XDriver._caller_prefix)
        self._proxy.force_cookies(rules=rules, enabled=enabled)

    def get_redirection_flow(self, url):
        if not self._proxy:
            raise XDriverException("Cannot get HTTP redirection flow. \"internal_proxy\" option must be enabled.",
                                   caller_prefix=XDriver._caller_prefix)
        self._proxy.redirection_mode(url)
        self.get(url)
        return self._proxy.get_redirection_flow()

    def spoof_headers(self, headers={}, domain_headers={}, reset=False, enabled=True):
        if not self._proxy:
            raise XDriverException("Cannot spoof headers. \"internal_proxy\" option must be enabled.",
                                   caller_prefix=XDriver._caller_prefix)
        self._proxy.spoof_headers(headers=headers, domain_headers=domain_headers, reset=reset, enabled=enabled)

    # Evaluate given policies (if 'all = True' is given, all supported policies will be evaluated)
    # Might want to disable CORS (`cors = False`) if not required, since it will take some time to evaluate
    # Can also pass custom redirection flow that was captured previously with `json_flow`. No CORS checking is possible with this option
    def evaluate_policies(self, url, json_flow=None, **kwargs):
        sec_auditor = SecurityAuditor(self, url)
        policies = {}
        if kwargs.pop("all", False):
            policies = {policy: True for policy in sec_auditor._policies}

        for arg in kwargs:  # Still consider the rest of the kwargs, since some checks might be explicitly disabled, e.g. CORS
            policies[arg] = kwargs[arg]

        return sec_auditor.evaluate(json_flow=json_flow, policies=policies)

    ''' Auxiliary method to easily run a task (`task_func`) in different browser setups. If no `drivers` list is given, all supported browsers will be used
        with default configurations. This can be further tuned to exclude one of the supported browsers by setting it to False in the `browsers` param. If the
        user wants to fine-tune the configuration of each browser instance under test, they should configure and boot each one before calling this method and
        pass the `drivers` list in the form: [{"browser" : str("browser name/unique ID"), "driver" : <XDriver instance>}, ...].
        The `task_func` function should always accept an XDriver instance as the first argument.
        If intructed to `quit` each instance will immediately shutdown after completing the task. 
        The results are formated as a dict, of the form {"browser name/unique ID" : {"driver" : <XDriver instance>, "ret" : <task_func's return value>}, ...}  '''

    @classmethod
    def cross_browser_run(cls, task_func, *args, **kwargs):
        drivers = kwargs.pop("drivers", [])
        browsers = kwargs.pop("browsers", {"chrome": True, "firefox": True, "opera": True})
        quit = kwargs.pop("quit", True)

        if not drivers:  # If no booted drivers are provided, default to check all supported browsers w/ default configs
            for browser in browsers:
                if not browsers[browser]:  # Except if explicitly disabled
                    continue
                Logger.spit("Booting %s" % browser, caller_prefix=XDriver._caller_prefix)
                driver = XDriver.boot(chrome=browser == CHROME, opera=browser == OPERA, firefox=browser == FIREFOX)
                drivers.append({"browser": browser, "driver": driver})

        results = {}
        for driver in drivers:
            ret = task_func(driver["driver"], browser=driver["browser"], *args, **kwargs)
            results[driver["browser"]] = {"driver": driver["driver"], "ret": ret}
            if quit:
                driver["driver"].quit()

        return results

    def enter_retry(self, method, max_retries=10):
        retries, max_retries = self._RETRIES.get(method, [0,
                                                          max_retries])  # Necessary so nested `_invokes` of the same method won't reset the retry counter
        self._RETRIES[method] = [retries, max_retries]
        if retries <= max_retries:
            return True
        return False

    def exit_retry(self, method):
        self._RETRIES.pop(method, None)  # Only need to pop the method name

    ''' Quit browser, stop virtual display if used, kill child processes (should only be the proxy, if used),
        clear StaleElement handling refs and delete profile if instructed '''

    def quit(self, clear_refs=True, delete_profile=True, delete_proxy_config=True):
        try:
            super(XDriver,
                  self).quit()  # First quit and then delete the temp profile, otherwise the browser will re-create it
        except Exception as e:
            Logger.spit("Exception while quiting browser", warning=True, caller_prefix=self._caller_prefix)
            Logger.spit("%s" % stringify_exception(e), warning=True, caller_prefix=self._caller_prefix)
        finally:
            if self._virtual_display:  # Make sure Xvfb subprocess exits gracefully
                self._virtual_display.stop()
            self._kill_child_processes()  # No more grace

        if clear_refs:
            self.clear_refs()  # Clear StaleElement handling references

        if delete_proxy_config and self._config["internal_proxy"]["enabled"]:
            self._proxy.remove_config()

        if delete_profile:
            if self._profile in XDriver._forbidden_paths:
                # Logger.spit("Are you nuts? You were about to delete %s" % self._profile, warning = True, caller_prefix = self._caller_prefix)
                raise XDriverException("Forbidden custom profile: %s" % self._profile,
                                       caller_prefix=self._caller_prefix)
            try:
                shutil.rmtree(self._profile, ignore_errors=True)
            except Exception as e:
                Logger.spit("Could not delete custom chrome profile: %s" % self._profile, warning=True,
                            caller_prefix=self._caller_prefix)
                Logger.spit("%s" % stringify_exception(e), warning=True, caller_prefix=self._caller_prefix)

    def _kill_child_processes(self):  # What it says
        killed = set()
        for child in self._children_proc:
            try:
                if not any([subproc in child.name() for subproc in
                            XDriver._subprocesses]):  # Don't kill anything other than the specified subprocesses
                    continue
                killed.add(child.name())
                # We want to send a SIGINT to the mitmdump subprocess, since SIGKIILL-ing it leaves unclean directories in /tmp
                if 'mitmdump' in child.name():
                    child.send_signal(signal.SIGINT)
                else:
                    child.kill()
            except Exception as e:
                pass
        Logger.spit("Killed (%s): %s" % (len(killed), str(killed)), debug=True, caller_prefix=XDriver._caller_prefix)

    ''' Make sure the browser (and its proxy) is working properly
    '''

    def heartbeat(self):
        try:
            # So, apparently the driver sometimes needs a dummy operation to boot, otherwise the heartbeat might fail consecutively.
            # Need to investigate this more and find a more elegant workaround
            # scr_filename = "/tmp/scr_%s.png" % str(uuid4())
            # self.save_screenshot(scr_filename) # So,
            # os.remove(scr_filename) # remove screenshot file if booted
            super(XDriver, self).get(XDriver._base_config["xdriver"][
                                         "heartbeat_url"])  # Do not `_invoke` it, we want to see the exception if raised
            self.set_page_load_timeout(
                XDriver._base_config["xdriver"]["timeout"])  # restore page load timeout after successful heartbeat
            self.set_script_timeout(
                XDriver._base_config["xdriver"]["timeout"])
            self.implicitly_wait(
                XDriver._base_config["xdriver"]["timeout"])
            return True
        except TimeoutException as e:
            return False

    # Custom method invoker to globally handle any exceptions that come up
    def _invoke(self, method, *args, **kwargs):
        original_kwargs = dict(kwargs)  # In case we re-_invoke it, we need the original kwargs
        ex = None
        ret_val = None

        try:
            if kwargs.pop("retry", True):  # By default, retry all methods if possible, otherwise explicitly requested
                self.enter_retry(method, max_retries=kwargs.pop("max_retries", self._config["xdriver"]["max_retries"]))
            web_element = kwargs.pop("webelement", None)
            ret_val = method(*args, **kwargs)
            if method == super(XDriver,
                               self).get: ret_val = True  # Need to explicitly set the ret value for WebDriver's get
            self.exit_retry(method)  # The operation completed, no need to keep the retry counter
            return ret_val
        except UnexpectedAlertPresentException as ex:
            self._invoke_exception_handler(self._UnexpectedAlertPresentException_handler)
            if method == super(XDriver, self).get:  # Nothing more to do for a `get`
                ret_val = True
        except (InvalidSwitchToTargetException, NoSuchFrameException, NoSuchWindowException) as ex:
            if len(self.window_handles) == 0:  # If no windows remain for some reason, raise it
                raise
            self.switch_to_default_content()  # Return to the default handle
            ret_val = False
        except (InvalidSelectorException) as ex:
            ret_val = False
        except (InvalidElementStateException, ElementNotSelectableException, ElementNotVisibleException,
                MoveTargetOutOfBoundsException) as ex:
            ret_val = False  # No need to retry the operation since these won't change
        except NoSuchElementException:  ## Experimental ##
            ret_val = False
        except (StaleElementReferenceException, NoSuchElementException) as ex:
            # Check _REFS for given WebElement.
            if not self._invoke_exception_handler(self._StaleElementReference_handler, web_element):
                raise
            ret_val = False
        except (TimeoutException, WebDriverException, ErrorInResponseException, RemoteDriverServerException,
                InvalidCookieDomainException, UnableToSetCookieException, ImeNotAvailableException,
                ImeActivationFailedException) as ex:
            str_ex = stringify_exception(ex)
            if ex is TimeoutException or any([crash in str_ex for crash in self._recoverable_crashes]):
                # Reboot browser, maintain state and retry the operation
                if not self._invoke_exception_handler(self._TimeoutException_handler):
                    raise
                if method != super(XDriver, self).get: self.get(
                    self._last_url)  # If it was `get`, it will be retried later on. For anything else, we need to manually go back to the last known URL
                ret_val = False
            else:
                # The JS script setup we did on page load got screwed over by an async page load
                if "is not defined" in str_ex:
                    self.setup_page_scripts()
                else:
                    raise

        retries, max_retries = self._RETRIES.get(method, [None, None])
        # If we are not in retry mode OR if the retries have exceeded the threshold, either return a default value (if set) or raise the exception to the caller
        if method not in self._RETRIES or retries >= max_retries:
            self.exit_retry(method)
            if ret_val != None:  # If a return value has been set, return it instead of raising the exception
                return ret_val
            raise  # These are considered fatal

        # About to re-invoke method. Increment retry counter
        self._RETRIES[method][0] += 1
        Logger.spit("Retrying for the {}th time...".format(self._RETRIES[method][0]), debug=True,
                    caller_prefix=XDriver._caller_prefix)
        # Logger.spit("Retrying for: %s || Because: %s" % (method, stringify_exception(ex, strip = True)), debug = True, caller_prefix = self._caller_prefix)
        return self._invoke(method, *args, **original_kwargs)

    # Exception handler invoker
    def _invoke_exception_handler(self, handler, *args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except UnexpectedAlertPresentException:
            self._invoke_exception_handler(self._UnexpectedAlertPresentException_handler)
        except NoAlertPresentException:  # This was raised during the _UnexpectedAlertPresentException_handler call.
            self.execute_script("window.alert = null;")
        except TimeoutException:
            return False

    ''' The caller must explicitly call this when the stored references are no longer needed (e.g. when starting to evaluate a different domain)
    '''

    def clear_refs(self):
        self._REFS = {}

    ### Exception handlers ###
    '''
    '''

    def _StaleElementReference_handler(self, webelement):
        Logger.spit("Handling StaleElementReferenceException", debug=True, caller_prefix=self._caller_prefix)
        element_ref = id(webelement)
        if element_ref not in self._REFS:
            Logger.spit("Stale WebElement not seen before ", warning=True, caller_prefix=self._caller_prefix)
            return False
        method, args, kwargs = self._REFS[element_ref]
        kwargs["timeout"] = 3  # add some max timeout
        new_element = method(*args, **kwargs)  # refetch element
        if not new_element:  # The element is not in the DOM, it's not just stale
            Logger.spit("Element could not be refetched ", warning=True, caller_prefix=self._caller_prefix)
            Logger.spit("%s" % str(self._REFS[element_ref]), warning=True, caller_prefix=self._caller_prefix)
            return False

        webelement.__dict__.update(new_element.__dict__)  # Transparently update old webelement's reference
        return True

    ''' If a timeout occurs we need to restore the browser instance, since the chromedriver is unresponsive to any interaction with the page.
        Interestingly, `webdriver.quit` and a few other non-page specific commands work fine. '''

    def _TimeoutException_handler(self):
        Logger.spit("Handling browser crash. Will try to restore XDriver.", warning=True,
                    caller_prefix=self._caller_prefix)
        self.reboot(clear_refs=False, delete_profile=False,
                    delete_proxy_config=False)  # We don't want to clear the _REFS, delete the profile or the proxy config
        return True

    ''' Switch to the alert, dismiss it, override alert func to null and switch back to page
    '''

    def _UnexpectedAlertPresentException_handler(self):
        Logger.spit("Handling UnexpectedAlertPresentException", warning=True, caller_prefix=self._caller_prefix)
        alert = self.switch_to.alert
        alert.dismiss()
        self.execute_script("window.alert = null;")  # Try to prevent the page from popping any more alerts
        self.switch_to.default_content()

    ''' Reboot browser with new profile. Transparent to callers
    '''

    def reload_profile(self, profile, delete_profile=True):
        Logger.spit("Reloading profile to: %s" % profile, caller_prefix=self._caller_prefix)
        self._config["browser"]["profile"] = profile
        self.reboot(clear_refs=False, delete_profile=delete_profile,
                    delete_proxy_config=False)  # Don't clear `_REFS`, but delete old profile if instructed; keep proxy config
        self.get(self._last_url)  # Mobfuscate_inputaybe this is not necessary

    ''' Graceful exit browser and reboot with appropriate settings (i.e. same proxy port, virtual display, same or different profile)
    '''

    def reboot(self, clear_refs=False, delete_profile=False, delete_proxy_config=False):
        Logger.spit("Rebooting browser..", warning=True, caller_prefix=self._caller_prefix)
        self.quit(clear_refs=clear_refs, delete_profile=delete_profile,
                  delete_proxy_config=delete_proxy_config)  # graceful exit (if possible)

        from xdriver.browsers.CXDriver import CXDriver
        from xdriver.browsers.FXDriver import FXDriver
        from xdriver.browsers.OXDriver import OXDriver

        XDriver._base_config = self._config  # Setup the base config to be used by the boot procedure
        new_instance = XDriver.boot(chrome=self._browser_type == CHROME, opera=self._browser_type == OPERA,
                                    firefox=self._browser_type == FIREFOX, refs={} if clear_refs else self._REFS,
                                    redirects={} if clear_refs else self._REDIRECTS,
                                    retries={} if clear_refs else self._RETRIES)
        if not new_instance:
            raise XDriverException("Could not reboot browser.", caller_prefix=self._caller_prefix)

        self.__dict__.update(new_instance.__dict__)  # Transparently restore XDriver reference with new one

    ### Webdriver Overridden Methods ###
    ''' Most of the times we want to be aware if the base domain is redirected somehwere else (e.g. a "t.co/askjd" URL might redirect to a totally differnt domain)
    '''

    def get(self, url, allow_redirections=False, accept_cookie=False, click_popup=False):
        if not url.startswith("http"):  # Handle single domains without scheme
            url = "http://%s" % url
        self._last_url = url  # Store the last URL that was explicitly visited. Might be needed if the driver hangs to restore state
        if not self._invoke(super(XDriver, self).get, url, max_retries=2):
            return False  # If it timeouts, return False
        if not allow_redirections:
            redirection_url = self.current_url()
            if URLUtils.get_main_domain(url) != URLUtils.get_main_domain(redirection_url):
                Logger.spit("%s redirected to: %s" % (url, redirection_url), warning=True,
                            caller_prefix=self._caller_prefix)
                return False
        # self.setup_page_scripts()
        self.store_reference_element(url)
        self.store_reference_element(
            self.current_url())  # also landing URL in case it differs from the passed URL; quite common

        # if accept_cookie:
        #     self._invoke(self.accept_cookies)
        # if click_popup:
        #     self._invoke(self.click_popup)
        return True

    '''Accept cookies'''

    def accept_cookies(self):
        element = self.get_clickable_elements_contains("accept")
        if element:
            for ct in range(len(element)):
                successfully_click = self.click(element[ct])
                if successfully_click:
                    return True
        return False

    '''Click popup window'''

    def click_popup(self):
        keyword_list = ["close", "ok", "agree", "I understand", "I accept"]
        for keyword in keyword_list:
            element = self.get_clickable_elements_contains(keyword)
            if element:
                for ct in range(len(element)):
                    successfully_click = self.click(element[ct])
                    if successfully_click:
                        return True
        return False

    def set_last_url(self, url):  # Set the last known URL (i.e. to a location that we didn't explicitly `get`)
        self._last_url = url

    ''' This is necessary since webdriver's `page_source` is @property defined and thus cannot be safely invoked
    '''

    def page_source(self):
        return self._invoke(self._page_source)

    def _page_source(self):
        return super(XDriver, self).page_source

    def rendered_source(self):
        try:
            return self._invoke(self.execute_script, "return document.getElementsByTagName('html')[0].innerHTML;")
        except selenium.common.exceptions.JavascriptException:
            return self.page_source()

    '''get page text through normal HTML'''

    def get_page_text(self):
        try:
            body = self.find_element_by_tag_name('html').text
            return body
        except:
            return ''

    def get_button_text(self):
        ret = self._invoke(self.execute_script, "return get_all_buttons_text();")
        if ret:
            return ' '.join(ret)
        else:
            return ''

    def get_title(self):
        try:
            title = self.title
            return title
        except:
            return ''

    '''get visible page tet (slower)'''

    def get_visible_page_text(self):
        return self._invoke(self.execute_script, "return get_all_visible_text();")

    ''' This is necessary since webdriver's `current_url` is @property defined and thus cannot be safely invoked 
    '''

    def current_url(self):
        return self._invoke(self._current_url)

    def _current_url(self):
        return super(XDriver, self).current_url

    ''' Try to switch to the given window
    '''

    def switch_to_window(self, window_handle):
        return self._invoke(self._switch_to_window, window_handle)

    def _switch_to_window(self, window_handle):
        # Default `switch_to.window` hangs in case there is an open alert, so we need a dummy op to trigger the alert handling
        self.execute_script("return 2;")
        self.switch_to.window(window_handle)
        return True

    ''' Switch back to the default content
    '''

    def switch_to_default(self):
        return self._invoke(self._switch_to_default)

    def _switch_to_default(self):
        self.switch_to.window(self.window_handles[0])
        return True

    def switch_to_default_content(self):
        return self._invoke(self._switch_to_default_content)

    def _switch_to_default_content(self):
        self.switch_to.default_content()
        return True

    # Scroll to top of the page
    def scroll_to_top(self):
        try:
            self.execute_script("window.scrollTo(0, 0);")
            return True
        except Exception as e:
            Logger.spit("Error {} when trying to scroll to the top".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return False

    # Scroll to bottom of the page
    def scroll_to_bottom(self):
        try:
            self.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            return True
        except Exception as e:
            Logger.spit("Error {} when trying to scroll to the bottom".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return False

    # Get current page's URL scheme
    def get_scheme(self):
        return self._invoke(self.execute_script, "return window.location.protocol")

    # Get window size
    def get_windowsize(self):
        return self._invoke(self.execute_script, "return getWindowSize();")

    ''' clean up windows
    '''

    def clean_up_window(self):
        self._invoke(self._clean_up_window)

    def _clean_up_window(self):
        current_window = self.current_window_handle
        for i in self.window_handles:  # loop over all chrome windows
            if i != current_window:  # close other windows
                self.switch_to_window(i)
                self.close()
        # switch back to the current window
        self.switch_to_window(current_window)
        return True

    ''' Get Screenshot as base64
    '''

    def get_screenshot_encoding(self):
        return self._invoke(super(XDriver, self).get_screenshot_as_base64)

    ''' Get and clear local/session storage
    '''

    def get_local_storage(self):
        try:
            return self._invoke(self.execute_script, "return get_local_storage();")
        except Exception as e:
            return {}

    def get_session_storage(self):
        try:
            return self._invoke(self.execute_script, "return get_session_storage();")
        except Exception as e:
            return {}

    def clear_local_storage(self):
        return self._invoke(self._clear_local_storage)

    def _clear_local_storage(self):
        self.execute_script("localStorage.clear();")
        return True

    def clear_session_storage(self):
        return self._invoke(self._clear_session_storage)

    def _clear_session_storage(self):
        self.execute_script("sessionStorage.clear();")
        return True

    def clear_storage(self):
        self.clear_local_storage()
        self.clear_session_storage()

    ''' Find and return an element after the given timeout
    '''

    def find_element(self, by=By.ID, value=None, timeout=0, visible=False, webelement=None):
        # This is necessary, because the expected condition below (implementing the timeout) recursively calls `find_element` and a stack overflow
        # occurs. Therefore, this ensures that the EC's calls will actually call the parent method
        if timeout == 0 and visible is False:
            # ret = self._invoke(super(XDriver, self).find_element, by = by, value = value) if webelement is None else self._invoke(webelement.find_element, by = by, value = value)
            ret = self._invoke(super(XDriver, self).find_element, by=by,
                               value=value) if webelement is None else self._invoke(self._webelement_find_element_by,
                                                                                    webelement, by=by, value=value)
        else:
            try:
                condition = EC.presence_of_element_located if not visible else EC.visibility_of_element_located
                ret = WebDriverWait(self, timeout).until(condition((by, value)))
            except TimeoutException:
                return None

        ref = id(ret)
        if ret:
            self._REFS[ref] = (self.find_element, (), {"by": by, "value": value, "timeout": timeout, "visible": visible,
                                                       "webelement": webelement})
        return ret

    def _webelement_find_element_by(self, element, by=By.ID, value=None):
        return element.find_element(by=by, value=value)

    ''' Find and return all matching elements after the given timeout
    '''

    def find_elements(self, by=By.ID, value=None, timeout=0, visible=False, webelement=None, *args, **kwargs):
        # We have to call this first b/c we need to simulate the given timeout. Essentially wait for at least one such element to appear
        if timeout > 0:
            self.find_element(by=by, value=value, timeout=timeout, visible=visible, webelement=webelement, *args,
                              **kwargs)
        # ret_elements = self._invoke(super(XDriver, self).find_elements, by = by, value = value, *args, **kwargs) if webelement is None else self._invoke(webelement.find_elements, by = by, value = value, *args, **kwargs)
        ret_elements = self._invoke(super(XDriver, self).find_elements, by=by, value=value, *args,
                                    **kwargs) if webelement is None else self._invoke(self._webelement_find_elements_by,
                                                                                      webelement, by=by, value=value,
                                                                                      webelement=webelement, *args,
                                                                                      **kwargs)
        if ret_elements:
            to_remove = set()
            dompaths = []
            # Collect the returned elements' DOMPath
            for el in ret_elements:
                try:
                    el_dompath = self.get_dompath(el)
                except StaleElementReferenceException:
                    to_remove.add(el)
                    continue
                # Make sure the returned elements are robust against StaleElementReferenceExceptions by simulating a `find_element_by_xpath`
                ref = id(el)
                if ref not in self._REFS:  # If not already previously fetched
                    self._REFS[ref] = (
                        self.find_element, (), {"by": By.XPATH, "value": el_dompath, "timeout": 3, "visible": False})

            for el in to_remove:
                ret_elements.remove(el)

        return ret_elements

    def _webelement_find_elements_by(self, element, by=By.ID, value=None, *args, **kwargs):
        return element.find_elements(by=by, value=value, *args, **kwargs)

    ''' Wrapper `find_element(s)` methods.
    '''

    def find_element_by_id(self, id_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.ID, value=id_, timeout=timeout, visible=visible, webelement=webelement)

    def find_elements_by_id(self, id_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.ID, value=id_, timeout=timeout, visible=visible, webelement=webelement, *args,
                                  **kwargs)

    def find_element_by_name(self, name_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.NAME, value=name_, timeout=timeout, visible=visible, webelement=webelement)

    def find_elements_by_name(self, name_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.NAME, value=name_, timeout=timeout, visible=visible, webelement=webelement, *args,
                                  **kwargs)

    def find_element_by_class_name(self, class_name_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.CLASS_NAME, value=class_name_, timeout=timeout, visible=visible,
                                 webelement=webelement)

    def find_elements_by_class_name(self, class_name_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.CLASS_NAME, value=class_name_, timeout=timeout, visible=visible,
                                  webelement=webelement, *args, **kwargs)

    def find_element_by_xpath(self, xpath_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.XPATH, value=xpath_, timeout=timeout, visible=visible, webelement=webelement)

    def find_elements_by_xpath(self, xpath_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.XPATH, value=xpath_, timeout=timeout, visible=visible, webelement=webelement,
                                  *args, **kwargs)

    def find_element_by_css_selector(self, css_selector_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.CSS_SELECTOR, value=css_selector_, timeout=timeout, visible=visible,
                                 webelement=webelement)

    def find_elements_by_css_selector(self, css_selector_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.CSS_SELECTOR, value=css_selector_, timeout=timeout, visible=visible,
                                  webelement=webelement, *args, **kwargs)

    def find_element_by_link_text(self, link_text_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.LINK_TEXT, value=link_text_, timeout=timeout, visible=visible,
                                 webelement=webelement)

    def find_elements_by_link_text(self, link_text_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.LINK_TEXT, value=link_text_, timeout=timeout, visible=visible,
                                  webelement=webelement, *args, **kwargs)

    def find_element_by_tag_name(self, tag_name_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.TAG_NAME, value=tag_name_, timeout=timeout, visible=visible, webelement=webelement)

    def find_elements_by_tag_name(self, tag_name_, timeout=0, visible=False, webelement=None, *args, **kwargs):
        return self.find_elements(By.TAG_NAME, value=tag_name_, timeout=timeout, visible=visible, webelement=webelement,
                                  *args, **kwargs)

    def find_element_by_partial_link_text(self, partial_link_text_, timeout=0, visible=False, webelement=None):
        return self.find_element(By.PARTIAL_LINK_TEXT, value=partial_link_text_, timeout=timeout, visible=visible,
                                 webelement=webelement)

    def find_elements_by_partial_link_text(self, partial_link_text_, timeout=0, visible=False, webelement=None, *args,
                                           **kwargs):
        return self.find_elements(By.PARTIAL_LINK_TEXT, value=partial_link_text_, timeout=timeout, visible=visible,
                                  webelement=webelement, *args, **kwargs)

    def find_element_by_location(self, point_x, point_y):
        return self._invoke(self.execute_script, 'return document.elementFromPoint(%r, %r);' % (point_x, point_y))

    ''' Check if the webdriver has been redirected after fetching the given URL, using the reference element stored at that time
    '''

    def is_redirected(self, url, timeout=5):
        return self._invoke(self._is_redirected, url, timeout=timeout)

    def _is_redirected(self, url, timeout=5):
        reference_element = self._REDIRECTS.get(url, None)
        if reference_element is None:  # If an unknown URL is given, return True
            Logger.spit("Unknown URL in `is_redirected` (%s)" % url, warning=True, caller_prefix=self._caller_prefix)
            return True
        end = time() + timeout
        while time() < end:
            try:
                reference_element.text  # dummy op to trigger the exception
            except StaleElementReferenceException as e:
                return True
        return False

    def store_reference_element(self, url):
        # We directly use the parent class method, so the element will not be refetched when asked if stale,
        # since 'html' tags are always there and `is_stale` would always return True
        _redirection_element = super(XDriver, self).find_element_by_tag_name("html")
        self._REDIRECTS[url] = _redirection_element

    def wait_for_url_change(self, url, timeout=5):
        end = time() + timeout
        while time() < end:
            current = self.current_url()
            if current != url:
                return True
        return False

    ''' Given a web element try to identify whether it has become stale or not
    '''

    def is_stale(self, element, visible=False):
        Logger.set_warning_off()
        try:
            self.get_attribute(element, "id")  # dummy operation to see if we can refetch the element or not
            stale = False
        except StaleElementReferenceException as e:
            stale = True
        Logger.set_warning_on()
        return stale

    ''' Move mouse over an element; triggers the 'mouseenter' DOM event
    '''

    def move_to_element(self, element):
        return self._invoke(self._move_to_element, element, webelement=element)

    def _move_to_element(self, element):
        ActionChains(self).move_to_element(element).perform()
        return True

    ''' Move mouse over an element and then away; triggers the 'mouseleave' DOM event
    '''

    def move_away_from_element(self, element):
        return self._invoke(self._move_away_from_element, element, webelement=element)

    def _move_away_from_element(self, element):
        ActionChains(self).move_to_element(element).move_by_offset(100, 100).perform()
        # self.find_elements_by_tag_name("body")[0].click() # Dummy op to move away from element
        return True

    ''' Move cursor over an element; triggers the 'mousemove' DOM event
    '''

    def move_over_element(self, element):
        return self._invoke(self._move_over_element, element, webelement=element)

    def _move_over_element(self, element):
        ActionChains(self).move_to_element(element).move_by_offset(1, 1).move_by_offset(-1, -1).perform()
        return True

    ''' Simple click. Goes over the given element and clicks. 
    '''

    def click(self, element):
        return self._invoke(self._click, element, webelement=element)

    def _click(self, element):
        ActionChains(self).move_to_element(element).click().perform()
        return True

    ''' Same as `click`, but more strict. The click MUST end up on the given element
    '''

    def exact_click(self, element):
        return self._invoke(self._exact_click, element, webelement=element)

    def _exact_click(self, element):
        element.click()
        return True

    ''' Useful for invisible elements that we want to trigger their `onClick`. Also, since sometimes the element at hand is not the actual clickable,
        but rather a parent of the clickable, we might need to traverse and `js_click` its children'''

    def js_click(self, element, with_children=False):
        return self._invoke(self._js_click, element, with_children=with_children, webelement=element)

    # return self._js_click(element, with_children = with_children)
    def _js_click(self, element, with_children=False):
        sleep(2)  # monkey fix for specific cases. let the clickable load its events (?)
        self.execute_script("arguments[0].click()", element)
        if with_children:
            try:
                children = self.find_elements_by_xpath(".//*", webelement=element)
                for child in children:
                    self.execute_script("arguments[0].click()", child)
            except WebDriverException as ex:  # If one of the clicks causes a redirection, we most likely found what we were looking for
                # if ex is StaleElementReferenceException or "arguments[0].click is not a function" in stringify_exception(ex):
                pass
        return True

    def double_click(self, element):
        return self._invoke(self._double_click, element, webelement=element)

    def _double_click(self, element):
        ActionChains(self).move_to_element(element).double_click().perform()
        return True

    # Right click
    def context_click(self, element):
        return self._invoke(self._context_click, element, webelement=element)

    def _context_click(self, element):
        ActionChains(self).move_to_element(element).context_click().perform()
        return True

    # Wheel click
    def middle_click(self, element):
        return self._invoke(self._middle_click, element, webelement=element)

    def _middle_click(self, element):
        self.execute_script(
            "var mouseWheelClick = new MouseEvent( \"click\", { \"button\": 1, \"which\": 1 }); arguments[0].dispatchEvent(mouseWheelClick)",
            element)
        return True

    ''' Click and hold on the element; triggers the 'mousedown' DOM event
    '''

    def mousedown(self, element):
        return self._invoke(self._mousedown, element, webelement=element)

    def _mousedown(self, element):
        ActionChains(self).move_to_element(element).click_and_hold().perform()
        return True

    ''' Click and hold and then release the mouse on the element; triggers the 'mouseup' event
    '''

    def mouseup(self, element):
        return self._invoke(self._mouseup, element, webelement=element)

    def _mouseup(self, element):
        ActionChains(self).move_to_element(element).click_and_hold().release().perform()
        return True

    def send_keys(self, element, keys):
        return self._invoke(self._send_keys, element, keys, webelement=element)

    def _send_keys(self, element, keys):
        element.send_keys(keys)
        return True

    def submit(self, element):
        return self._invoke(self._submit, element, webelement=element)

    def _submit(self, element):
        # element.submit()
        self.execute_script("arguments[0].submit()", element)
        return True

    # Trigger the 'onsubmit' DOM event via locating and clicking the submit button
    # If that fails, fall back to default `submit` above
    def onsubmit(self, element):
        return self._invoke(self._onsubmit, element, webelement=element)

    def _onsubmit(self, element):
        try:
            submit_el = self.find_element_by_xpath(".//input[@type='submit']", webelement=element)
            ActionChains(self).move_to_element(submit_el).click().perform()
        except Exception as e:
            self.submit(element)
        return True

    def reset(self, element):
        return self._invoke(self._reset, element, webelement=element)

    def _reset(self, element):
        self.execute_script("arguments[0].reset()", element)
        return True

    # Trigger the 'onreset' DOM event via locating and clicking the reset button
    # If that fails, fall back to default `reset` above
    def onreset(self, element):
        return self._invoke(self._onreset, element, webelement=element)

    def _onreset(self, element):
        try:
            reset_el = self.find_element_by_xpath(".//input[@type='reset']", webelement=element)
            ActionChains(self).move_to_element(reset_el).click().perform()
        except Exception as e:
            self.reset(element)
        return True

    # Trigger 'onfocus' and 'onfocusin' DOM events
    def focus(self, element):
        return self._invoke(self._focus, element, webelement=element)

    def _focus(self, element):
        try:
            ActionChains(self).move_to_element(element).click().perform()
        except Exception as e:
            self.execute_script("arguments[0].focus()", element)  # Fallback to JS
        return True

    # Trigger 'onfocusout' DOM event
    def focusout(self, element):
        return self._invoke(self._focusout, element, webelement=element)

    def _focusout(self, element):
        try:
            self.execute_script("arguments[0].focus(); arguments[0].blur()", element)
        except Exception as e:
            ActionChains(self).move_to_element(element).click().move_by_offset(-2000,
                                                                               -2000).click().perform()  # Click element to place focus, then click on upper left corner to remove focus
        return True

    # Trigger 'onblur' DOM event
    def blur(self, element):
        return self._invoke(self._blur, element, webelement=element)

    def _blur(self, element):
        try:
            self.execute_script("arguments[0].focus(); arguments[0].blur()", element)
        except Exception as e:
            ActionChains(self).move_to_element(element).click().move_by_offset(-2000,
                                                                               -2000).click().perform()  # Click element to place focus, then click on upper left corner to remove focus
        return True

    ''' Element specific auxiliary methods
    '''

    # Get an element's DOMPath
    def get_dompath(self, element):
        try:
            dompath = self._invoke(self.execute_script, "return get_dompath(arguments[0]).toLowerCase();", element,
                                   webelement=element)
        except Exception as e:
            raise  # Debug debug Debug
        # Construct element's full dompath and substitute any namespace part of it (contains ':') with a wildcard (*)
        return "//html%s" % "/".join(
            [part if ":" not in part else "*" for part in dompath.split("/")]) if dompath else dompath

    # Get element's outerHTML
    def get_element_src(self, element, full=False):
        src = self._invoke(self.execute_script, "return arguments[0].outerHTML;", element, webelement=element)
        if not full:
            return "%s>" % src.split(">")[0] if src else src
        return src

    # Get element's attributes as a dict
    def get_attributes(self, element):
        return self._invoke(self.execute_script, "return get_attributes(arguments[0]);", element, webelement=element)

    # Get element's attribute
    def get_attribute(self, element, attribute):
        return self._invoke(self._get_attribute, element, attribute, webelement=element)

    def _get_attribute(self, element, attribute):
        try:
            attribute = element.get_attribute(attribute)
            return attribute
        except StaleElementReferenceException:
            return ''

    # Get element text
    def get_text(self, element):
        try:
            text = self._invoke(self.execute_script, 'return arguments[0].innerText;', element, webelement=element)
            return text
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when trying to get element text".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return ''

    def get_location(self, element):
        try:
            loc = self._invoke(self.execute_script, 'return get_loc(arguments[0]);', element, webelement=element)
            return loc
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when trying to get element location".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return [0, 0, 0, 0]

    def get_property(self, element, eproperty):
        try:
            return self._invoke(self._get_property, element, eproperty, webelement=element)
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when trying to get element property".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return ''

    def _get_property(self, element, eproperty):
        return element.get_property(eproperty)

    def get_element_property(self, element):
        try:
            return self._invoke(self.execute_script, "return get_element_properties(arguments[0]);", element,
                                webelement=element)
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when trying to get element property".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return [''] * 10

    # Get an element's tag in lowercase
    def get_tag(self, element):
        try:
            return self._invoke(self.execute_script, "return arguments[0].tagName.toLowerCase()", element,
                                webelement=element)

        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when trying to get element tagname".format(e), warning=True,
                        caller_prefix=XDriver._caller_prefix)
            return ''

    # Check whether an element's tag matches the given tag
    def is_tag(self, element, tag):
        return self.get_tag(element) == tag.lower()

    # Get an element's type
    def get_type(self, element):
        try:
            etype = self._invoke(self.execute_script, "return arguments[0].type", element, webelement=element)
        except Exception as e:
            etype = self.get_attribute(element, "type")
        return etype.lower() if etype else ""

    # Check whether an element's type matches the given type
    def is_type(self, element, ctype):
        return self.get_type(element) == ctype.lower()

    # Check whether the given element is `required`
    def is_required(self, element):
        return self._invoke(self.execute_script, "return arguments[0].required", element, webelement=element)

    # Get and set the given element's value
    def get_value(self, element):
        return self._invoke(self.execute_script, "return arguments[0].value", element, webelement=element)

    def set_value(self, element, value):
        self._invoke(self.execute_script, "arguments[0].value = '%s';" % value, element, webelement=element)
        return value

    # Mark the given element as `checked`
    def check_element(self, element):
        self._invoke(self.execute_script, "arguments[0].checked = true;", element, webelement=element)

    # Check if the given element is `checked`
    def is_checked(self, element):
        return self._invoke(self.execute_script, "return arguments[0].checked", element, webelement=element)

    # Select the given index, when given a `Select` webelement
    def set_selected_index(self, element, idx):
        self._invoke(self.execute_script, "arguments[0].selectedIndex = '%s';" % idx, element, webelement=element)

    def get_parent(self, element):
        return self._invoke(self.execute_script, "arguments[0].parentElement", element, webelement=element)

    def get_children(self, element):
        return self._invoke(self.execute_script, "arguments[0].children", element, webelement=element)

    def get_descendants(self, element):
        ret = self.find_elements_by_xpath(".//*", webelement=element)
        if ret:
            # return [element for element in ret if element and type(element) != list]
            return [element for element in ret if element]
        return ret

    # Scroll element into view
    def scroll_to(self, element):
        ret = self._invoke(self.execute_script, "arguments[0].scrollIntoView(true);", element, webelement=element)

    ''' Returns True if the given WebElement appears to be on the top layer of the canvas
    '''

    def is_displayed(self, element):
        return self._invoke(self._is_displayed, element, webelement=element)

    def _is_displayed(self, element):
        return element.is_displayed()

    ''' This MUST be called before anything else in the current page's context, so after a `get` or when redirected
    '''

    def setup_page_scripts(self):
        # if self._browser_instance_type == FIREFOX: # Only needed for firefox. Chromium-based browsers use the DevTools API to add scripts on new docs
        self._invoke(self._setup_page_scripts)

    def _setup_page_scripts(self):
        self.execute_script(self._config["xdriver"]["scripts_after_load"])

    ''' Check whether the current page contains a given regex in src
    '''

    def contains_in_src(self, pattern, exact=False):
        return self._contains_in(self.rendered_source(), pattern, exact=exact)

    ''' Check whether the current page contains a given regex in its DISPLAYED text
    '''

    def contains_in_text(self, pattern, exact=False):
        body = self.rendered_source()
        if not body:
            return False
        return self._contains_in(body, pattern, exact=exact)

    def _contains_in(self, search_string, pattern, exact=False):
        if re.search(pattern, search_string, re.IGNORECASE if not exact else 0):
            return True
        return False

    ''' Return a list of all links
    '''
    def get_all_links_orig(self):
        return self._invoke(self._get_all_links_orig)

    def _get_all_links_orig(self):
        ret = self._invoke(self.execute_script, "return get_all_links();")
        interested_links = []
        for link_ele in ret:
            link, link_dompath, link_source = link_ele
            if re.search(XDriver._forbidden_suffixes, link_source, re.IGNORECASE):
                continue
            if link not in interested_links:
                interested_links.append([link, link_source])
                self._REFS[id(link)] = (self.find_element, (), {"by": By.XPATH, "value": link_dompath, "timeout": 3, "visible": False})

        return interested_links
    

    def get_all_links(self):
        return self._invoke(self._get_all_links)

    def _get_all_links(self):
        ret = self._invoke(self.execute_script, "return get_all_links();")
        interested_links = []
        link_doms = []
        link_sources = []
        for link_ele in ret:
            link, link_dompath, link_source = link_ele
            interested_links.append(link)
            link_doms.append(link_dompath)
            link_sources.append(link_source)
            self._REFS[id(link)] = (
            self.find_element, (), {"by": By.XPATH, "value": link_dompath, "timeout": 3, "visible": False})

        return interested_links, link_doms, link_sources

    ''' Return a list of all anchor's `href` attributes, that point to the same domain
    '''

    def get_internal_links(self):
        return self._invoke(self._get_internal_links)

    def _get_internal_links(self):

        domain = URLUtils.get_main_domain(self.current_url())
        ret = self._invoke(self.execute_script, "return get_all_links();")
        interested_links = []
        for link_ele in ret:
            link, link_dompath, link_source = link_ele
            if re.search(XDriver._forbidden_suffixes, link_source, re.IGNORECASE):
                continue
            if (not link_source.startswith('http')) or URLUtils.get_main_domain(link_source) == domain:
                if link not in interested_links:
                    interested_links.append([link, link_source])
                    self._REFS[id(link)] = (
                    self.find_element, (), {"by": By.XPATH, "value": link_dompath, "timeout": 3, "visible": False})

        return interested_links

    '''Get all <input>'''

    def get_all_inputs(self):
        ret = self._invoke(self.execute_script, "return get_all_inputs();")
        interested_inputs = []
        interested_inputs_dom = []

        for input_ele in ret:
            input, input_dompath = input_ele
            interested_inputs.append(input)
            interested_inputs_dom.append(input_dompath)
            self._REFS[id(input)] = (
            self.find_element, (), {"by": By.XPATH, "value": input_dompath, "timeout": 3, "visible": False})

        return interested_inputs, interested_inputs_dom

    def get_all_visible_username_password_inputs(self):
        ret_password, ret_username = self._invoke(self.execute_script,
                                                  "return get_all_visible_password_username_inputs();")
        return ret_password, ret_username

    '''Get all <button> or clickable elements in <form>'''

    def get_all_buttons(self):
        ret = self._invoke(self.execute_script, "return get_all_buttons();")
        interested_buttons = []
        interested_buttons_dom = []

        for button_ele in ret:
            button, button_dompath = button_ele
            interested_buttons.append(button)
            interested_buttons_dom.append(button_dompath)
            self._REFS[id(button)] = (
            self.find_element, (), {"by": By.XPATH, "value": button_dompath, "timeout": 3, "visible": False})

        return interested_buttons, interested_buttons_dom

    def get_all_elements_from_coordinate_list(self, coordinate_list):
        ret, returned_coords = self._invoke(self.execute_script,
                                            "return get_all_elements_from_coordinate_list(arguments[0]);",
                                            coordinate_list)
        interested_elements = []
        interested_elements_dom = []

        for this_element in ret:
            ele, ele_dompath = this_element
            interested_elements.append(ele)
            interested_elements_dom.append(ele_dompath)
            self._REFS[id(ele)] = (
                self.find_element, (), {"by": By.XPATH, "value": ele_dompath, "timeout": 3, "visible": False})

        return interested_elements, interested_elements_dom, returned_coords

    def get_all_numeric_buttons(self):
        ret = self._invoke(self.execute_script, "return get_numeric_buttons();")
        interested_buttons = []
        for button_ele in ret:
            button, button_dompath = button_ele
            interested_buttons.append(button)
            self._REFS[id(button)] = (
                self.find_element, (), {"by": By.XPATH, "value": button_dompath, "timeout": 3, "visible": False})

        return interested_buttons

    '''Get all iframes'''

    def get_all_iframes(self):
        ret = self._invoke(self.execute_script, "return get_all_iframes();")
        interested_iframes = []

        for iframe_ele in ret:
            iframe, iframe_dom_path = iframe_ele
            interested_iframes.append(iframe)
            self._REFS[id(iframe)] = (
            self.find_element, (), {"by": By.XPATH, "value": iframe_dom_path, "timeout": 3, "visible": False})

        return interested_iframes

    def get_all_visible_imgs(self):
        ret = self._invoke(self.execute_script, "return get_all_visible_imgs();")
        interested_imgs = []

        for img_ele in ret:
            img, img_dompath = img_ele
            interested_imgs.append(img)
            self._REFS[id(img)] = (
                self.find_element, (), {"by": By.XPATH, "value": img_dompath, "timeout": 3, "visible": False})

        return interested_imgs

    '''Get displayed <form>'''

    def get_displayed_forms(self):
        return self._invoke(self._get_displayed_forms)

    def _get_displayed_forms(self):
        forms = self.find_elements_by_tag_name("form")
        ret_forms = []
        for form in forms:
            try:
                if self.is_displayed(form):
                    ret_forms.append(form)
            except StaleElementReferenceException as e:
                continue
        return ret_forms

    def get_form_labels(self, form):
        f = self._invoke(FormOriginal.FormOriginal, self, form,
                         webelement=form)  # `_invoke` it in case the form has become stale
        return f.get_labels() if form else []

    ''' Returns a tuple of two lists with all login and registration forms -> (login_forms, reg_forms)
    '''

    def get_account_forms(self, login_only=False, signup_only=False, *args, **kwargs):
        # TODO: find login/sign up
        ''' When running in virtual or headless mode, the window is not fully maximized as in the real display.
            This causes the js code to misedntify account forms as not displayed, when they are and thus they are not returned
            The loop and `scroll_to` on all displayed forms of the page is necessary to avoid this. Not efficient but necessary. '''
        login_forms = []
        signup_forms = []
        displayed_forms = self.get_displayed_forms()
        displayed_forms.insert(0,
                               None)  # Dummy 1st element so we try to fetch any account forms without messing with the scroll
        for f in displayed_forms:
            if f:
                self.scroll_to(f)
            else:
                self.scroll_to_top()
            ret = self._invoke(self.execute_script, "return get_account_forms();")  # do it recursively
            if not ret:
                # return ([], []) # No forms, or something went terribly wrong
                continue
            # self._REFS[id(form)] = (self.find_element, (), {"by" : By.XPATH, "value" : form_dompath, "timeout" : 5, "visible" : False})
            for form in ret["login"]:
                form, form_dompath = form[0], form[1]
                if form in login_forms or not self.is_displayed(form):
                    continue
                login_forms.append(form)
                self._REFS[id(form)] = (
                    self.find_element, (), {"by": By.XPATH, "value": form_dompath, "timeout": 5, "visible": False})
            for form in ret["signup"]:
                form, form_dompath = form[0], form[1]
                if form in signup_forms or not self.is_displayed(form):
                    continue
                signup_forms.append(form)
                self._REFS[id(form)] = (
                    self.find_element, (), {"by": By.XPATH, "value": form_dompath, "timeout": 5, "visible": False})

            if (login_only and login_forms) or (signup_only and signup_forms) or (
                    not login_only and not signup_only and login_forms and signup_forms):
                return (login_forms, signup_forms)

        return (login_forms, signup_forms)

    def get_login_forms(self, *args, **kwargs):
        return self.get_account_forms(login_only=True, *args, **kwargs)[0]

    def get_signup_forms(self, *args, **kwargs):
        return self.get_account_forms(signup_only=True, *args, **kwargs)[1]

    # Fill the given form
    def fill_and_submit(self, form, required_only=False, override_rules={}):
        return self.fill_form(form, submit=True, required_only=required_only, override_rules=override_rules)

    def fill_form(self, form, submit=False, required_only=False, override_rules={}):
        filtered_elements, values, submit_button, submit_button_location = self._invoke(self._fill_form, form,
                                                                                        submit=submit,
                                                                                        required_only=required_only,
                                                                                        override_rules=override_rules,
                                                                                        webelement=form)
        return filtered_elements, values, submit_button, submit_button_location

    def _fill_form(self, form, submit=False, required_only=False, override_rules={}):
        f = FormOriginal.FormOriginal(self, form)
        filtered_elements, values, submit_button, submit_button_location = f.fill(submit=submit,
                                                                                  required_only=required_only,
                                                                                  override_rules=override_rules)
        return filtered_elements, values, submit_button, submit_button_location

    # Check whether the given element is a form input
    def is_form_input(self, element):
        tag = self.get_tag(element)
        etype = self.get_type(element)
        if (tag != "input" and tag != "textarea" and tag != "select") or etype == "submit" or etype == "hidden":
            return False
        return True

    '''Get all javascripts'''

    def get_all_scripts(self):
        scripts_elements = self._invoke(self.execute_script, "return get_all_scripts();")
        script_list = []

        for script_ele in scripts_elements:
            script, script_dompath, script_src, script_text = script_ele
            if script_text and len(script_text):  # script in text
                js_source = script_text
            else:  # script in src
                try:
                    js_source = urllib.request.urlopen(script_src, timeout=0.5).read()
                except Exception as e:
                    Logger.spit("Error {} in downloading js file {}".format(e, script_src),
                                debug=True, caller_prefix=XDriver._caller_prefix)
                    js_source = ''

            if isinstance(js_source, bytes):  # decode js
                js_source = js_source.decode('ISO 8859-1')

            script_list.append([script, script_dompath, script_src, js_source])
            self._REFS[id(script)] = (
                self.find_element, (), {"by": By.XPATH, "value": script_dompath, "timeout": 3, "visible": False})

        return script_list

    '''Get clickable elements contain certain patterns'''
    def get_all_clickable_elements(self):
        btns, btns_dom = self.get_all_buttons()
        links, links_dom, _ = self.get_all_links()
        image_elements = self._invoke(self.execute_script, "return get_all_clickable_imgs();")
        all_leaf_node_xpath = ["//span[not(*)]", "//div[not(*)]",
                               "//p[not(*)]", "//i[not(*)]"] # fixme: I find some leaf DOM element implements onclick event with class, difficult to trace
        other_elements_pre = []
        other_elements = []
        other_elements_dom = []
        for path in all_leaf_node_xpath:
            elements = self.find_elements_by_xpath(path)
            if elements:
                other_elements_pre.extend(elements)

        for ele in other_elements_pre:
            try:
                dompath = self.get_dompath(ele)
                other_elements_dom.append(dompath)
                other_elements.append(ele)
                self._REFS[id(ele)] = (self.find_element, (), {"by": By.XPATH, "value": dompath, "timeout": 3, "visible": False})
            except:
                continue

        images = []
        images_dom = []

        for ele in image_elements:
            img, dompath = ele
            images.append(img)
            images_dom.append(dompath)
            self._REFS[id(img)] = (self.find_element, (), {"by": By.XPATH, "value": dompath, "timeout": 3, "visible": False})

        return (btns, btns_dom), (links, links_dom), (images, images_dom), \
            (other_elements, other_elements_dom)

    def get_clickable_elements_contains(self, patterns):

        button_xpaths = self._get_elements_xpath_contains(patterns, tag='button', role='button')
        link_xpaths = self._get_elements_xpath_contains(patterns, tag='a', role='link')
        input_xpath = self._get_input_elements_xpath_contains(patterns)
        free_text_xpath = self._get_free_text_elements_xpath_contains(patterns)

        element_list = []
        for path in button_xpaths + link_xpaths + [input_xpath] + [free_text_xpath]:
            elements = self.find_elements_by_xpath(path)
            if elements:
                element_list.extend(elements)

        return element_list

    def _get_input_elements_xpath_contains(self, patterns):
        property_list = ["text()", "@class", "@title", "@value", "@label", "@aria-label"]

        return "//input[@type='submit' or @type='button'][%s]" % (
            " or ".join(["starts-with(normalize-space(%s), '%s')" % (lower(replace_nbsp(property)), patterns.lower())
                         for property in property_list]))

    def _get_elements_xpath_contains(self, patterns, tag, role):
        property_list = ["text()", "@class", "@title", "@value", "@label", "@aria-label"]

        rule1 = "//%s[" % (tag if tag else "*") + " or ".join(
            ["starts-with(normalize-space(%s), '%s')" % (lower(replace_nbsp(property)), patterns.lower())
             for property in property_list])

        rule2 = "//*[@role='%s'][%s]" % (role if role else "*", "starts-with(normalize-space(.), '%s')" % patterns)
        return [rule1, rule2]

    def _get_free_text_elements_xpath_contains(self, patterns):
        xpath_base = "//*[starts-with(normalize-space(%s), '%s')]" % (lower(replace_nbsp("text()")), patterns.lower())
        return '%s[not(self::script)][not(.%s)]' % (xpath_base, xpath_base)

    '''Get first common DOM parent between two elements'''

    def get_dom_common_parents(self, element1, element2):
        try:
            return self._invoke(self.execute_script, 'return findFirstCommonAncestor(arguments[0], arguments[1]);',
                                element1, element2)
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when getting the common DOM parent between two elements".format(e),
                        warning=True, caller_prefix=XDriver._caller_prefix)
            return None

    '''Get DOM distance between two elements (by adding up the DOM distance to common parent)'''

    def get_dom_dist(self, element1, element2):
        try:
            return self._invoke(self.execute_script, 'return get_domdist(arguments[0], arguments[1]);', element1,
                                element2)
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when getting the DOM distance between two elements".format(e),
                        warning=True, caller_prefix=XDriver._caller_prefix)
            dom_depth = self.get_dom_depth()
            return [dom_depth, dom_depth]

    '''Get DOM depth for an element from the root'''

    def get_dom_depth_forelement(self, element):
        try:
            return self._invoke(self.execute_script, 'return get_dom_depth_forelement(arguments[0]);', element,
                                webelement=element)
        except StaleElementReferenceException as e:
            Logger.spit("Error {} occurred when getting the common DOM depth of an element".format(e),
                        warning=True, caller_prefix=XDriver._caller_prefix)
            dom_depth = self.get_dom_depth()
            return [dom_depth, dom_depth]

    '''Get DOM tree depth'''

    def get_dom_depth(self):
        return self._invoke(self.execute_script, 'return get_dom_depth();')

    '''Check visilibility of an element'''

    def check_visibility(self, element_loc):
        x1, y1, x2, y2 = element_loc
        return np.sum([1 for x in element_loc if x <= 0]) == 0 and \
            (x2 - x1) > 0 and \
            (y2 - y1) > 0

    def get_element_prev_sibling(self, element):
        return self._invoke(self.execute_script, 'return arguments[0].previousElementSibling;', element)

    def obfuscate_page(self):
        self._invoke(self.execute_script, """
          var script = document.createElement('script');
          script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/0.5.0-beta4/html2canvas.min.js';
          document.head.appendChild(script);
        """)
        sleep(1)
        # return self._invoke(self.execute_script, """obfuscate_input();
        #                                                 obfuscate_button();
        #                                                 """)
        return self._invoke(self.execute_script, """obfuscate_button();""")

    '''recaptcha'''

    def get_implicit_recaptcha(self):

        xpath_base = "//*[starts-with(normalize-space(%s), '%s')]" % (lower(replace_nbsp("@class")),
                                                                      "g-recaptcha")

        element_list = []
        elements = self._invoke(super(XDriver, self).find_elements, By.XPATH, xpath_base)

        if elements:
            element_list.extend(elements)
        return element_list

    def get_recaptcha_checkbox(self):

        xpath_base = "//*[starts-with(normalize-space(%s), '%s')]" % (
        lower(replace_nbsp("@class")), "recaptcha-checkbox-border")

        element_list = []
        elements = self._invoke(super(XDriver, self).find_elements, By.XPATH, xpath_base)

        if elements:
            element_list.extend(elements)
        return element_list

    def get_recaptcha_audio_button(self):

        xpath_base = "//*[@id='recaptcha-audio-button']"
        element_list = []
        elements = self._invoke(super(XDriver, self).find_elements, By.XPATH, xpath_base)

        if elements:
            element_list.extend(elements)
        return element_list




