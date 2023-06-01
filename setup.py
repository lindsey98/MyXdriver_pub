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
  package_data = {'' : ["*.js", "*.json", "*.sh", "chromedriver", "geckodriver",
						"operadriver", "mitmdump", "*.txt"]},
  version = '0.1', # version number
  description = '',   # Package descriptin
  author = 'Ruofan Liu, Kostas Drakonakis',
  author_email = 'liu.ruofan16@u.nus.edu',
  url = 'https://github.com/lindsey98/MyXdriver_pub', # Github URL, e.g. https://github.com/user/reponame
  download_url = 'https://github.com/lindsey98/MyXdriver_pub',
)
