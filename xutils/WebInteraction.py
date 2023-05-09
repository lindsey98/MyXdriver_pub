#!/usr/bin/python
import time

import tldextract

from ..XDriver import XDriver
from .Regexes import Regexes
from .forms.Form import Form
from .forms.FormElement import FormElement
from .Logger import Logger
from .state.StateClass import StateClass
from .action.StateAction import StateAction
import urllib.parse
from PIL import Image
import numpy as np
import re
import cv2
import io
import base64

class WebInteraction():
    _caller_prefix = 'Webinteraction'
    def __init__(self, phishintention_cls, mmocr_model,  button_locator_model, interaction_depth=3, sim_ts=0.83,
                 standard_sleeping_time=3):
        self.home_page_heuristics = [
            ".*index.*\.htm",
            ".*login.*\.htm",
            ".*signin.*\.htm",
            ".*verif.*\.htm",
            ".*valid.*\.htm",
            ".*confir.*\.htm",
            "me.html"

        ]
        self.weaker_home_page_heuristics = [
            ".*index.*\.php",
            ".*login.*\.php",
            ".*signin.*\.php",
            ".*confir.*\.php",
            ".*verif.*\.php",
            "me.php"

        ]
        self.phishintention_cls = phishintention_cls
        self.interaction_depth = interaction_depth
        self.button_locator_model = button_locator_model
        self.sim_ts = sim_ts
        self.mmocr_model = mmocr_model
        self.standard_sleeping_time = standard_sleeping_time

    '''sort links by likelihood of being the index page'''
    def sort_files_lambda(self, x):
        x = x.lower()
        if x.startswith('rename') or x.startswith('new') or x.startswith('hack'):
            return 6
        if any([True if re.search(rule, x, re.IGNORECASE) else False for rule in self.home_page_heuristics]):
            return 1
        elif x.endswith(".html") or x.endswith(".htm"):
            return 2
        elif any([True if re.search(rule, x, re.IGNORECASE) else False for rule in self.weaker_home_page_heuristics]):
            return 3
        elif re.search(Regexes.AUTH, x, re.IGNORECASE):
            return 4
        elif x.startswith('_') or '~' in x or '@' in x or x.startswith('.') or 'htaccess' in x or 'block' in x or 'anti' in x or x.lower == 'log/' or x.lower == 'off/':
            return 6
        else:
            return 5

    def page_error_checking(self, driver):
        source = driver.page_source()
        if source == "<html><head></head><body></body></html>":
            return False
        elif ("404 Not Found" in source
              or "The requested URL was not found on this server" in source
              or "Server at localhost Port" in source
              or "Not Found" in source
              or "403 Forbidden" in source
              or "no access to view" in source
              or "Bad request" in source
        ):
            return False
        if source == "<html><head></head><body></body></html>":
            return False
        error = "(not found)|(no such file or directory)|(failed opening)|(refused to connect)|(invalid argument)|(undefined index)|(undefined property)|(undefined variable)|(syntax error)|(site error)|(parse error)"
        if re.search(error, source, re.IGNORECASE):
            return False
        return True

    def page_interaction_checking(self, driver):
        ct = 0
        hang = False
        while "Index of" in driver.get_page_text():
            links = driver.get_all_links()
            links = [x for x in links if (not x[1].startswith('?')) and (not x[1].startswith('/')) and
                     (not x[1].endswith('png')) and (not x[1].endswith('jpg')) and (not x[1].endswith('txt')) and
                     (not x[1].endswith('.so'))]
            if len(links) == 0:
                hang = True
                break
            likelihood_sort = list(map(lambda x: self.sort_files_lambda(x[1]), links))
            if len(likelihood_sort) == 0:
                hang = True
                break
            sorted_index = np.argmin(likelihood_sort)
            sorted_link_by_likelihood = links[sorted_index]
            driver.click(sorted_link_by_likelihood[0])
            time.sleep(0.5)
            # print('After clicking {}'.format(driver.current_url()))
            ct += 1
            if ct >= 10:
                hang = True
                break

        if hang:
            return False
        return self.page_error_checking(driver)

    '''check white screen'''
    def white_screen(self, shot_path):
        old_screenshot_img = Image.open(shot_path)
        old_screenshot_img = old_screenshot_img.convert("RGB")
        old_screenshot_img_arr = np.asarray(old_screenshot_img)
        old_screenshot_img_arr = np.flip(old_screenshot_img_arr, -1)  # RGB2BGR
        img = cv2.cvtColor(old_screenshot_img_arr, cv2.COLOR_BGR2GRAY)

        img_area = np.prod(img.shape)
        white_area = np.sum(img == 255)
        if white_area / img_area >= 0.99:  # skip white screenshots
            return True  # dirty
        return False

    def page_white_screen(self, driver, ts = 1.0):
        old_screenshot_img = Image.open(io.BytesIO(base64.b64decode(driver.get_screenshot_encoding())))
        old_screenshot_img = old_screenshot_img.convert("RGB")
        old_screenshot_img_arr = np.asarray(old_screenshot_img)
        old_screenshot_img_arr = np.flip(old_screenshot_img_arr, -1)  # RGB2BGR
        img = cv2.cvtColor(old_screenshot_img_arr, cv2.COLOR_BGR2GRAY)

        img_area = np.prod(img.shape)
        white_area = np.sum(img == 255)
        if white_area / img_area >= ts:  # skip white screenshots
            return True  # dirty
        return False

    def get_post_requests_traffic(self, driver):
        post_strings = [x for x in driver.get_log('performance') if 'POST' in x['message']]
        messages = ''.join([x['message'] for x in post_strings])
        postData = ''.join(re.findall('"postData":"([^"]*)"', messages))
        return postData

    '''get benign/suspicious classification result from its behaviours'''
    def get_benign(self, orig_url, driver, obfuscate=False, byimage=True):
        # by default, it is benign
        benign = True
        total_time = 0
        algo_time = 0

        # initialization
        Logger.spit('URL={}'.format(orig_url), caller_prefix=WebInteraction._caller_prefix, debug=True)
        try:
            driver.get(orig_url, allow_redirections=False)
            time.sleep(self.standard_sleeping_time)  # fixme: wait until page is fully loaded
        except Exception as e:
            Logger.spit('Exception when getting the URL {}'.format(e), caller_prefix=WebInteraction._caller_prefix, warning=True)
            raise

        sc = StateClass(driver, self.phishintention_cls)  # determine state
        sa = StateAction(driver, self.phishintention_cls)  # execute certain action

        # redirect to CRP page if staying on a non-CRP
        is_crp_page = sc.is_CRP()
        print('Is it a CRP page? {}'.format(is_crp_page))
        if not is_crp_page:
            _, _, current_url = sa.CRP_transition()
            if tldextract.extract(current_url).domain != tldextract.extract(orig_url).domain: # if CRP transition redirect to a third party page, come back
                try:
                    driver.get(orig_url, allow_redirections=False)
                    time.sleep(self.standard_sleeping_time)  # fixme: wait until page is fully loaded
                except Exception as e:
                    Logger.spit('Exception when getting the URL {}'.format(e), caller_prefix=WebInteraction._caller_prefix,
                                warning=True)
                    raise

        if obfuscate:
            if byimage:
                driver.obfuscate_inputs_byimage()
            else:
                driver.obfuscate_inputs()
        start_total_time = time.time()
        start_algo_time = time.time()
        # record original page source
        orig_url = driver.current_url()  # re-initialize the original URL
        driver.scroll_to_top()
        form = Form(driver, self.phishintention_cls, self.mmocr_model,
                    self.button_locator_model, obfuscate=obfuscate) # initialize form

        # repeatedly fill in inputs and submit
        ct_retry_loop = 0
        while len(form._buttons) > 0:

            # check whether there is any verifiable information (include hidden)
            if ct_retry_loop == 0 and (not form.contain_verifiable_inputs()):
                Logger.spit("No verifiable input", warning=True, caller_prefix=WebInteraction._caller_prefix)
                break

            # get the original logo features
            screenshot_encoding = driver.get_screenshot_encoding()
            returned_logos = self.phishintention_cls.return_all_logos(screenshot_encoding)
            if returned_logos is not None:  # if the original website has logo but the redirected site doesnt, return False anyway
                returned_logo = returned_logos[0]
                orig_logo_feat = self.phishintention_cls.return_logo_feat(returned_logo)
            else:
                orig_logo_feat = None

            # form filling and form submission
            filled_values = form.fill_all_inputs()
            prev_screenshot_elements = sc.screenshot_elements()
            prev_num_windows = len(driver.window_handles)
            prev_inputs = [form._input_rules[ii] for ii in range(len(form._inputs)) if \
                           form._input_visibilities[ii] == True]
            prev_src = driver.get_page_text()  # re-initialize page source

            # scrolling only happens at the first time, otherwise the screenshot changes just because we scroll it, e.g.: deepl.com
            # button maybe at the bottom, need to decide when to scroll
            if ct_retry_loop == 0 and (not form._button_visibilities[0]):
                Logger.spit("Scroll to the bottom since the buttons are invisible", debug=True, caller_prefix=WebInteraction._caller_prefix)
                driver.scroll_to_bottom()
                # scrolling change the screenshot
                form.button_reinitialize()

            change_in_webpage = form.submit(prev_num_windows=prev_num_windows) # form submission
            algo_time += time.time() - start_algo_time

            # wait for page loading
            time.sleep(10)

            start_algo_time = time.time()
            # the screenshot has changed, 0 is not responding
            has_redirection, orig_window = sc.does_redirection(orig_url=orig_url,
                                                              prev_num_windows=prev_num_windows,
                                                              prev_screenshot_elements=prev_screenshot_elements)
            # display a recaptcha
            has_recaptcha_displayed = sc.recaptcha_displayed()

            # redirection to third-party is an indicator of phishing
            if has_redirection:
                # if orig_logo_feat is not None:
                #     screenshot_encoding = driver.get_screenshot_encoding()
                #     returned_logos = self.phishintention_cls.return_all_logos(screenshot_encoding)
                #     if returned_logos is not None:  # if the original website has logo but the redirected site doesnt, return False anyway
                #         returned_logo = returned_logos[0]
                #         redirected_site_logo_feat = self.phishintention_cls.return_logo_feat(returned_logo)
                #         # logo matched!
                #         if redirected_site_logo_feat @ orig_logo_feat >= self.sim_ts:
                #             benign = False
                #             break
                benign = False
                break # some poorly developed benign websites also does random redirection

            # re-initialize form if the webpage changed
            if change_in_webpage:
                form = Form(driver, self.phishintention_cls, self.mmocr_model, self.button_locator_model)

            # normal webpage expects to see an visible error message
            has_error_displayed, has_filled_values_displayed = sc.has_error_message_displayed(prev_src,
                                                                                              filled_values)

            orig_url = driver.current_url()  # re-initialize the original URL
            curr_inputs = [form._input_rules[ii] for ii in range(len(form._inputs)) if \
                           form._input_visibilities[ii] == True]
            curr_verifiable_inputs = [x for x in curr_inputs if x in form.verifiable_inputs]

            # both the redirected page and the original page requires overlapping information -> login form is not bypassed
            if len(set(curr_inputs).intersection(set(prev_inputs))-{FormElement._DEFAULT_RULE}):
                same_information = True
                Logger.spit("Requires the same information again...", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
            else:
                same_information = False

            # before form submission, has the verifiable input but it is hidden,
            # dont make decision now, maybe next step the hidden input will appear, e.g microsoft login page
            # if len(prev_inputs) == 0:
            #     ct_retry_loop += 1
            # when we meet recaptcha, no way to further proceed, eg: yahoo login page redirects to a recaptcha
            if has_recaptcha_displayed:
                Logger.spit("Recaptcha is displayed", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
                break
            # No page transtion is defined as:
            #   Same credentials are required / Still have verifiable inputs, OR No change in page source, OR Error message is displayed, OR Previous filled values are displayed (# e.g. a 2FA is sent to your email xx@mail.com)
            elif has_error_displayed or \
                    has_filled_values_displayed or \
                    (not change_in_webpage) or \
                    same_information or \
                    len(curr_verifiable_inputs) > 0:
                ct_retry_loop += 1
            # Successful page transition AND data submission:
            else:
                postData = self.get_post_requests_traffic(driver)
                # print(postData)
                if postData and len(postData):
                    sentCredentials = [val for val in filled_values if (val and
                                       val in urllib.parse.unquote(postData))]
                    if len(sentCredentials):
                        Logger.spit("Credentials {} have been submitted to the server".format(sentCredentials),
                                    warning=True,
                                    caller_prefix=WebInteraction._caller_prefix)
                        benign = False
                        break
                ct_retry_loop += 1

            # still have verifiable input field left
            # elif len(curr_verifiable_inputs) > 0:
            #     Logger.spit("Still have verifiable input fields", warning=True,
            #                 caller_prefix=WebInteraction._caller_prefix)
            #     ct_retry_loop += 1
            # else:  # the webpage may turn to an error page because of connection problem, we need to avoid this FP
            #     is_blank = self.white_screen(driver)
            #     if not is_blank:
            #         Logger.spit("Suspicious webpage found!", warning=True,
            #                     caller_prefix=WebInteraction._caller_prefix)
            #         benign = False
            #         break
            #     else:
            #         ct_retry_loop += 1
            is_crp_page = sc.is_CRP()
            if not is_crp_page:
                break
            # control interaction length
            if ct_retry_loop >= self.interaction_depth:
                break

        algo_time += time.time() - start_algo_time
        total_time += time.time() - start_total_time
        return benign, algo_time, total_time

    '''this is a stricter version of benign/suspicious classifier, the main goal is to avoid FPs'''
    def get_benign_stricter(self, orig_url, driver):
        # by default, it is benign
        benign = True
        total_time = 0
        algo_time = 0

        '''Initialization'''
        Logger.spit('URL={}'.format(orig_url), caller_prefix=WebInteraction._caller_prefix, debug=True)
        try:
            success = driver.get(orig_url, allow_redirections=False)
            if not success: # if there is a redirection to other domain, we shall not report it
                return benign, algo_time, total_time
            time.sleep(self.standard_sleeping_time)  # fixme: wait until page is fully loaded
        except Exception as e:
            Logger.spit('Exception when getting the URL {}'.format(e), caller_prefix=WebInteraction._caller_prefix, warning=True)
            raise

        '''Ignore expired domain page'''
        title = driver.get_title()
        domain_tld = tldextract.extract(orig_url).domain + '.' + tldextract.extract(orig_url).suffix
        if domain_tld in title.lower() or 'domain' in title.lower() or 'blocked' in title.lower():
            Logger.spit("likely to be an expired page", warning=True, caller_prefix=WebInteraction._caller_prefix)
            return benign, algo_time, total_time
        # text = " ".join(driver.get_page_text().split('\n'))
        # text = " ".join(text.split(" "))
        # if re.search("domain.*(for sale|auction|expired|available|hosting)|parked free|WordPress|archived",
        #              text[:1000], re.I):
        #     Logger.spit("likely to be an expired page", warning=True, caller_prefix=WebInteraction._caller_prefix)
        #     return benign, algo_time, total_time

        '''Step 1: redirect to CRP page if staying on a non-CRP'''
        sc = StateClass(driver, self.phishintention_cls)  # determine state
        sa = StateAction(driver, self.phishintention_cls)  # execute certain action
        is_crp_page = sc.is_CRP()
        if not is_crp_page:
            Logger.spit("Not a CRP page, trying to find one...", debug=True, caller_prefix=WebInteraction._caller_prefix)
            _, _, current_url = sa.CRP_transition()
            if tldextract.extract(current_url).domain != tldextract.extract(orig_url).domain: # if CRP transition redirect to a third party page, come back
                try:
                    success = driver.get(orig_url, allow_redirections=False)
                    if not success:
                        return benign, algo_time, total_time
                    time.sleep(self.standard_sleeping_time)  # fixme: wait until page is fully loaded
                except Exception as e:
                    Logger.spit('Exception when getting the URL {}'.format(e), caller_prefix=WebInteraction._caller_prefix,
                                warning=True)
                    raise
        else:
            Logger.spit("Already a CRP page...", debug=True, caller_prefix=WebInteraction._caller_prefix)

        is_crp_page = sc.is_CRP()
        if not is_crp_page:
            Logger.spit("Cannot find a CRP page, benign...", warning=True,
                        caller_prefix=WebInteraction._caller_prefix)
            return benign, algo_time, total_time

        start_total_time = time.time()
        start_algo_time = time.time()

        orig_url = driver.current_url()  # re-initialize the original URL
        driver.scroll_to_top()
        form = Form(driver, self.phishintention_cls, self.mmocr_model, self.button_locator_model) # initialize form

        '''Step 2: repeatedly fill in inputs and submit'''
        ct_retry_loop = 0
        while len(form._buttons) > 0:

            # check whether there is any verifiable information (include hidden)
            if ct_retry_loop == 0 and (not form.contain_verifiable_inputs()):
                Logger.spit("No verifiable input", warning=True, caller_prefix=WebInteraction._caller_prefix)
                break

            if len(form._inputs) >= 30 or len(form._buttons) >= 30: # fixme: performance optimization, too many inputs/buttons, dont bother
                Logger.spit("Too many inputs/buttons, skip", warning=True, caller_prefix=WebInteraction._caller_prefix)
                break

            # we shall avoid registration page as it will always proceed to the next page, a signature for registration page is that it requires user to double confirm their password
            # another signature is it might contain sign-up related keywords in its URL
            if re.search('sign([^0-9a-zA-Z]|\s)*up|regist(er|ration)?', orig_url, re.IGNORECASE):
                Logger.spit("It is likely to be a registration page, not a login page", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
                break

            # form filling and form submission
            filled_values = form.fill_all_inputs()
            prev_screenshot_elements = sc.screenshot_elements()
            prev_num_windows = len(driver.window_handles)
            prev_inputs = [form._input_rules[ii] for ii in range(len(form._inputs)) if \
                           form._input_visibilities[ii] == True]
            prev_src = driver.get_page_text()  # re-initialize page source

            # scrolling only happens at the first time, otherwise the screenshot changes just because we scroll it, e.g.: deepl.com
            # button maybe at the bottom, need to decide when to scroll
            if ct_retry_loop == 0 and (not form._button_visibilities[0]):
                Logger.spit("Scroll to the bottom since the buttons are invisible", debug=True, caller_prefix=WebInteraction._caller_prefix)
                driver.scroll_to_bottom()
                # scrolling change the screenshot
                form.button_reinitialize()

            change_in_webpage = form.submit(prev_num_windows=prev_num_windows) # form submission
            algo_time += time.time() - start_algo_time

            # wait for page loading
            time.sleep(5)

            start_algo_time = time.time()
            # the screenshot has changed, 0 is not responding
            has_redirection, orig_window = sc.does_redirection(orig_url=orig_url,
                                                              prev_num_windows=prev_num_windows,
                                                              prev_screenshot_elements=prev_screenshot_elements)

            # display a recaptcha
            has_recaptcha_displayed = sc.recaptcha_displayed()

            '''Step 3: make decision'''
            # redirection to third-party sharing the same logo a clear indicator of phishing
            if has_redirection:
                benign = False
                Logger.spit("Redirect to a third-party site {}".format(
                    tldextract.extract(driver.current_url().domain)), warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
                Logger.spit("Suspicious webpage found!", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
                break

            # re-initialize form if the webpage changed
            if change_in_webpage:
                form = Form(driver, self.phishintention_cls, self.mmocr_model, self.button_locator_model)

            # normal webpage expects to see an visible error message
            has_error_displayed, has_filled_values_displayed = sc.has_error_message_displayed(prev_src, filled_values)

            orig_url = driver.current_url()  # re-initialize the original URL
            curr_inputs = [form._input_rules[ii] for ii in range(len(form._inputs)) if \
                           form._input_visibilities[ii] == True]
            curr_verifiable_inputs = [x for x in curr_inputs if x in form.verifiable_inputs]

            # both the redirected page and the original page requires overlapping information -> login form is not bypassed
            if len(set(curr_inputs).intersection(set(prev_inputs))-{FormElement._DEFAULT_RULE}):
                same_information = True
                Logger.spit("Requires the same information again...", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
            else:
                same_information = False

            # before form submission, has the verifiable input but it is hidden,
            # dont make decision now, maybe next step the hidden input will appear, e.g microsoft login page
            # if len(prev_inputs) == 0:
            #     ct_retry_loop += 1
            # when we meet recaptcha, no way to further proceed, eg: yahoo login page redirects to a recaptcha
            if has_recaptcha_displayed:
                Logger.spit("Recaptcha is displayed", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
                break
            # No page transtion is defined as:
            #   Same credentials are required, OR No change in page source, OR Error message is displayed, OR Previous filled values are displayed (# e.g. a 2FA is sent to your email xx@mail.com)
            elif has_error_displayed or \
                    has_filled_values_displayed or \
                    (not change_in_webpage) or \
                    same_information or \
                    len(curr_verifiable_inputs) > 0:
                ct_retry_loop += 1
            # Successful page transition AND data submission:
            else:
                postData = self.get_post_requests_traffic(driver)
                if postData and len(postData):
                    sentCredentials = [val for val in filled_values if (val and
                                       val in urllib.parse.unquote(postData))]
                    if len(sentCredentials):
                        Logger.spit("Credentials {} have been submitted to the server".format(sentCredentials),
                                    warning=True,
                                    caller_prefix=WebInteraction._caller_prefix)
                        Logger.spit("Suspicious webpage found!", warning=True,
                                    caller_prefix=WebInteraction._caller_prefix)
                        benign = False
                        break
                ct_retry_loop += 1

            # still have verifiable input field left
            # elif len(curr_verifiable_inputs) > 0:
            #     Logger.spit("Still have verifiable input fields", warning=True,
            #                 caller_prefix=WebInteraction._caller_prefix)
            #     ct_retry_loop += 1
            # else: # the webpage may turn to an error page because of connection problem, we need to avoid this FP
            #     screenshot_elements = sc.screenshot_elements()
            #     bincount_screen_elements = np.bincount(screenshot_elements)
            #     if np.sum(bincount_screen_elements > 0) >= 2:
            #         Logger.spit("Suspicious webpage found!", warning=True,
            #                     caller_prefix=WebInteraction._caller_prefix)
            #         benign = False
            #         break
            #     else:
            #         ct_retry_loop += 1

            # control interaction length
            if ct_retry_loop >= self.interaction_depth:
                Logger.spit("Exceed interaction depth, benign", warning=True,
                            caller_prefix=WebInteraction._caller_prefix)
                break

        algo_time += time.time() - start_algo_time
        total_time += time.time() - start_total_time
        return benign, algo_time, total_time
