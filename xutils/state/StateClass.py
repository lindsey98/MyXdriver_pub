import os

import selenium.common.exceptions

from ..forms.FormElement import FormElement
from ..forms.Form import Form
from ..URLUtils import URLUtils
import re
from ..Regexes import Regexes
from ..Logger import Logger
import numpy as np
from fuzzywuzzy import fuzz
from PIL import Image
import io
import base64
from unidecode import unidecode
from googletrans import Translator
import six
from google.cloud import translate_v2 as translate
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] ="/home/ruofan/git_space/phishing-research/knowledge_base/discoverylabel.json"

class StateClass():
    _caller_prefix = "StateClass"

    def __init__(self, driver_cls, phishintention_cls):
        self._driver = driver_cls
        self.PhishIntention = phishintention_cls
        self.regex_cut_thre = 200
        self.translator = Translator()

    '''
        Get unique strings for each paragraph when comparing two paragraphs
    '''
    @staticmethod
    def textdiff(paragraph1, paragraph2, ts=0.9):
        para1 = paragraph1
        para2 = paragraph2
        text_sim_matrix = np.zeros((len(para1), len(para2)))
        for i in range(len(para1)):
            for j in range(len(para2)):
                if para1[i] and para2[j]:
                    ratio = fuzz.ratio(para1[i].lower(), para2[j].lower())
                    text_sim_matrix[i][j] = ratio / 100
                else:
                    text_sim_matrix[i][j] = 0

        unique_text1 = [para1[i] for i in range(len(para1)) if np.sum(text_sim_matrix[i, :] > ts) == 0]
        unique_text2 = [para2[j] for j in range(len(para2)) if np.sum(text_sim_matrix[:, j] > ts) == 0]
        return unique_text1, unique_text2

    '''
        Check screenshot complexity
    '''
    def screenshot_elements(self):
        pred_boxes, pred_classes = self.PhishIntention.return_all_bboxes(self._driver.get_screenshot_encoding())
        if pred_boxes is None:
            return []
        else:
            return pred_classes.numpy().tolist()
    '''
        Has at least one input and one button
    '''
    def has_inputs_and_buttons(self, form: Form):
        if len(form._inputs) > 0 and len(form._buttons) > 0:
            return True
        return False

    '''
        Is a CRP page
    '''
    def is_CRP(self):
        ret_password, ret_username = self._driver.get_all_visible_username_password_inputs()
        num_username, num_password = len(ret_username), len(ret_password)
        cre_pred = self.PhishIntention.crp_classifier_reimplement(num_username=num_username,
                                                                  num_password=num_password,
                                                                  screenshot_encoding=self._driver.get_screenshot_encoding())
        Logger.spit("This page is a CRP page? {}".format("Yes" if cre_pred == 0 else "No"),
                    debug=True,
                    caller_prefix=StateClass._caller_prefix)
        return cre_pred == 0

    '''
        Redirection
    '''

    def does_redirection(self, orig_url, prev_num_windows, prev_screenshot_elements):

        current_window = self._driver.window_handles[0] # record current window
        if len(self._driver.window_handles) > prev_num_windows: # new window popped up
            for i in self._driver.window_handles:  # loop over all chrome windows
                self._driver.switch_to_window(i)
                current_url = self._driver.current_url()
                if current_url == orig_url:
                    current_window = i
                else:
                    new_window = i  # redirect on a new window
                    self._driver.switch_to_window(new_window)


        orig_domain = URLUtils.get_main_domain(orig_url)
        current_url = self._driver.current_url()
        redirected_domain = URLUtils.get_main_domain(current_url)

        # stay in the same domain
        if redirected_domain == orig_domain:
            # the best way to check redirection is through screenshot
            # because the URL might change when the error message pop up, but there is no major change in the screenshot
            # On the other hand, if there is a javascript popup (dis)appears, the screenshot has changed, but there is no change in URL
            # screenshot_elements = self.screenshot_elements()
            # bincount_prev_elements = np.bincount(prev_screenshot_elements)
            # bincount_curr_elements = np.bincount(screenshot_elements)
            # set_of_elements = min(len(bincount_prev_elements), len(bincount_curr_elements))
            # screenshot_ele_change_ts = np.sum(bincount_prev_elements) // 2
            # if np.sum(np.abs(bincount_curr_elements[:set_of_elements] - bincount_prev_elements[:set_of_elements])) > screenshot_ele_change_ts:
            #     Logger.spit("This page proceeds to the next page",
            #                 debug=True,
            #                 caller_prefix=StateClass._caller_prefix)
            #     return 1, current_window
            return 0, current_window # same URL, no change in screenshot

        # both the URL and the domain change
        else:
            Logger.spit("This page does redirect to third-party domain {}".format(redirected_domain),
                        warning=True,
                        caller_prefix=StateClass._caller_prefix)
            # todo: do not switch back
            # if len(self._driver.window_handles) > prev_num_windows:
            #     self._driver.switch_to_window(current_window)
            return 1, current_window

    # '''
    #     Has countdown timer (experimental)
    # '''
    # def has_countdown_timer(self):
    #     all_scripts = self._driver.get_all_scripts()
    #     for s in all_scripts:
    #         script, script_dompath, script_src, js_source = s
    #         if re.search(Regexes.TIME_SCRIPT, js_source, re.IGNORECASE):
    #             Logger.spit("This page has a countdown timer",
    #                         debug=True,
    #                         caller_prefix=StateClass._caller_prefix)
    #             return True
    #     return False

    '''
        Has recaptcha
    '''

    def recaptcha_displayed(self):
        # iframes = self._driver.get_all_iframes()
        # for frame in iframes:
        #     try:
        #         iframe_src = self._driver.get_attribute(frame, 'src')
        #     except selenium.common.exceptions.StaleElementReferenceException:
        #         continue
        #     except AttributeError:
        #         continue
        #     if re.search('captcha|seccode', iframe_src[:self.regex_cut_thre], re.IGNORECASE):
        #         return True
        #
        # imgs = self._driver.get_all_visible_imgs()
        # for img in imgs:
        #     try:
        #         img_src = self._driver.get_attribute(img, 'src')
        #     except selenium.common.exceptions.StaleElementReferenceException:
        #         continue
        #     if re.search('captcha|seccode', img_src[:self.regex_cut_thre], re.IGNORECASE):
        #         return True

        # scripts = self._driver.get_all_scripts()
        # for script in scripts:
        #     _, script_dompath, script_src, js_source = script
        #     if re.search('captcha|seccode', js_source[:self.regex_cut_thre], re.IGNORECASE):
        #         return True
        #     if re.search('captcha|seccode', script_src[:self.regex_cut_thre], re.IGNORECASE):
        #         return True

        # automatically render
        implicit_recaptcha_elements = self._driver.get_implicit_recaptcha()
        if len(implicit_recaptcha_elements) > 0:
            return True
        # explicit render
        scripts = self._driver.get_all_scripts()
        for script in scripts:
            _, script_dompath, script_src, js_source = script
            if 'grecaptcha.execute' in js_source or 'grecaptcha.render' in js_source:
                return True
        return False



    '''
        Has error message displayed
        Has previous filled values displayed
    '''
    def has_error_message_displayed(self, prev_src, filled_values):
        current_src = self._driver.get_page_text()  # in case javascript is executed
        unique_text1, unique_text2 = self.textdiff(prev_src.strip().split('\n'),
                                                   current_src.strip().split('\n'))
        unique_text2.append(self._driver.get_button_text())

        error_message = False

        for token in unique_text2[:min(5, len(unique_text2))]:
            token = token.rstrip()
            token = " ".join(token.split())
            if len(token) > self.regex_cut_thre:
                continue
            try:
                token = self.translator.translate(token, dest='en').text
            except Exception as e:
                try: # google cloud translation API as backup
                    translate_client = translate.Client()
                    if isinstance(token, six.binary_type):
                        token = token.decode("utf-8")
                    token = translate_client.translate(token, target_language='en')["translatedText"]
                except Exception as e:
                    # print(e)
                    pass
            Logger.spit("New text: {}".format(token), debug=True)
            # check error message
            if any([True if re.search(rule, token, re.IGNORECASE) else False for rule in
                    Regexes.ERROR_INCORRECT]):
                Logger.spit("Incorrect info error",
                            warning=True,
                            caller_prefix=StateClass._caller_prefix)
                error_message =  1
                break
            elif any([True if re.search(rule, token, re.IGNORECASE) else False for rule in
                      Regexes.ERROR_TRY_AGAIN]):
                Logger.spit("Try again error",
                            warning=True,
                            caller_prefix=StateClass._caller_prefix)
                error_message =  2
                break
            elif any([True if re.search(rule, token, re.IGNORECASE) else False for rule in Regexes.ERROR_CONNECTION]):
                Logger.spit("Connection error",
                            warning=True,
                            caller_prefix=StateClass._caller_prefix)
                error_message =  3
                break
            elif any([True if re.search(rule, token, re.IGNORECASE) else False for rule in Regexes.ERROR_FILE]):
                Logger.spit("File uploading error",
                            warning=True,
                            caller_prefix=StateClass._caller_prefix)
                error_message =  4
                break
            elif any([True if re.search(rule, token, re.IGNORECASE) else False for rule in Regexes.ERROR_BOT]):
                Logger.spit("not human|verify you are a human",
                            warning=True,
                            caller_prefix=StateClass._caller_prefix)
                error_message =  5
                break
            # elif re.search('went wrong|sorry,|error has occurred|oops|unavailable', unidecode(token), re.IGNORECASE):
            #     Logger.spit("General error",
            #                 warning=True,
            #                 caller_prefix=StateClass._caller_prefix)
            #     error_message = 6
            #     break
            # elif re.search("undefined index|undefined variable|php error|include\(\)|ERR_EMPTY_RESPONSE", unidecode(token), re.IGNORECASE):
            #     Logger.spit("PHP error",
            #                 warning=True,
            #                 caller_prefix=StateClass._caller_prefix)
            #     error_message = 7
            #     break


        filled_values_displayed = False
        for value in filled_values:
            if value is None:
                continue
            for token in unique_text2[:min(5, len(unique_text2))]:
                if re.search(value, unidecode(token[:self.regex_cut_thre]), re.IGNORECASE):
                    Logger.spit("The previous filled values are displayed",
                                warning=True,
                                caller_prefix=StateClass._caller_prefix)
                    filled_values_displayed = True
                    break
            if filled_values_displayed:
                break

        return error_message, filled_values_displayed
    '''
        Is empty page
    '''
    def empty_page(self):
        source = self._driver.page_source()
        if source == "<html><head></head><body></body></html>":
            Logger.spit("Empty page", warning=True, caller_prefix=StateClass._caller_prefix)
            return True
        elif (
                "404 Not Found" in source
                or "<p>The requested URL was not found on this server.</p>" in source
                or "Server at localhost Port" in source
                or "<h1>404 Not Found</h1>" in source
        ):
            Logger.spit("Empty page", warning=True, caller_prefix=StateClass._caller_prefix)
            return True
        return False



