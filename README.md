**General**
-
In this repository, we build a system to automatically decide the maliciousness of a phishing webpage through its behaviours 

**System Overview**
-
<img src='WebInteraction Diagram-2.png' style="width:3000px;height:650px"/>


**Setup**
-
Implemented and tested on Ubuntu 16.04 and 20.04 with python3.7. Should work on other debian-based systems as well.
1. Installing Git LFS (https://git-lfs.github.com/)
2. 
Create an environment with python==3.7
Install torch, torchvision compatible with your CUDA, see here: https://pytorch.org/get-started/previous-versions/
3. Install compatible Detectron2
```
python -m pip install 'git+https://github.com/lindsey98/detectron2.git'
# (add --user if you don't have permission)

# Or, to install it from a local clone:
git clone https://github.com/lindsey98/detectron2.git
python -m pip install -e detectron2
```
4. Install PhishIntention by
```
 pip install git+https://github.com/lindsey98/PhishIntention.git
```
5. Clone this MyXDriver repo and `cd` into it
 ```
git clone https://github.com/lindsey98/MyXdriver.git
cd MyXdriver
```
6. run `$ ./setup.sh`
* Make sure the webdrivers' versions are compatible with the corresponding browsers' version
<!-- * When prompted, download the webdriver binaries you need and place them under `./browsers/config/webdrivers`. If you want to do this at a later time, place them at that location in the install directory (e.g. `/usr/local/lib/python3.7/dist-packages/xdriver`)
Run `./xutils/proxy/mitm/mitmdump` to create the `~/.mitmproxy` dir and add the generated mitmproxy certificate in the browsers' trust stores -->
7. Install mmocr: See https://github.com/open-mmlab/mmocr, https://mmocr.readthedocs.io/en/dev-1.x/get_started/install.html 
