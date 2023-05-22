**General**
-
In this repository, we build a system to automatically decide the maliciousness of a phishing webpage through its behaviours. 
This repository is built upon https://gitlab.com/kostasdrk/xdriver3-open.

This repository includes partial code for our paper "Knowledge Expansion and Counterfactual Interaction for Reference-Based Phishing Detection".
Published in USENIX Security 2023. The main repository is here: https://github.com/code-philia/Dynaphish 

**System Overview**
-
We build an interaction webdriver (Selenium-based) to automatically perform form filling, form submission, and webpage transition detection.
Our main goal is to report suspicious behaviours in web login process, such as (1) no verification on fake account details and (2) evasive redirection to third-party website upon form submission. 
-
<img src='WebInteraction Diagram-2.png' style="width:3000px;height:650px"/>


**Setup**
-
Implemented and tested on Ubuntu 16.04 and 20.04 with python3.7. Should work on other debian-based systems as well.
1. 
Create an environment with python==3.7
Install torch, torchvision compatible with your CUDA, see here: https://pytorch.org/get-started/previous-versions/

2. Install compatible Detectron2, see https://detectron2.readthedocs.io/en/latest/tutorials/install.html 

3. Install PhishIntention by
```
 pip install git+https://github.com/lindsey98/PhishIntention.git
```

4. Clone this MyXDriver_pub repo and `cd` into it
 ```
git clone https://github.com/lindsey98/MyXdriver_pub.git
cd MyXdriver_pub
```

5. run `$ ./setup.sh`
* Make sure the webdrivers' versions are compatible with the corresponding browsers' version

6. Install mmocr: See https://github.com/open-mmlab/mmocr, https://mmocr.readthedocs.io/en/dev-1.x/get_started/install.html 
