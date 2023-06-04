#!/usr/bin/python
import time

import numpy as np
import selenium.common.exceptions

from .FormElement import FormElement
from ..Logger import Logger
from ..Coordinates import bbox_boarder_dist_simple
from ..TextMatching import special_character_replacement
from ..Regexes import Regexes

from PIL import Image
import io
import base64
import os


class Form():
    _caller_prefix = "Form"
    _unknown_label = "UNKNOWN"
    verifiable_inputs = {Regexes.PASSWORD, Regexes.USERID, Regexes.USERNAME}

    def __init__(self, driver,
                 phishintention_cls,
                 mmocr_model,
                 submission_button_locator,
                 rule_matching=True,
                 obfuscate=False):

        self._driver = driver
        self.PhishIntention = phishintention_cls
        self._mmocr_model = mmocr_model
        self._submission_button_locator = submission_button_locator
        self.obfuscate = obfuscate
        self._rule_matching = rule_matching

        # find labels and their coordinates
        self._labels_locations = self.get_labels_elements_cv()  # fixme
        # find inputs
        self._inputs, self._inputs_dom, self._input_rules, self._input_visibilities, self._input_etypes, self._inputs_locations = self._get_input_elements()
        # find clickable buttons
        self._buttons, self._buttons_dom, self._button_rules, self._button_visibilities, self._buttons_locations = self._get_button_elements()

        self._all_numeric_buttons = self._driver.get_all_numeric_buttons()

        Logger.spit("Number of inputs = {}, Number of buttons = {}".format(len(self._inputs), len(self._buttons)),
                    debug=True, caller_prefix=Form._caller_prefix)

    def erase_input_placeholder(self):
        self._driver._invoke(self._driver.execute_script, '''
            let inputslist = document.getElementsByTagName('input');
            for (let i = 0; i <= inputslist.length; i++) {
                let input = inputslist[i];
                console.log(input);

                try{
                    let nodetag = input.tagName.toLowerCase();
                    let etype = input.type;
                    let location = get_loc(input);
                    if (nodetag == "select" || etype == "submit" || etype == "button" || etype == "image" || etype == "reset" || etype == "radio" || etype == "checkbox" || etype == "hidden") {
                        continue;
                    }
                    if (location[2] - location[0] <= 5 || location[3] - location[1] <= 5){
                        continue;
                    }
                    // element obfuscation
                    input.setAttribute('placeholder','');
                }
                catch(err){
                    console.log(err);
                    continue;
                }
            } 
        '''
                             )

    """
		Reinitialize when the screenshot has changed
	"""

    def button_reinitialize(self):
        # find clickable elements
        self._buttons, self._buttons_dom, self._button_rules, self._button_visibilities, self._buttons_locations = self._get_button_elements()
        # re-compute locations
        self._inputs_locations = list(map(lambda e: self._driver.get_location(e), self._inputs))

    """
		Detect text in the element by OCR
	"""

    def _call_ocr(self, input_ele_loc):
        try:
            screenshot_img = Image.open(io.BytesIO(base64.b64decode(self._driver.get_screenshot_encoding())))
        except:
            return ''
        screenshot_img = screenshot_img.convert("RGB")
        x1, y1, x2, y2 = input_ele_loc
        ele_screenshot = screenshot_img.crop((x1, y1, x2, y2))

        ele_screenshot_arr = np.asarray(ele_screenshot)
        ele_screenshot_arr = np.flip(ele_screenshot_arr, -1)  # RGB2BGR

        try:
            result = self._mmocr_model.readtext(img=ele_screenshot_arr, print_result=False)
        except:
            return ''
        if len(result) > 0:
            if len(result[0]['text']) > 0:
                return result[0]['text']
        return ''

    """
        Detect text in the element by OCR (on elements screenshot)
    """

    def _call_ocr_element(self, element):
        try:
            ele_screenshot = Image.open(io.BytesIO(base64.b64decode(element.screenshot_as_base64)))
        except:
            return ''
        ele_screenshot = ele_screenshot.convert("RGB")
        ele_screenshot_arr = np.asarray(ele_screenshot)
        ele_screenshot_arr = np.flip(ele_screenshot_arr, -1)  # RGB2BGR

        try:
            result = self._mmocr_model.readtext(img=ele_screenshot_arr, print_result=False)
        except:
            return ''
        if len(result) > 0:
            if len(result[0]['text']) > 0:
                return result[0]['text']
        return ''

    """
		Get all input elements and their matched filling rules
	"""

    def _get_input_elements(self):

        elements, elements_dom = self._driver.get_all_inputs()
        if self.obfuscate:
            self.erase_input_placeholder()
        elements_loc = list(map(lambda e: self._driver.get_location(e), elements))

        cv_elements, cv_elements_dom, cv_elements_loc = self.get_input_elements_cv()  # also add the input elements reported from CV
        for it, b in enumerate(cv_elements):
            if b not in elements:
                elements.append(b)
                elements_dom.append(cv_elements_dom[it])
                elements_loc.append(cv_elements_loc[it])

        filter_elements = []
        filter_elements_dom = []
        rules = []
        visibilities = []
        types = []
        locations = []

        for jj in range(len(elements)):
            element = elements[jj]
            element_dom = elements_dom[jj]
            element_loc = elements_loc[jj]
            visible = self._driver.check_visibility(element_loc)
            try:
                FE = FormElement(self._driver, element)
                # Step1: use regex to match HTML attributes
                matched_rule = FE._decide_rule_inputs()
                if matched_rule is not None:
                    filter_elements.append(element)
                    filter_elements_dom.append(element_dom)
                    rules.append(matched_rule)
                    visibilities.append(visible)
                    types.append(FE._etype)
                    locations.append(element_loc)
                else:
                    if visible:
                        # Step2: use regex to match OCR result
                        start_time = time.time()
                        ocr_string_this_input = self._call_ocr(element_loc)
                        end_time = time.time()
                        Logger.spit("Run OCR on input element {} takes time: {:.4f}s".format(jj, end_time - start_time),
                                    debug=True, caller_prefix=Form._caller_prefix)
                        matched_rule = FE._decide_input_rule_given_str(ocr_string_this_input)
                        if matched_rule is not None:
                            filter_elements.append(element)
                            filter_elements_dom.append(element_dom)
                            rules.append(matched_rule)
                            visibilities.append(visible)
                            types.append(FE._etype)
                            locations.append(element_loc)

                        else:
                            # Step3: use regex to match the label near the input
                            # 3.1 get previous sibling element
                            closest_label = self._driver.get_element_prev_sibling(element)
                            start_time = time.time()
                            ocr_string_label = self._call_ocr_element(closest_label)
                            end_time = time.time()
                            Logger.spit("Run OCR on input element {} 's nearest label takes time: {:.4f}s".format(jj,
                                                                                                                  end_time - start_time),
                                        debug=True, caller_prefix=Form._caller_prefix)
                            matched_rule = FE._decide_input_rule_given_str(ocr_string_label)

                            if matched_rule is not None:
                                filter_elements.append(element)
                                filter_elements_dom.append(element_dom)
                                rules.append(matched_rule)
                                visibilities.append(visible)
                                types.append(FE._etype)
                                locations.append(element_loc)

                            else:
                                # 3.2 get PhishIntention reported labels
                                if len(self._labels_locations) > 0:
                                    input_ele_to_labels_dist, *_ = bbox_boarder_dist_simple(
                                        [self._driver.get_location(element)],
                                        self._labels_locations)
                                    input_ele_to_labels_dist = input_ele_to_labels_dist[0]  # N_labels
                                    closest_label_loc = self._labels_locations[np.argsort(input_ele_to_labels_dist)[0]]

                                    start_time = time.time()
                                    ocr_string_label = self._call_ocr(closest_label_loc)
                                    end_time = time.time()
                                    Logger.spit(
                                        "Run OCR on input element {} 's nearest label takes time: {:.4f}s".format(
                                            jj, end_time - start_time),
                                        debug=True, caller_prefix=Form._caller_prefix)
                                    matched_rule = FE._decide_input_rule_given_str(ocr_string_label)

                                    if matched_rule is not None:
                                        # one label can only correspond to one input, the label cannot be re-assigned to other inputs
                                        self._labels_locations.pop(np.argsort(input_ele_to_labels_dist)[0])
                                        filter_elements.append(element)
                                        filter_elements_dom.append(element_dom)
                                        rules.append(matched_rule)
                                        visibilities.append(visible)
                                        types.append(FE._etype)
                                        locations.append(element_loc)

                if matched_rule is None:
                    matched_rule = FormElement._DEFAULT_RULE
                    filter_elements.append(element)
                    filter_elements_dom.append(element_dom)
                    rules.append(matched_rule)
                    visibilities.append(visible)
                    types.append(FE._etype)
                    locations.append(element_loc)


            except Exception as e:
                Logger.spit("Error {} when trying to decide rule".format(e), warning=True,
                            caller_prefix=Form._caller_prefix)
        return filter_elements, filter_elements_dom, rules, visibilities, types, locations

    '''
		Get all button elements
	'''

    def _get_button_elements(self):

        elements, elements_dom, elements_loc = [], [], []
        # report submission button
        cv_elements, cv_elements_dom, cv_elements_loc = self.get_button_elements_cv()

        # only if submission button is not reported from CV model, use HTML as backup
        if len(cv_elements) == 0:
            elements, elements_dom = self._driver.get_all_buttons()
            elements_loc = list(map(lambda e: self._driver.get_location(e), elements))

        for it, b in enumerate(cv_elements):
            if b not in elements:
                elements.append(b)
                elements_dom.append(cv_elements_dom[it])
                elements_loc.append(cv_elements_loc[it])

        filter_elements = []
        filter_elements_dom = []
        rules = []
        visibilities = []
        locations = []

        for jj in range(len(elements)):
            element = elements[jj]
            element_dom = elements_dom[jj]
            element_loc = elements_loc[jj]
            visible = self._driver.check_visibility(element_loc)
            try:
                if visible:
                    # this step is only to check it is NOT a "register" button
                    FE = FormElement(self._driver, element)
                    matched_rule_relaxed, matched_rule_strict = FE._decide_rule_buttons()

                    if matched_rule_strict:
                        filter_elements.insert(0, element)
                        filter_elements_dom.insert(0, element_dom)
                        rules.insert(0, matched_rule_strict)
                        visibilities.insert(0, visible)
                        locations.insert(0, element_loc)
                    elif matched_rule_relaxed:
                        filter_elements.append(element)
                        filter_elements_dom.append(element_dom)
                        rules.append(matched_rule_relaxed)
                        visibilities.append(visible)
                        locations.append(element_loc)

            except Exception as e:
                Logger.spit("Error {} when trying to decide rule".format(e), warning=True,
                            caller_prefix=Form._caller_prefix)

        return filter_elements, filter_elements_dom, rules, visibilities, locations

    """
		Use CV method to get all buttons
	"""

    def get_button_elements_cv(self):
        pred_boxes = self._submission_button_locator.return_submit_button(self._driver.get_screenshot_encoding())
        if pred_boxes is None:
            return [], [], []
        pred_boxes = pred_boxes.tolist()
        elements, elements_dom, elements_loc_raw = self._driver.get_all_elements_from_coordinate_list(pred_boxes)
        # It is possible that finding element by coordinates can return irrelavant elements, so we need to have a check whether the found elements positions are correct
        elements_loc_cross_check = list(map(lambda e: self._driver.get_location(e), elements))

        filtered_elements, filtered_elements_dom, filtered_elements_loc = [], [], []
        for jj in range(len(elements)):
            xcross1, ycross1, xcross2, ycross2 = elements_loc_cross_check[jj]
            if xcross2 - xcross1 <= 0 or ycross2 - ycross1 <= 0:
                continue
            else:
                filtered_elements.append(elements[jj])
                filtered_elements_dom.append(elements_dom[jj])
                filtered_elements_loc.append(elements_loc_raw[jj])

        return filtered_elements, filtered_elements_dom, filtered_elements_loc

    """
		Use CV method to get all labels
	"""

    def get_labels_elements_cv(self):

        pred_boxes = self.PhishIntention.return_all_bboxes4type(self._driver.get_screenshot_encoding(), 'label')
        if pred_boxes is None:
            return []
        pred_boxes = pred_boxes.tolist()
        return pred_boxes

    """
		Use CV method to get all inputs
	"""

    def get_input_elements_cv(self):
        pred_boxes = self.PhishIntention.return_all_bboxes4type(self._driver.get_screenshot_encoding(), 'input')
        if pred_boxes is None:
            return [], [], []
        pred_boxes = pred_boxes.tolist()
        elements, elements_dom, elements_pred_boxes = self._driver.get_all_elements_from_coordinate_list(pred_boxes)
        return elements, elements_dom, elements_pred_boxes

    """
		Sort buttons based on connectedness and proximity
	"""

    def sort_buttons_by_affinity_to_inputs(self, screenH=1080):
        forbidden_input_etypes = ['hidden', "submit", "reset", "search"]
        # Filter input locations, ignore checkbox, radio buttons, ignore zero-area inputs
        input_locations = [self._inputs_locations[ii] for ii in range(len(self._inputs_locations)) if
                           self._input_etypes[ii] not in forbidden_input_etypes and \
                           self._input_visibilities[ii] and \
                           self._input_rules[ii] != FormElement._DEFAULT_RULE
                           ]
        # Horizontal coordinate distance
        if len(self._buttons_locations) and len(input_locations):
            vertical_dist, _, buttons_below, _, _, _, _, _ = bbox_boarder_dist_simple(self._buttons_locations,
                                                                                      input_locations)
            buttons_correct = np.prod(buttons_below, axis=-1)
            coord_dist = np.amin(vertical_dist / screenH, axis=-1)  # distance to the nearest input
            if np.sum(buttons_correct == 0) != len(buttons_correct):
                coord_dist = np.where(buttons_correct == 1, coord_dist,
                                      1.)  # the correct button should be below the inputs

            mixup_dist = coord_dist
            sorted_index = np.argsort(mixup_dist)
            self._buttons = [self._buttons[x] for x in sorted_index]
            self._buttons_dom = [self._buttons_dom[x] for x in sorted_index]
            self._button_visibilities = [self._button_visibilities[x] for x in sorted_index]
            self._buttons_locations = [self._buttons_locations[x] for x in sorted_index]
            self._button_rules = [self._button_rules[x] for x in sorted_index]

    """
		Fill in inputs with specified rule
	"""

    def fill_all_inputs(self):
        filled_values = []
        for ct, element in enumerate(self._inputs):
            FE = FormElement(self._driver, element)
            etext = FE._text
            try:
                value = FE.fill(rule=self._input_rules[ct],
                                numeric_buttons=self._all_numeric_buttons)
            except selenium.common.exceptions.StaleElementReferenceException as e:
                Logger.spit("Error {} when trying to fill in element".format(e), warning=True,
                            caller_prefix=Form._caller_prefix)
                continue
            if self._input_rules[ct] in Form.verifiable_inputs:
                filled_values.append(value)
            Logger.spit("Notice: filled value {} in input field {}".format(value, etext), debug=True,
                        caller_prefix=Form._caller_prefix)
        return filled_values

    """
		Click submit buttons
	"""

    def submit(self, prev_num_windows, cached_button_element=None):

        prev_src = self._driver.get_page_text()
        prev_html = self._driver.rendered_source()

        if len(self._buttons) == 0:
            return False
        if cached_button_element is not None:
            element = cached_button_element
        else:
            element = self._buttons[0]  # fixme: I only click the most relevant button for conservativeness

        etext = self._driver.get_text(element)
        if (not etext) or len(etext)==0:
            etext = self._driver.get_attribute(element, "value")
        Logger.spit("Try clicking button {} ...".format(etext), debug=True,
                    caller_prefix=Form._caller_prefix)
        try:
            self._driver.move_to_element(element)
            click_success = self._driver.click(element)
        except selenium.common.exceptions.StaleElementReferenceException:
            return False

        if click_success:
            Logger.spit("Clicking button {} successfully".format(etext), debug=True,
                        caller_prefix=Form._caller_prefix)
            current_src = self._driver.get_page_text()
            current_html = self._driver.rendered_source()
            current_num_windows = len(self._driver.window_handles)

            # new window is open
            if current_num_windows != prev_num_windows:
                Logger.spit("Clicking the button opens a new window", debug=True,
                            caller_prefix=Form._caller_prefix)
                return True
            # change in page source
            elif special_character_replacement(prev_src.lower()).replace(' ', '') != special_character_replacement(
                    current_src.lower()).replace(' ', '') or \
                    special_character_replacement(prev_html.lower()).replace(' ', '') != special_character_replacement(
                current_html.lower()).replace(' ', ''):
                Logger.spit("Detect changes in webpage source", debug=True,
                            caller_prefix=Form._caller_prefix)
                return True
            # NO change in page source
            else:
                Logger.spit("No change in webpage", warning=True,
                            caller_prefix=Form._caller_prefix)
                return False
        else:
            Logger.spit("No change in webpage", warning=True,
                        caller_prefix=Form._caller_prefix)
            return False

    """
		Count number of verifiable inputs
	"""

    def contain_verifiable_inputs(self):
        input_rules = self._input_rules
        if any([x in input_rules for x in Form.verifiable_inputs]):
            return True
        return False