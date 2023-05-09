
from ..PhishIntentionWrapper import PhishIntentionWrapper
from PIL import Image
import io
import base64
import numpy as np
from phishintention.src.AWL_detector import element_config


class SubmissionButtonLocator(PhishIntentionWrapper):

    def __init__(self, button_locator_weights_path, button_locator_config):
        _, self.BUTTON_SUBMISSION_MODEL = element_config(rcnn_weights_path=button_locator_weights_path, rcnn_cfg_path=button_locator_config)

    def return_submit_button(self, screenshot_encoding):
        screenshot_img = Image.open(io.BytesIO(base64.b64decode(screenshot_encoding)))
        screenshot_img = screenshot_img.convert("RGB")
        screenshot_img_arr = np.asarray(screenshot_img)
        screenshot_img_arr = np.flip(screenshot_img_arr, -1)  # RGB2BGR

        pred_classes, pred_boxes, pred_scores = self.element_recognition_reimplement(img_arr=screenshot_img_arr,
                                                                                     model=self.BUTTON_SUBMISSION_MODEL)
        if pred_boxes is None or len(pred_boxes) == 0:
            return None
        pred_boxes = pred_boxes.detach().cpu().numpy()
        return pred_boxes
