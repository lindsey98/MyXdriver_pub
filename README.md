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
- ✅ Observe the suspicious behaviors during login action
   - 🏁 Let users proceed without verification on fake credentials
   - 🏁 Redirect to third-party webpage after form submission

**System Overview**
-
We build an interaction webdriver (Selenium-based) to automatically perform form filling, form submission, and webpage transition detection.
Our main goal is to report suspicious behaviors during the login process, such as (1) no verification of fake account details and (2) evasive redirection to third-party websites upon form submission. 
<img src='WebInteraction Diagram-2.png' style="width:3000px;height:650px"/>


**Setup**
-
Implemented and tested on Ubuntu 16.04 and 20.04 with python 3.8. Should work on other Debian-based systems as well.
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
- Automatic form filling: See testing/formfill.py
- Phishing detection based on suspicious behaviors during login: See testing/webinteraction.py

**Reference**
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

