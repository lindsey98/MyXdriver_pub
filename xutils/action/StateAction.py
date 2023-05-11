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

