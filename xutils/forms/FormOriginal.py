#!/usr/bin/python

import re

from .FormElementOriginal import FormElementOriginal
from ..Logger import Logger
from ..Exceptions import stringify_exception
from ..Regexes import RegexesOriginal

from time import sleep


class FormOriginal():
    _caller_prefix = "FormOriginal"
    _MAX_STEPS = 5

    def __init__(self, driver, form):
        self._driver = driver
        self._form = form
        self._str, self._str_tokenized = self._gen_form_str()
        self._has_captcha = self._detect_captcha()

    ''' Generate a form representation string. This is different from the form signature and is used for string matching against known regexes
    '''

    def _gen_form_str(self):
        elid = self._form.get_attribute("id")
        elname = self._form.get_attribute("name")
        elaction = self._form.get_attribute("action")
        elclass = self._form.get_attribute("class")
        elstr = "%s|%s|%s|%s" % (elid, elname, elaction, elclass)
        elset = set([elid, elname, elaction, elclass]) - set([None]) - set(["undefined"]) - set([""])
        return "%s|" % "|".join(elset), frozenset(elset)

    ''' Check if the form matches any known/common sign-up form regexes
    '''

    def is_signup_form(self):
        return True if re.search(RegexesOriginal.SIGNUP, self._str, re.IGNORECASE) else False

    ''' Check if the form matches any known/common `other` form regexes
    '''

    def is_other_form(self):
        return True if re.search(RegexesOriginal.OTHER_FORM, self._str, re.IGNORECASE) else False

    ''' Check the form's source, to determine whether it contains a (re-)CAPCTHA or not
    '''

    def _detect_captcha(self):
        form_src = self._driver.get_element_src(self._form, full=True)
        if re.search(RegexesOriginal.CAPTCHA, form_src, re.IGNORECASE):
            return True
        return False

    def has_captcha(self):
        return self._has_captcha

    ''' Check if the form is likely on the top layer
    '''

    def is_on_top_layer(self):
        # First check if the form is on top. If yes, we're good
        formOnTop = self._driver.isOnTopLayer(self._form)
        if formOnTop:
            return True
        # Otherwise, check if more than half of its elements are on top
        elements = self._form.find_elements_by_tag_name("label") + self._form.find_elements_by_tag_name(
            "input") + self._form.find_elements_by_tag_name("textarea") + \
                   self._form.find_elements_by_tag_name("select") + self._form.find_elements_by_tag_name("button")
        elementsOnTop = 0
        for element in elements:
            if self._driver.isOnTopLayer(element):
                elementsOnTop += 1
        if elementsOnTop >= len(elements) / 2:
            return True
        return False

    def _assign_labels(self):
        label_str = ""
        last_label_str = ""
        label_for_id = None

        label_fors = {}

        elements = []

        self._radio_check = True

        # First traverse the form elements one by one, in the order they appear and collect labels for each input
        # Intuition is that inputs are placed right after their accompanying <label> descriptions
        for element in self._driver.get_descendants(self._form):
            form_element = FormElementOriginal(self._driver, element)
            element_label = None

            # # # TEST # # #
            # Leave those even if hidden
            if self._driver.get_type(form_element.get_web_element()) == "checkbox":
                pass
            elif self._driver.get_type(form_element.get_web_element()) == "radio":
                if self._driver.is_checked(
                        form_element.get_web_element()):  # If a radio is already checked, don't check any others
                    self._radio_check = False
            elif not self._driver.is_displayed(form_element.get_web_element()):
                continue
            ################

            if self._driver.is_form_input(form_element.get_web_element()):
                if not label_str:
                    label_str = last_label_str  # propagate last known label to unlabelled inputs
                form_element.add_possible_label(label_str)
                elements.append(form_element)
                last_label_str = label_str
                label_str = ""  # reset label string for next input
            elif self._driver.is_tag(form_element.get_web_element(), "label"):
                label_str = form_element.get_prop("textContent")
                label_for_id = form_element.get("for")
                if label_for_id:
                    if label_for_id in label_fors:
                        label_fors[label_for_id].append(label_str)
                    else:
                        label_fors[label_for_id] = [label_str]
        # Assign dedicated labels to each element (if found)
        for element in elements:
            eid = element.get("id")
            for label_str in label_fors.get(eid, []):
                element.add_label(label_str)

        return elements


    def get_labels(self):
        _labels = []
        try:
            elements = self._assign_labels()
            for element in elements:
                el_str = element.get_element_str()
                el_lbls = element.get_labels(stringified=True)
                el_plbls = element.get_possible_labels(stringified=True)
                _labels.append(
                    {"str": el_str,
                     "labels": el_lbls,
                     "possible_labels": el_plbls
                     }
                )
        except Exception as e:
            Logger.spit("Error while assigning labels", warning=True, caller_prefix=FormOriginal._caller_prefix)
            Logger.spit("%s" % stringify_exception(e), warning=True, caller_prefix=FormOriginal._caller_prefix)
        return _labels

    ''' Fill the form
    '''

    def fill(self, submit=True, required_only=False, override_rules={}):
        _values = []

        cur_url = self._driver.current_url()
        self._driver.store_reference_element(cur_url)
        filtered_elements = []

        try:
            elements = self._assign_labels()
            for element in elements:
                if required_only and not element.is_required():
                    continue
                el_str = element.get_element_str()
                el_lbls = element.get_labels(stringified=True)
                el_plbls = element.get_possible_labels(stringified=True)
                dom_path = self._driver.get_dompath(element.get_web_element())

                self._driver.set_value(element.get_web_element(), "")
                val, rule = element.fill(override_rules=override_rules, radio_check=self._radio_check)
                filtered_elements.append(element.get_web_element())
                _values.append(
                    {
                     "dom": dom_path,
                     "str": el_str,
                     "labels": el_lbls,
                     "possible_labels": el_plbls,
                     "value": val,
                     "rule": rule
                     }
                )

            if _values and submit:
                submit_btns = [sb for sb in self._driver.find_elements_by_tag_name("button", webelement=self._form) if
                               self._driver.is_displayed(sb)]
                submit_inputs = [si for si in self._driver.find_elements_by_tag_name("input", webelement=self._form) if
                                 (self._driver.is_type(si, "submit") or self._driver.is_type(si,
                                                                                             "button")) and self._driver.is_displayed(
                                     si)]
                submit_as = [sa for sa in self._driver.find_elements_by_tag_name("a", webelement=self._form) if
                             self._driver.is_displayed(sa) and (
                                         re.search(RegexesOriginal.SIGNUP, self._driver.get_element_src(sa),
                                                   re.IGNORECASE) or re.search(r"submit",
                                                                               self._driver.get_element_src(sa),
                                                                               re.IGNORECASE))]
                submit_btns += submit_inputs
                if not submit_btns:  # use detected <a> elements ONLY if we haven't found a submit button/input
                    submit_btns += submit_as

                if len(submit_btns) > 0:
                    submit_btns_location = self._driver.get_location(submit_btns[0])

                if len(submit_btns) == 1:
                    Logger.spit("Located exactly one submit button. Will click it..", caller_prefix=FormOriginal._caller_prefix)
                    if not self._driver.click(submit_btns[0]):
                        Logger.spit("Could not click it. Will submit..", warning=True,
                                    caller_prefix=FormOriginal._caller_prefix)
                        self._driver.submit(self._form)
                else:
                    Logger.spit("Located %s. Will submit.." % "no submit buttons" if len(
                        submit_btns) == 0 else "more than one submit buttons", warning=True,
                                caller_prefix=FormOriginal._caller_prefix)
                    self._driver.submit(self._form)
                if not self._driver.is_redirected(cur_url):
                    Logger.spit("Form submission does not seem to cause a redirection..", warning=True,
                                caller_prefix=FormOriginal._caller_prefix)
        except Exception as e:  # Screw the exceptions, if we submitted something we still need to return
            Logger.spit("%s" % stringify_exception(e), warning=True, caller_prefix=FormOriginal._caller_prefix)
            raise

        if _values and submit:
            if len(submit_btns) > 0:
                return filtered_elements, _values, submit_btns[0], submit_btns_location
        return filtered_elements, _values, None, None