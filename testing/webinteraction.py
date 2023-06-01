import time
from xdriver.xutils.PhishIntentionWrapper import PhishIntentionWrapper
from xdriver.xutils.WebInteraction import WebInteraction
from xdriver.xutils.Logger import Logger
from mmocr.apis import MMOCRInferencer
from xdriver.xutils.forms.SubmissionButtonLocator import SubmissionButtonLocator
from xdriver.XDriver import XDriver

if __name__ == "__main__":
    sleep_time = 5; timeout_time = 30
    phishintention_cls = PhishIntentionWrapper()
    mmocr_model = MMOCRInferencer(det=None,
                        rec='ABINet',
                        device='cuda')
    button_locator_model = SubmissionButtonLocator(
        button_locator_config='/home/ruofan/git_space/phishing-research/web_interaction/xdriver3-open/xutils/forms/button_locator_models/config.yaml',
        button_locator_weights_path='/home/ruofan/git_space/phishing-research/web_interaction/xdriver3-open/xutils/forms/button_locator_models/model_final.pth')

    InteractionModel = WebInteraction(phishintention_cls=phishintention_cls,
                                      mmocr_model=mmocr_model,
                                      button_locator_model=button_locator_model,
                                      interaction_depth=1)
    Logger.set_debug_on()
    XDriver.set_headless()
    driver = XDriver.boot(chrome=True)
    driver.set_script_timeout(timeout_time)
    driver.set_page_load_timeout(timeout_time)
    time.sleep(sleep_time)  # fixme: you have to sleep sometime, otherwise the browser will keep crashing

    target = 'www.facebook.com'

    driver.get(target, accept_cookie=True, click_popup=True)
    benign, algo_time, total_time, \
    redirection_evasion, no_verification = InteractionModel.get_benign(orig_url=driver.current_url(),
                                                                       driver=driver)
    print('Is it benign?', benign)
    print('Time spent: ', total_time)
    if not benign:
        print('Does it satisfy redirection evasion invariant ? {}'
              'Does it satisfy no verification invariant? {}'.format(redirection_evasion, no_verification))

    driver.quit()
