#!/bin/bash

install_dir="/tmp/"

function success {
	echo "[+] $1"
}

function fail {
	echo "[-] $1"
}

function warn {
	echo "[!] $1"
}

function prompt {
	ret=""
	while true; do
    	read -p "$1 [y/n]: " yn
	    case $yn in
	        [Yy]* ) ret=1; break;;
	        [Nn]* ) ret=0; break;;
	        * ) echo "Please answer yes or no.";;
    	esac
	done
	return $ret
}

function install_chrome {
	debfile="google-chrome-stable_current_amd64.deb"
	wget "https://dl.google.com/linux/direct/$debfile" -P "$install_dir"
	if [ $? -ne 0 ];
	then
		fail "Could not download Chrome"
		return 1
	fi
	sudo dpkg -i "$install_dir$debfile"
	if [ $? -ne 0 ];
	then
		fail "Could not install Chrome package"
		return 2
	fi
	success "Successfully installed Chrome"
	return 0
}

function install_firefox {
	sudo apt-get install -y firefox
	if [ $? -ne 0 ];
	then
		fail "Could not install Firefox"
		return 1
	fi
	success "Successfully installed Firefox"
	return 0
}

function install_opera {
	wget -qO- https://deb.opera.com/archive.key | sudo apt-key add -
	if [ $? -ne 0 ];
	then
		fail "Could not add Opera keyring"
		return 1
	fi

	sudo add-apt-repository "deb [arch=i386,amd64] https://deb.opera.com/opera-stable/ stable non-free"
	if [ $? -ne 0 ];
	then
		fail "Could not add Opera apt repository"
		return 2
	fi

	sudo apt-get update # update to locate package
	sudo apt install -y opera-stable
	if [ $? -ne 0 ];
	then
		fail "Could not install Opera"
		return 3
	fi
	success "Successfully installed Opera"
	return 0
}

declare -A browsers
browsers=(["google-chrome-stable"]=install_chrome ["firefox"]=install_firefox ["opera"]=install_opera)

declare -A drivers
drivers=(["google-chrome-stable"]="chromedriver" ["firefox"]="geckodriver" ["opera"]="operadriver")

declare -A drivers_urls
drivers_urls=(["google-chrome-stable"]="https://sites.google.com/a/chromium.org/chromedriver/downloads" ["firefox"]="https://github.com/mozilla/geckodriver/releases" ["opera"]="https://github.com/operasoftware/operachromiumdriver/releases")

drivers_dir="./browsers/config/webdrivers/"

function check_browsers {
	for browser in ${!browsers[@]};
	do
		installed=false
		dpkg -l "$browser" > /dev/null 2>&1
		if [ $? -eq 0 ];
		then
			success "$browser is installed. (version: $($browser --version))"
			installed=true
		else
			warn "$browser does not seem to be installed"
			prompt "Do you want to install its latest stable version?"
			if [ $? -eq 1 ];
			then
				success "Installing $browser"
				${browsers[$browser]}
				if [ $? -eq 0 ];
				then
					installed=true
				fi
			else
				fail "Skipping $browser installation"
			fi
		fi
		if [ $installed ];
		then
			driver=${drivers[$browser]}
			if [ ! -f "$drivers_dir$driver" ];
			then
				fail "$driver not found under $drivers_dir"
				warn "You can download it from: ${drivers_urls[$browser]}"
				warn "Make sure your $browser installation is compatible with the $driver version"
			else
				success "$driver OK"
			fi
		fi
		echo -e ""
	done
	return 0
}

function download_mitm {
	mitm_dir="./xutils/proxy/mitm/"
	wget -c https://snapshots.mitmproxy.org/2.0.2/mitmproxy-2.0.2-linux.tar.gz -P "$mitm_dir"
	if [ $? -ne 0 ];
	then
		fail "Could not download mitmproxy"
		return 1
	fi

	tar xf "$mitm_dir""mitmproxy-2.0.2-linux.tar.gz" -C "$mitm_dir"
	if [ $? -ne 0 ];
	then
		fail "Could not untar mitmproxy"
		return 2
	fi

	rm "$mitm_dir""mitmproxy-2.0.2-linux.tar.gz"
	rm "$mitm_dir""mitmproxy" # We only need mitmdump
	rm "$mitm_dir""mitmweb"

	success "Downloaded mitmproxy"
	return 0
}

function check_mitm {
	mitm_dir="./xutils/proxy/mitm/"
	if [ ! -f "$mitm_dir/mitmdump" ];
	then
		fail "mitmdump not found under $mitm_dir"
		prompt "Do you want to download it?"
		if [ $? -eq 1 ];
		then
			success "Downloading mitmproxy"
			download_mitm
		else
			fail "Skipping mitmdump download. This is necessary."
			return 1
		fi
	else
		success "mitmdump OK"
	fi
	return 0
}

function check_xvfb {
	dpkg -l xvfb  > /dev/null 2>&1
	if [ $? -eq 0 ];
	then
		success "xvfb OK"
		return 0
	else
		warn "xvfb does not seem to be installed"
		warn "It is required if you want to have virtual display support for your browsers."
		prompt "Do you want to install it?"
		if [ $? -eq 1 ];
		then
			success "Downloading xvfb"
			sudo apt-get install -y xvfb
		else
			fail "Skipping xvfb download."
			return 1
		fi
	fi
}

check_browsers
check_mitm
check_xvfb
pip3 install --upgrade .
