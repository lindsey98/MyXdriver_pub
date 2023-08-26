**MyXdriver**
-
In this repository, we build a system to automatically decide the maliciousness of a phishing webpage through its behaviors. 
This repository includes partial code for our paper "Knowledge Expansion and Counterfactual Interaction for Reference-Based Phishing Detection".
Published in USENIX Security 2023. The main repository is here: https://github.com/code-philia/Dynaphish 
Supported functionalities:
- ✅ Locate all inputs, submission buttons, etc.
- ✅ Decide the semantics of inputs and fill in faked credentials
- ✅ Submit forms
- ✅ Track webpage state changes
- ✅ Detect the presence of reCaptcha
- ✅ Detect the presence of error messages
- ✅ HTML obfuscation
- ✅ Observe the suspicious behaviors during login action
   - 🏁 Let users proceed without verification on fake credentials
   - 🏁 Redirect to third-party webpage after form submission

**System Overview**
-
We build an interaction webdriver (Selenium-based) to automatically perform form filling, form submission, and webpage transition detection.
Our main goal is to report suspicious behaviors during the login process, such as (1) no verification of fake account details and (2) evasive redirection to third-party websites upon form submission. 
<img src='WebInteraction Diagram.png'/>


**Setup**
-
Implemented and tested on Ubuntu 16.04 and 20.04 with Python 3.8. Should work on other Debian-based systems as well.
1.  
Clone this MyXDriver_pub repo and `cd` into it
 ```
git clone https://github.com/lindsey98/MyXdriver_pub.git
cd MyXdriver_pub
```
2. Manually download chromedriver executable (https://chromedriver.chromium.org/), and put it under config/webdrivers.
* Make sure the webdriver's version is compatible with the corresponding browsers' version

3. run `./setup.sh`

**Usage**
-
- Automatic form filling: See test script [testing/formfill.py](https://github.com/lindsey98/MyXdriver_pub/blob/master/testing/formfill.py)
   - Locate all inputs: [xutils.forms.Form.Form._get_input_elements](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/forms/Form.py#L139)
   - Locate the submission button [xutils.forms.Form.Form._get_button_elements](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/forms/Form.py#L260)
   - Decide the semantics of inputs: [xutils.forms.FormElement.FormElement._decide_rule_inputs](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/forms/FormElement.py#L284)
   - Fill in all inputs: [xutils.forms.Form.Form.fill_all_inputs](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/forms/Form.py#L396)
   - Form submission: [xutils.forms.Form.Form.submit](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/forms/Form.py#L418)
     
- Track webpage state
   - Check whether the webpage is empty: [xutils.state.StateClass StateClass.empty_page](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/state/StateClass.py#L248)
   - Check whether the webpage is a credential-requiring page or not: [xutils.state.StateClass.StateClass.is_CRP](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/state/StateClass.py#L70)
   - Check whether the webpage has been redirected to a different domain: [xutils.state.StateClass.StateClass.does_redirection](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/state/StateClass.py#L86)
   - Detect the presence of reCaptcha: [xutils.state.StateClass.StateClass.recaptcha_displayed](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/state/StateClass.py#L135)
   - Detect the presence of error messages: [xutils.state.StateClass.StateClass.has_error_message_displayed](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/state/StateClass.py#L151)
     
- Phishing detection based on suspicious behaviors during login: See [testing/webinteraction.py](https://github.com/lindsey98/MyXdriver_pub/blob/master/testing/webinteraction.py)
   - Redirection to third-party websites: [xutils.WebInteraction.WebInteraction.get_benign](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/WebInteraction.py#L268-L294)
   - No verification on fake credentials: [xutils.WebInteraction.WebInteraction.get_benign](https://github.com/lindsey98/MyXdriver_pub/blob/master/xutils/WebInteraction.py#L336-L359)
 
- Miscellaneous: For other utilities, please refer to [XDriver.py](https://github.com/lindsey98/MyXdriver_pub/blob/master/XDriver.py)
   - Get DOM path for an element: [XDriver.XDriver.get_dompath](https://github.com/lindsey98/MyXdriver_pub/blob/master/XDriver.py#L1276)
   - Get the coordinate for an element: [XDriver.XDriver.get_location](https://github.com/lindsey98/MyXdriver_pub/blob/master/XDriver.py#L1318)
   - Retrieve the elements given a list of coordinates: [XDriver.XDriver.get_all_elements_from_coordinate_list](https://github.com/lindsey98/MyXdriver_pub/blob/master/XDriver.py#L1551)
   - Get all potential clickable elements: [XDriver.XDriver.get_all_clickable_elements](https://github.com/lindsey98/MyXdriver_pub/blob/master/XDriver.py#L1730)
   - Obfuscate buttons as images: [XDriver.XDriver.obfuscate_page](https://github.com/lindsey98/MyXdriver_pub/blob/master/XDriver.py#L1852)

**Reference**
-
If you find our tool helpful, please consider citing our paper
```bibtex
 @inproceedings {291106,
 author = {Ruofan Liu and Yun Lin and Yifan Zhang and Penn Han Lee and Jin Song Dong},
 title = {Knowledge Expansion and Counterfactual Interaction for {Reference-Based} Phishing Detection},
 booktitle = {32nd USENIX Security Symposium (USENIX Security 23)},
 year = {2023},
 isbn = {978-1-939133-37-3},
 address = {Anaheim, CA},
 pages = {4139--4156},
 url = {https://www.usenix.org/conference/usenixsecurity23/presentation/liu-ruofan},
 publisher = {USENIX Association},
 month = aug,
 }
```

