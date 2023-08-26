from xdriver.XDriver import XDriver
from xdriver.xutils.Logger import Logger
from xdriver.xutils.forms.Form import Form
from mmocr.apis import MMOCRInferencer
from xdriver.xutils.forms.SubmissionButtonLocator import SubmissionButtonLocator
from xdriver.xutils.PhishIntentionWrapper import PhishIntentionWrapper
import time

if __name__ == '__main__':
    orig_url = "https://passport.alibaba.com/icbu_login.htm"
    sleep_time = 3; timeout_time = 60
    XDriver.set_headless()
    driver = XDriver.boot(chrome=True)
    driver.set_script_timeout(timeout_time / 2)
    driver.set_page_load_timeout(timeout_time)
    time.sleep(sleep_time)
    Logger.set_debug_on()

    # load phishintention, mmocr, button_locator_model
    phishintention_cls = PhishIntentionWrapper()
    mmocr_model = MMOCRInferencer(det=None,
                        rec='ABINet',
                        device='cuda')
    button_locator_model = SubmissionButtonLocator(
        button_locator_config='/home/ruofan/git_space/MyXdriver_pub/xutils/forms/button_locator_models/config.yaml',
        button_locator_weights_path='/home/ruofan/git_space/MyXdriver_pub/xutils/forms/button_locator_models/model_final.pth')

    # initialization
    Logger.spit('URL={}'.format(orig_url), caller_prefix=XDriver._caller_prefix, debug=True)
    try:
        driver.get(orig_url, allow_redirections=True)
        time.sleep(sleep_time)  # fixme: wait until page is fully loaded
    except Exception as e:
        Logger.spit('Exception when getting the URL {}'.format(e), caller_prefix=XDriver._caller_prefix,
                    warning=True)
        raise

    form = Form(driver, phishintention_cls, mmocr_model,
                button_locator_model, obfuscate=False)  # initialize form

    # form filling and form submission
    filled_values = form.fill_all_inputs()

    # scrolling only happens at the first time, otherwise the screenshot changes just because we scroll it, e.g.: deepl.com
    # button maybe at the bottom, need to decide when to scroll
    if len(form._button_visibilities)>0 and (not form._button_visibilities[0]):
        Logger.spit("Scroll to the bottom since the buttons are invisible", debug=True,
                    caller_prefix=XDriver._caller_prefix)
        driver.scroll_to_bottom()
        # scrolling change the screenshot
        form.button_reinitialize()

    form.submit(1)  # form submission
    driver.quit()
