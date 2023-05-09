import random

class StateAction():
    _caller_prefix = 'StateAction'

    def __init__(self, driver_cls, phishintention_cls):
        self._driver = driver_cls
        self.PhishIntention = phishintention_cls

    def CRP_transition(self):
        successful, orig_url, current_url = self.PhishIntention.dynamic_analysis_reimplement(self._driver)
        return successful, orig_url, current_url

    def interact_CAPTCHA(self):
        pass

    def click_random_internal_link(self):
        ret = self._driver.get_internal_links()
        if len(ret):
            choice = random.choice(range(len(ret)))
            link = ret[choice][0]
            success = self._driver.click(link)
            return success
        return None

    def click_random_link(self):
        ret = self._driver.get_all_links()
        if len(ret):
            choice = random.choice(range(len(ret)))
            link = ret[choice][0]
            success = self._driver.click(link)
            return success
        return None
