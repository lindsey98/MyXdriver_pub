import numpy as np
import selenium.common.exceptions
from phishintention.phishintention_config import load_config, driver_loader
from phishintention.src.crp_classifier_utils.bit_pytorch.grid_divider import coord2pixel_reverse
from phishintention.src.AWL_detector import find_element_type
from phishintention.src.OCR_aided_siamese import pred_siamese_OCR
from phishintention.src.OCR_aided_siamese import phishpedia_classifier_OCR
from phishintention.src.crp_classifier import html_heuristic, credential_classifier_mixed_al
from phishintention.src.crp_locator import dynamic_analysis
from ..XDriver import XDriver
import time
import re
from .Regexes import Regexes
from .Logger import Logger
from PIL import Image
import io
import base64
import torch
import torch.nn.functional as F
import torchvision.transforms as transform
import cv2
import os
from phishintention.src.OCR_siamese_utils.utils import brand_converter, resolution_alignment
import pickle
import tldextract
import socket

'''I re-implement PhishIntention to be better integrated with XDriver,
the CRP classifier and Siamese are using the real-time screenshot and HTML'''
class PhishIntentionWrapper():

    _caller_prefix = "PhishIntentionWrapper"
    SIAMESE_THRE_RELAX = 0.85
    _RETRIES = 3
    _DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

    def __init__(self, reload_targetlist=False):
        self.AWL_MODEL, self.CRP_CLASSIFIER, self.CRP_LOCATOR_MODEL, self.SIAMESE_MODEL, self.OCR_MODEL, self.SIAMESE_THRE, self.LOGO_FEATS, self.LOGO_FILES, self.DOMAIN_MAP_PATH = load_config(device=self._DEVICE, reload_targetlist=reload_targetlist)
        self.CRP_CLASSIFIER.to(PhishIntentionWrapper._DEVICE)
        self.OCR_MODEL.to(PhishIntentionWrapper._DEVICE)

    def reset_model(self, config_path):
        self.AWL_MODEL, self.CRP_CLASSIFIER, self.CRP_LOCATOR_MODEL, self.SIAMESE_MODEL, self.OCR_MODEL, self.SIAMESE_THRE, \
        self.LOGO_FEATS, self.LOGO_FILES, self.DOMAIN_MAP_PATH = load_config(cfg_path=config_path, device=self._DEVICE)
        self.CRP_CLASSIFIER.to(PhishIntentionWrapper._DEVICE)
        self.OCR_MODEL.to(PhishIntentionWrapper._DEVICE)
        print('Length of reference list = {}'.format(len(self.LOGO_FEATS)))

    def return_logo_feat(self, logo: Image):
        img_feat = pred_siamese_OCR(img=logo,
                                    model=self.SIAMESE_MODEL,
                                    ocr_model=self.OCR_MODEL)
        return img_feat

    def predict_n_save_logo(self, shot_path):
        '''
            use AWL detector to crop and save logo
            Args:
                shot_path: path to screenshot
        '''
        with open(shot_path, "rb") as image_file:
            screenshot_encoding = base64.b64encode(image_file.read())
        returned_logos = self.return_all_logos(screenshot_encoding)
        if returned_logos is None:
            return None, None  # logo is not reported

        # save the logo
        reference_logo = returned_logos[0]
        logo_path = shot_path.replace('shot.png', 'logo.png')
        # if not os.path.exists(logo_path):
        reference_logo.save(logo_path)
        return logo_path, reference_logo

    def siamese_inference_OCR_reimplement(self, domain_map, reference_logo):

        img_feat = self.return_logo_feat(reference_logo)
        print('logo feature returned')
        # sim_list = self.LOGO_FEATS @ img_feat.T  # take dot product for every pair of embeddings (Cosine Similarity)
        sim_list = np.matmul(self.LOGO_FEATS, img_feat.T)
        pred_brand_list = self.LOGO_FILES

        assert len(sim_list) == len(pred_brand_list)

        ## get top 3 brands
        idx = np.argsort(sim_list)[::-1][:3]
        pred_brand_list = np.array(pred_brand_list)[idx]
        sim_list = np.array(sim_list)[idx]

        # top1,2,3 candidate logos
        top3_logolist = [Image.open(x) for x in pred_brand_list]
        top3_brandlist = [brand_converter(os.path.basename(os.path.dirname(x))) for x in pred_brand_list]
        top3_domainlist = [domain_map[x] for x in top3_brandlist]
        top3_simlist = sim_list
        print('top3 similar logo returned')

        for j in range(3):
            predicted_brand, predicted_domain = None, None

            ## If we are trying those lower rank logo, the predicted brand of them should be the same as top1 logo, otherwise might be false positive
            if top3_brandlist[j] != top3_brandlist[0]:
                continue

            ## If the largest similarity exceeds threshold
            if top3_simlist[j] >= self.SIAMESE_THRE:
                predicted_brand = top3_brandlist[j]
                predicted_domain = top3_domainlist[j]
                final_sim = top3_simlist[j]

            ## Else if not exceed, try resolution alignment, see if can improve
            else:
                cropped, candidate_logo = resolution_alignment(reference_logo, top3_logolist[j])
                img_feat = self.return_logo_feat(cropped)
                logo_feat = self.return_logo_feat(candidate_logo)
                final_sim = logo_feat.dot(img_feat)
                if final_sim >= self.SIAMESE_THRE:
                    predicted_brand = top3_brandlist[j]
                    predicted_domain = top3_domainlist[j]
                else:
                    break  # no hope, do not try other lower rank logos

            ## If there is a prediction, do aspect ratio check
            if predicted_brand is not None:
                ratio_crop = reference_logo.size[0] / reference_logo.size[1]
                ratio_logo = top3_logolist[j].size[0] / top3_logolist[j].size[1]
                # aspect ratios of matched pair must not deviate by more than factor of 2.5
                if max(ratio_crop, ratio_logo) / min(ratio_crop, ratio_logo) > 2.5:
                    continue  # did not pass aspect ratio check, try other
                # If pass aspect ratio check, report a match
                else:
                    return predicted_brand, predicted_domain, final_sim

        return None, None, top3_simlist[0]

    def phishpedia_classifier_OCR_reimplement(self, domain_map_path, reference_logo, url):
        # targetlist domain list
        pred_target, siamese_conf = None, None
        with open(domain_map_path, 'rb') as handle:
            domain_map = pickle.load(handle)

        target_this, domain_this, this_conf = self.siamese_inference_OCR_reimplement(domain_map, reference_logo)

        # domain matcher to avoid FP
        if (target_this is not None) and (tldextract.extract(url).domain+'.'+tldextract.extract(url).suffix not in domain_this):
            # avoid fp due to godaddy domain parking, ignore webmail provider (ambiguous)
            # if target_this == 'GoDaddy' or target_this == "Webmail Provider" or target_this == "Government of the United Kingdom":
            #     target_this = None  # ignore the prediction
            #     this_conf = None
            pred_target = target_this
            siamese_conf = this_conf

        return pred_target, siamese_conf

    @staticmethod
    def element_recognition_reimplement(img_arr: np.ndarray, model):
        pred = model(img_arr)
        pred_i = pred["instances"].to('cpu')
        pred_classes = pred_i.pred_classes  # Boxes types
        pred_boxes = pred_i.pred_boxes.tensor  # Boxes coords
        pred_scores = pred_i.scores  # Boxes prediction scores

        pred_classes = pred_classes.detach().cpu()
        pred_boxes = pred_boxes.detach().cpu()
        pred_scores = pred_scores.detach().cpu()

        return pred_classes, pred_boxes, pred_scores

    @staticmethod
    def credential_classifier_cv_reimplement(image: Image, coords, types, model):

        # transform to tensor
        transformation = transform.Compose([transform.Resize((256, 512)),
                                            transform.ToTensor()])
        image = transformation(image)

        # append class channels class grid tensor is of shape 8xHxW
        img_arr = np.asarray(image)
        grid_tensor = coord2pixel_reverse(img_path=img_arr, coords=coords, types=types, reshaped_size=(256, 512))

        image = torch.cat((image.double(), grid_tensor), dim=0)
        assert image.shape == (8, 256, 512)  # ensure correct shape

        # inference
        with torch.no_grad():
            pred_features = model.features(image[None, ...].to(PhishIntentionWrapper._DEVICE, dtype=torch.float))
            pred_orig = model(image[None, ...].to(PhishIntentionWrapper._DEVICE, dtype=torch.float))
            pred = F.softmax(pred_orig, dim=-1).argmax(dim=-1).item()  # 'credential': 0, 'noncredential': 1
            conf = F.softmax(pred_orig, dim=-1).detach().cpu()

        return pred, conf, pred_features

    def return_all_bboxes(self, screenshot_encoding):
        screenshot_img = Image.open(io.BytesIO(base64.b64decode(screenshot_encoding)))
        screenshot_img = screenshot_img.convert("RGB")
        screenshot_img_arr = np.asarray(screenshot_img)
        screenshot_img_arr = np.flip(screenshot_img_arr, -1)  # RGB2BGR
        pred_classes, pred_boxes, pred_scores = self.element_recognition_reimplement(img_arr=screenshot_img_arr,
                                                                                     model=self.AWL_MODEL)
        if pred_boxes is None or len(pred_boxes) == 0:
            return None, None
        return pred_boxes, pred_classes

    def return_all_bboxes4type(self, screenshot_encoding, type):
        assert type in ['label', 'button', 'input', 'logo', 'block']

        pred_boxes, pred_classes = self.return_all_bboxes(screenshot_encoding)
        if pred_boxes is None or len(pred_boxes) == 0:
            return None
        pred_boxes, pred_classes = find_element_type(pred_boxes, pred_classes, bbox_type=type)
        if len(pred_boxes) == 0:
            return None

        pred_boxes = pred_boxes.detach().cpu().numpy()
        return pred_boxes

    def return_all_logos(self, screenshot_encoding):
        screenshot_img = Image.open(io.BytesIO(base64.b64decode(screenshot_encoding)))
        screenshot_img = screenshot_img.convert("RGB")

        pred_boxes = self.return_all_bboxes4type(screenshot_encoding, 'logo')
        if pred_boxes is None or len(pred_boxes) == 0:
            return None

        cropped_logos = []
        for ct in range(len(pred_boxes)):
            x1, y1, x2, y2 = pred_boxes[ct]
            cropped_logo = screenshot_img.crop((x1,y1,x2,y2))
            cropped_logos.append(cropped_logo)
        return cropped_logos

    def has_logo(self, screenshot_path: str):

        try:
            with open(screenshot_path, "rb") as image_file:
                screenshot_encoding = base64.b64encode(image_file.read())
        except:
            return False, False

        cropped_logos = self.return_all_logos(screenshot_encoding=screenshot_encoding)
        if cropped_logos is None or len(cropped_logos) == 0:
            return False, False

        cropped = cropped_logos[0]
        img_feat = self.return_logo_feat(cropped)
        sim_list = self.LOGO_FEATS @ img_feat.T  # take dot product for every pair of embeddings (Cosine Similarity)

        if np.sum(sim_list >= self.SIAMESE_THRE_RELAX) == 0: # not exceed siamese relaxed threshold, not in targetlist
            return True, False
        else:
            return True, True


    def layout_vis(self, screenshot_path, pred_boxes, pred_classes):
        class_dict = {0: 'logo', 1: 'input', 2: 'button', 3: 'label', 4: 'block'}
        screenshot_img = Image.open(screenshot_path)
        screenshot_img = screenshot_img.convert("RGB")
        screenshot_img_arr = np.asarray(screenshot_img)
        screenshot_img_arr = np.flip(screenshot_img_arr, -1)
        screenshot_img_arr = screenshot_img_arr.astype(np.uint8)
        if pred_boxes is None or len(pred_boxes) == 0:
            return screenshot_img_arr

        pred_boxes = pred_boxes.detach().cpu().numpy()
        pred_classes = pred_classes.detach().cpu().numpy()

        # draw rectangles
        for j, box in enumerate(pred_boxes):
            if class_dict[pred_classes[j].item()] != 'block':
                cv2.rectangle(screenshot_img_arr, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (69,139,0), 2)
                cv2.putText(screenshot_img_arr, class_dict[pred_classes[j].item()], (int(box[0]), int(box[1])), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 0, 255), 2)

        return screenshot_img_arr

    def crp_classifier_reimplement(self, num_username, num_password, screenshot_encoding):
        cre_pred = 0 if (num_username or num_password) else 1

        if cre_pred == 1:  # if HTML heuristic report as nonCRP
            screenshot_img = Image.open(io.BytesIO(base64.b64decode(screenshot_encoding)))
            screenshot_img = screenshot_img.convert("RGB")
            screenshot_img_arr = np.asarray(screenshot_img)
            screenshot_img_arr = np.flip(screenshot_img_arr, -1)
            pred_classes_crp, pred_boxes_crp, _ = self.element_recognition_reimplement(img_arr=screenshot_img_arr,
                                                                                       model=self.AWL_MODEL)
            cre_pred, cred_conf, _ = self.credential_classifier_cv_reimplement(image=screenshot_img,
                                                                                coords=pred_boxes_crp,
                                                                                types = pred_classes_crp,
                                                                                model=self.CRP_CLASSIFIER)
        return cre_pred

    def crp_locator_keyword_heuristic_reimplement(self, driver: XDriver):

        ct = 0  # count number of sign-up/login links
        reach_crp = False  # reach a CRP page or not
        orig_url = driver.current_url()  # URL after loading might be different from orig_url
        current_url = orig_url
        page_text = driver.get_page_text()

        # no HTML text
        if not page_text or len(page_text) == 0:
            return reach_crp, orig_url, current_url
        page_text = page_text.split('\n')

        for line in page_text:  # iterate over html text
            if len(line.replace(' ', '')) > 300:
                continue
            # looking for keyword
            keyword_finder = re.findall(Regexes.CREDENTIAL_TAKING_KEYWORDS, " ".join(line.split()), re.IGNORECASE)
            if len(keyword_finder) > 0:
                ct += 1
                # clicking the text
                Logger.spit("Try clicking :{}".format(line), debug=True,
                            caller_prefix=PhishIntentionWrapper._caller_prefix)
                elements = driver.get_clickable_elements_contains(line)
                prev_windows = driver.window_handles
                if len(elements):
                    success_clicked = driver.click(elements[0])

                    # clicking the keywords
                    if success_clicked is not True:
                        found_kw = [y for x in keyword_finder for y in x if len(y) > 0]
                        if len(found_kw) > 0:
                            found_kw = found_kw[0]  # only click one of the keywords
                            Logger.spit("Try clicking :{}".format(found_kw), debug=True,
                                        caller_prefix=PhishIntentionWrapper._caller_prefix)
                            elements = driver.get_clickable_elements_contains(found_kw)
                            if len(elements):
                                success_clicked = driver.click(elements[0])

                    if success_clicked:
                        Logger.spit("Successfully clicked", debug=True, caller_prefix=PhishIntentionWrapper._caller_prefix)
                        time.sleep(0.5)

                        # switch to new window if any
                        current_url = driver.current_url()
                        current_window = driver.window_handles[0]  # record original window

                        if len(driver.window_handles) > len(prev_windows):  # new window popped up
                            for i in driver.window_handles:  # loop over all chrome windows
                                driver.switch_to_window(i)
                                this_url = driver.current_url()
                                if this_url == current_url:
                                    current_window = i
                                elif i not in prev_windows:
                                    new_window = i  # redirect on a new window
                                    driver.switch_to_window(new_window)

                        # save the redirected url
                        current_url = driver.current_url()
                        new_screenshot_encoding = driver.get_screenshot_encoding()
                        ret_password, ret_username = driver.get_all_visible_username_password_inputs()
                        num_username, num_password = len(ret_username), len(ret_password)
                        # Call CRP classifier
                        cre_pred = self.crp_classifier_reimplement(num_username=num_username,
                                                                   num_password=num_password,
                                                                   screenshot_encoding=new_screenshot_encoding)
                        if cre_pred == 0:  # this is an CRP
                            reach_crp = True
                            break  # stop when reach an CRP already
                        driver.switch_to_window(current_window)
                        # fixme: I break the loop anyway
                        # reach_crp = True
                        # break  # stop when reach an CRP already

                if not reach_crp:
                    # Back to the original site if CRP not found
                    try:
                        driver.get(orig_url)
                    except:
                        Logger.spit("Cannot go back to the original URL, Exit ...", warning=True,
                                    caller_prefix=PhishIntentionWrapper._caller_prefix)
                        return reach_crp, orig_url, current_url  # TIMEOUT Error

            # Only check Top 3
            if ct >= PhishIntentionWrapper._RETRIES:
                break

        return reach_crp, orig_url, current_url

    def crp_locator_cv_reimplement(self, driver: XDriver):

        reach_crp = False
        orig_url = driver.current_url()
        current_url = orig_url

        # CV-based login finder predict elements
        old_screenshot_img = Image.open(io.BytesIO(base64.b64decode(driver.get_screenshot_encoding())))
        old_screenshot_img = old_screenshot_img.convert("RGB")
        old_screenshot_img_arr = np.asarray(old_screenshot_img)
        old_screenshot_img_arr = np.flip(old_screenshot_img_arr, -1) # RGB2BGR
        _, login_buttons, _ = self.element_recognition_reimplement(img_arr=old_screenshot_img_arr,
                                                                    model=self.CRP_LOCATOR_MODEL)

        # if no prediction at all
        if login_buttons is None or len(login_buttons) == 0:
            return reach_crp, orig_url, current_url

        login_buttons = login_buttons.detach().cpu().numpy()
        for bbox in login_buttons[: min(PhishIntentionWrapper._RETRIES, len(login_buttons))]:  # only for top3 boxes
            x1, y1, x2, y2 = bbox
            element = driver.find_element_by_location((x1 + x2) // 2, (y1 + y2) // 2)  # click center point of predicted bbox for safe
            Logger.spit("Try clicking point: ({}, {})".format((x1 + x2) // 2, (y1 + y2) // 2), debug=True,
                        caller_prefix=PhishIntentionWrapper._caller_prefix)
            if element:
                prev_windows = driver.window_handles
                try:
                    success_clicked = driver.click(element)
                except selenium.common.exceptions.StaleElementReferenceException:
                    continue
                if success_clicked is True:
                    Logger.spit("Successfully clicked", debug=True, caller_prefix=PhishIntentionWrapper._caller_prefix)
                    time.sleep(0.5)

                    # switch to new window if any
                    current_url = driver.current_url()
                    current_window = driver.window_handles[0]  # record original window

                    if len(driver.window_handles) > len(prev_windows):  # new window popped up
                        for i in driver.window_handles:  # loop over all chrome windows
                            driver.switch_to_window(i)
                            this_url = driver.current_url()
                            if this_url == current_url:
                                current_window = i
                            elif i not in prev_windows:
                                new_window = i  # redirect on a new window
                                driver.switch_to_window(new_window)

                    # save the redirected url
                    current_url = driver.current_url()
                    new_screenshot_encoding = driver.get_screenshot_encoding()
                    ret_password, ret_username = driver.get_all_visible_username_password_inputs()
                    num_username, num_password = len(ret_username), len(ret_password)
                    # Call CRP classifier
                    cre_pred = self.crp_classifier_reimplement(num_username=num_username,
                                                               num_password=num_password,
                                                               screenshot_encoding=new_screenshot_encoding)
                    if cre_pred == 0:  # this is an CRP
                        reach_crp = True
                        break  # stop when reach an CRP already
                    driver.switch_to_window(current_window)

                if not reach_crp:
                    # Back to the original site if CRP not found
                    try:
                        driver.get(orig_url)
                    except:
                        Logger.spit("Cannot go back to the original URL, Exit ...", warning=True, caller_prefix=PhishIntentionWrapper._caller_prefix)
                        return reach_crp, orig_url, current_url  # TIMEOUT Error

        return reach_crp, orig_url, current_url

    def dynamic_analysis_reimplement(self, driver: XDriver):

        # get url
        successful = False  # reach CRP or not?

        # HTML heuristic based login finder
        reach_crp, orig_url, current_url = self.crp_locator_keyword_heuristic_reimplement(driver=driver)
        Logger.spit('After HTML keyword finder, reach a CRP page ? {}, \n Original URL = {}, \n Current URL = {}'.format(reach_crp, orig_url, current_url),
                    debug=True,
                    caller_prefix=PhishIntentionWrapper._caller_prefix)

        # If HTML login finder did not find CRP, call CV-based login finder
        if not reach_crp:
            reach_crp, orig_url, current_url = self.crp_locator_cv_reimplement(driver=driver)
            Logger.spit(
                'After CV login finder, reach a CRP page ? {}, \n Original URL = {}, \n Current URL = {}'.format(
                    reach_crp, orig_url, current_url),
                debug=True,
                caller_prefix=PhishIntentionWrapper._caller_prefix)


        if reach_crp:
            successful = True
        else:
            try:
                driver.get(orig_url)
            except:
                Logger.spit("Cannot go back to the original URL, Exit ...", warning=True,
                            caller_prefix=PhishIntentionWrapper._caller_prefix)
                return successful, orig_url, current_url  # load URL unsuccessful


        return successful, orig_url, current_url

    def dynamic_analysis_and_save_reimplement(self, orig_url,
                                              screenshot_path,
                                              driver: XDriver):

        new_screenshot_path = screenshot_path.replace('shot.png', 'new_shot.png')
        new_info_path = new_screenshot_path.replace('new_shot.png', 'new_info.txt')
        process_time = 0.

        # get url
        successful = False  # reach CRP or not?
        try:
            driver.get(orig_url)
            time.sleep(3)
        except:
            return orig_url, screenshot_path, successful, process_time

        # HTML heuristic based login finder
        start_time = time.time()
        reach_crp, orig_url, current_url = self.crp_locator_keyword_heuristic_reimplement(driver=driver)
        process_time += time.time() - start_time
        Logger.spit('After HTML keyword finder, reach a CRP page ? {}, \n Original URL = {}, \n Current URL = {}'.format(reach_crp, orig_url, current_url),
                    debug=True,
                    caller_prefix=PhishIntentionWrapper._caller_prefix)

        # If HTML login finder did not find CRP, call CV-based login finder
        if not reach_crp:
            reach_crp, orig_url, current_url = self.crp_locator_cv_reimplement(driver=driver)
            Logger.spit(
                'After CV login finder, reach a CRP page ? {}, \n Original URL = {}, \n Current URL = {}'.format(
                    reach_crp, orig_url, current_url),
                debug=True,
                caller_prefix=PhishIntentionWrapper._caller_prefix)


        if not reach_crp:
            try:
                driver.get(orig_url)
            except:
                Logger.spit("Cannot go back to the original URL, Exit ...", warning=True,
                            caller_prefix=PhishIntentionWrapper._caller_prefix)
            return orig_url, screenshot_path, successful, process_time  # load URL unsuccessful


        # FIXME: update the screenshots
        try:
            driver.save_screenshot(new_screenshot_path)
        except Exception as e:
            return orig_url, screenshot_path, successful, process_time  # save updated screenshot unsucessful

        with open(new_info_path, 'w', encoding='ISO-8859-1') as f:
            f.write(current_url)
        if reach_crp:
            successful = True

        return current_url, new_screenshot_path, successful, process_time

    '''This is the original PhishIntention test script, it assumes we have already crawled the screenshot and the HTML, it is not integrated with XDriver'''
    '''The CRP classification part is pure static'''
    def test_orig_phishintention(self, url, screenshot_path, driver: XDriver):

        waive_crp_classifier = False
        dynamic = False
        ele_detector_time = 0
        siamese_time = 0
        crp_time = 0
        dynamic_time = 0
        process_time = 0

        while True:
            screenshot_img = Image.open(screenshot_path)
            screenshot_img = screenshot_img.convert("RGB")

            with open(screenshot_path, "rb") as image_file:
                screenshot_encoding = base64.b64encode(image_file.read())

            # 0 for benign, 1 for phish, default is benign
            phish_category = 0
            pred_target = None
            siamese_conf = None
            print("Entering phishintention")

            ####################### Step1: layout detector ##############################################
            start_time = time.time()
            pred_boxes, pred_classes = self.return_all_bboxes(screenshot_encoding)
            if not waive_crp_classifier: # first time entering the loop
                plotvis = self.layout_vis(screenshot_path, pred_boxes, pred_classes)
                print("plot")
            ele_detector_time = time.time() - start_time

            if pred_boxes is None or len(pred_boxes) == 0:
                print('No element is detected, report as benign')
                return phish_category, pred_target, plotvis, siamese_conf, dynamic, str(ele_detector_time) + '|' + str(
                    siamese_time) + '|' + str(crp_time) + '|' + str(dynamic_time) + '|' + str(
                    process_time), pred_boxes, pred_classes

            logo_pred_boxes, logo_pred_classes = find_element_type(pred_boxes=pred_boxes, pred_classes=pred_classes, bbox_type='logo')
            if len(logo_pred_boxes) == 0:
                print('No logo is detected')
                return phish_category, pred_target, plotvis, siamese_conf, dynamic, str(ele_detector_time) + '|' + str(
                    siamese_time) + '|' + str(crp_time) + '|' + str(dynamic_time) + '|' + str(
                    process_time), pred_boxes, pred_classes

            logo_pred_boxes = logo_pred_boxes.detach().cpu().numpy()
            x1, y1, x2, y2 = logo_pred_boxes[0]
            reference_logo = screenshot_img.crop((x1, y1, x2, y2))

            print('Entering siamese')

            ######################## Step2: Siamese (logo matcher) ########################################
            start_time = time.time()
            pred_target, siamese_conf = self.phishpedia_classifier_OCR_reimplement(reference_logo=reference_logo,
                                                                                   domain_map_path=self.DOMAIN_MAP_PATH,
                                                                                   url=url)
            siamese_time = time.time() - start_time
            if pred_target is None:
                print('Did not match to any brand, report as benign')
                return phish_category, pred_target, plotvis, siamese_conf, dynamic, \
                       str(ele_detector_time) + '|' + str(siamese_time) + '|' + str(crp_time) + '|' + str(
                           dynamic_time) + '|' + str(process_time), \
                       pred_boxes, pred_classes

            # first time entering the loop
            if not waive_crp_classifier:
                pred_target_initial = pred_target
                url_orig = url
            else: # second time entering the loop
                # the page before and after transition are matched to different target
                if pred_target_initial != pred_target:
                    print('After CRP transition, the logo\'s brand has changed, report as benign')
                    return phish_category, pred_target, plotvis, siamese_conf, dynamic, \
                           str(ele_detector_time) + '|' + str(siamese_time) + '|' + str(crp_time) + '|' + str(
                               dynamic_time) + '|' + str(process_time), \
                           pred_boxes, pred_classes

            ######################## Step3: CRP checker (if a target is reported) #################################
            print('A target is reported by siamese, enter CRP classifier')
            if waive_crp_classifier:  # only run dynamic analysis ONCE
                break

            if pred_target is not None:
                html_path = screenshot_path.replace("shot.png", "html.txt")
                start_time = time.time()
                cre_pred = html_heuristic(html_path)
                if cre_pred == 1:  # if HTML heuristic report as nonCRP
                    # CRP classifier
                    cre_pred, cred_conf, _ = credential_classifier_mixed_al(img=screenshot_path, coords=pred_boxes,
                                                                            types=pred_classes, model=self.CRP_CLASSIFIER)
                crp_time = time.time() - start_time
                print('CRP prediction after static analysis (0 is CRP, 1 is non CRP) = {}'.format(cre_pred))

                ######################## Step4: Dynamic analysis #################################
                if cre_pred == 1:
                    print('Enter dynamic CRP finder')
                    waive_crp_classifier = True  # only run dynamic analysis ONCE
                    # dynamic
                    start_time = time.time()
                    try:
                        url, screenshot_path, successful, process_time = self.dynamic_analysis_and_save_reimplement(orig_url=url,
                                                                                      screenshot_path=screenshot_path,
                                                                                      driver=driver)
                    except selenium.common.exceptions.TimeoutException:
                        successful = False
                    dynamic_time = time.time() - start_time

                    # If dynamic analysis did not reach a CRP
                    if successful == False or tldextract.extract(url).domain != tldextract.extract(url_orig).domain:
                        print('Dynamic analysis cannot find any link redirected to a CRP page, report as benign')
                        return phish_category, None, plotvis, None, dynamic, str(ele_detector_time) + '|' + str(
                            siamese_time) + '|' + str(crp_time) + '|' + str(dynamic_time) + '|' + str(
                            process_time), pred_boxes, pred_classes
                    else:  # dynamic analysis successfully found a CRP
                        dynamic = True
                        print('Dynamic analysis found a CRP, go back to layout detector')

                else:  # already a CRP page
                    print('Already a CRP, continue')
                    break
        #
        ######################## Step5: Return #################################
        if pred_target is not None:
            print('Phishing is found!')
            phish_category = 1
            # Visualize, add annotations
            cv2.putText(plotvis, "Target: {} with confidence {:.4f}".format(pred_target, siamese_conf),
                        (100, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        return phish_category, pred_target, plotvis, siamese_conf, dynamic, \
               str(ele_detector_time) + '|' + str(siamese_time) + '|' + str(crp_time) + '|' + str(
                   dynamic_time) + '|' + str(process_time), \
               pred_boxes, pred_classes

    ''''PhishIntention but no dynamic part'''
    def test_orig_phishintention_wo_dynamic(self, url, screenshot_path):

        waive_crp_classifier = False
        dynamic = False
        ele_detector_time = 0
        siamese_time = 0
        crp_time = 0
        dynamic_time = 0
        process_time = 0

        screenshot_img = Image.open(screenshot_path)
        screenshot_img = screenshot_img.convert("RGB")

        with open(screenshot_path, "rb") as image_file:
            screenshot_encoding = base64.b64encode(image_file.read())

        # 0 for benign, 1 for phish, default is benign
        phish_category = 0
        pred_target = None
        siamese_conf = None
        print("Entering phishintention")

        ####################### Step1: layout detector ##############################################
        start_time = time.time()
        pred_boxes, pred_classes = self.return_all_bboxes(screenshot_encoding)
        plotvis = self.layout_vis(screenshot_path, pred_boxes, pred_classes)
        print("plot")
        ele_detector_time = time.time() - start_time

        if pred_boxes is None or len(pred_boxes) == 0:
            print('No element is detected, report as benign')
            return phish_category, pred_target, plotvis, siamese_conf, dynamic, str(ele_detector_time) + '|' + str(
                siamese_time) + '|' + str(crp_time) + '|' + str(dynamic_time) + '|' + str(
                process_time), pred_boxes, pred_classes

        logo_pred_boxes, logo_pred_classes = find_element_type(pred_boxes=pred_boxes, pred_classes=pred_classes, bbox_type='logo')
        if len(logo_pred_boxes) == 0:
            print('No logo is detected')
            return phish_category, pred_target, plotvis, siamese_conf, dynamic, str(ele_detector_time) + '|' + str(
                siamese_time) + '|' + str(crp_time) + '|' + str(dynamic_time) + '|' + str(
                process_time), pred_boxes, pred_classes

        logo_pred_boxes = logo_pred_boxes.detach().cpu().numpy()
        x1, y1, x2, y2 = logo_pred_boxes[0]
        reference_logo = screenshot_img.crop((x1, y1, x2, y2))

        print('Entering siamese')

        ######################## Step2: Siamese (logo matcher) ########################################
        start_time = time.time()
        pred_target, siamese_conf = self.phishpedia_classifier_OCR_reimplement(reference_logo=reference_logo,
                                                                               domain_map_path=self.DOMAIN_MAP_PATH,
                                                                               url=url)
        siamese_time = time.time() - start_time
        if pred_target is None:
            print('Did not match to any brand, report as benign')
            return phish_category, pred_target, plotvis, siamese_conf, dynamic, \
                   str(ele_detector_time) + '|' + str(siamese_time) + '|' + str(crp_time) + '|' + str(
                       dynamic_time) + '|' + str(process_time), \
                   pred_boxes, pred_classes

        ######################## Step3: CRP checker (if a target is reported) #################################
        print('A target is reported by siamese, enter CRP classifier')

        html_path = screenshot_path.replace("shot.png", "html.txt")
        start_time = time.time()
        cre_pred = html_heuristic(html_path)
        if cre_pred == 1:  # if HTML heuristic report as nonCRP
            # CRP classifier
            cre_pred, cred_conf, _ = credential_classifier_mixed_al(img=screenshot_path, coords=pred_boxes,
                                                                    types=pred_classes, model=self.CRP_CLASSIFIER)
        crp_time = time.time() - start_time

        if cre_pred == 0:  # already a CRP page
            print('Already a CRP, continue')
        else:
            return 0, None, plotvis, None, dynamic, str(ele_detector_time) + '|' + str(
                siamese_time) + '|' + str(crp_time) + '|' + str(dynamic_time) + '|' + str(
                process_time), pred_boxes, pred_classes
        #
        ######################## Step5: Return #################################
        print('Phishing is found!')
        phish_category = 1
        # Visualize, add annotations
        cv2.putText(plotvis, "Target: {} with confidence {:.4f}".format(pred_target, siamese_conf),
                    (100, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        return phish_category, pred_target, plotvis, siamese_conf, dynamic, \
               str(ele_detector_time) + '|' + str(siamese_time) + '|' + str(crp_time) + '|' + str(
                   dynamic_time) + '|' + str(process_time), \
               pred_boxes, pred_classes

    '''This is the original Phishpedia test script'''
    def test_orig_phishpedia(self, url, screenshot_path):

        ele_detector_time = 0
        siamese_time = 0

        screenshot_img = Image.open(screenshot_path)
        screenshot_img = screenshot_img.convert("RGB")

        with open(screenshot_path, "rb") as image_file:
            screenshot_encoding = base64.b64encode(image_file.read())

        # 0 for benign, 1 for phish, default is benign
        phish_category = 0
        pred_target = None
        siamese_conf = None
        print("Entering phishpedia")

        ####################### Step1: layout detector ##############################################
        start_time = time.time()
        pred_boxes, pred_classes = self.return_all_bboxes(screenshot_encoding)
        plotvis = self.layout_vis(screenshot_path, pred_boxes, pred_classes)
        print("plot")
        ele_detector_time = time.time() - start_time

        if pred_boxes is None or len(pred_boxes) == 0:
            print('No element is detected, report as benign')
            return phish_category, pred_target, plotvis, siamese_conf, \
                   str(ele_detector_time) + '|' + str(siamese_time), \
                   pred_boxes, pred_classes

        logo_pred_boxes, logo_pred_classes = find_element_type(pred_boxes=pred_boxes, pred_classes=pred_classes, bbox_type='logo')
        if len(logo_pred_boxes) == 0:
            print('No logo is detected, report as benign')
            return phish_category, pred_target, plotvis, siamese_conf, \
                   str(ele_detector_time) + '|' + str(siamese_time), \
                   pred_boxes, pred_classes

        logo_pred_boxes = logo_pred_boxes.detach().cpu().numpy()
        x1, y1, x2, y2 = logo_pred_boxes[0]
        reference_logo = screenshot_img.crop((x1, y1, x2, y2))

        print('Entering siamese')

        ######################## Step2: Siamese (logo matcher) ########################################
        start_time = time.time()
        pred_target, siamese_conf = self.phishpedia_classifier_OCR_reimplement(reference_logo=reference_logo,
                                                                              domain_map_path=self.DOMAIN_MAP_PATH,
                                                                              url=url)
        siamese_time = time.time() - start_time

        if pred_target is None:
            print('Did not match to any brand, report as benign')
            return phish_category, pred_target, plotvis, siamese_conf, \
                   str(ele_detector_time) + '|' + str(siamese_time), \
                   pred_boxes, pred_classes

        ######################## Step5: Return #################################
        if pred_target is not None:
            print('Phishing is found!')
            phish_category = 1
            # Visualize, add annotations
            cv2.putText(plotvis, "Target: {} with confidence {:.4f}".format(pred_target, siamese_conf),
                        (100, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        return phish_category, pred_target, plotvis, siamese_conf, \
               str(ele_detector_time) + '|' + str(siamese_time), \
               pred_boxes, pred_classes