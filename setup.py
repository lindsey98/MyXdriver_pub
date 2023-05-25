from setuptools import setup, find_packages

setup(
  name = 'xdriver', # package name folder
  packages = ['xdriver',
			  'xdriver.browsers', 'xdriver.browsers.config',
			  'xdriver.browsers.config.webdrivers', 'xdriver.browsers.config.extensions',
			  'xdriver.js',
			  'xdriver.security',
			  'xdriver.xutils', 'xdriver.xutils.forms', 'xdriver.xutils.state', 'xdriver.xutils.action',
			  'xdriver.xutils.proxy', 'xdriver.xutils.proxy.mitm',
			  'xdriver.testing'],   # package name
  package_dir = {
	'xdriver' : '.',
  },
  package_data = {'' : ["*.js", "*.json", "*.sh", "chromedriver", "geckodriver", "operadriver", "mitmdump", "*.txt"]},
  version = '0.1', # version number
  license= None, # License e.g. 'MIT', "GPL2.0"
  description = '',   # Package descriptin
  author = 'Ruofan Liu, Kostas Drakonakis',
  author_email = 'liu.ruofan16@u.nus.edu',
  url = 'https://github.com/lindsey98/MyXdriver_pub', # Github URL, e.g. https://github.com/user/reponame
  download_url = 'https://github.com/lindsey98/MyXdriver_pub',
  keywords = ['selenium', 'browser', 'automation', 'security'],
  install_requires = [ # Dependencies
		  "tldextract",
		  "Faker",
		  "PyVirtualDisplay",
		  "psutil",
		  "requests",
		  "googletrans",
		  "selenium",
		  "mime",
		  "beautifulsoup4==4.9.3",
	  	  "pyautogui",
	  	  "charset-normalizer",
	  	  "Pillow",
	  	  "lxml"
	  ],
  dependency_links = [ # Dependencies not in PyPI
  ],
  classifiers = [
	'Development Status :: 4 - Beta',  # Pick from "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as current state of the package
	'Intended Audience :: Security Researchers, Security Engineers', # Targeted audience
	'Topic :: Software Development :: ?',
	'License :: OSI Approved :: ?',   # Same as before
	'Programming Language :: Python :: 3.8' # Supported python versions
  ],
)
