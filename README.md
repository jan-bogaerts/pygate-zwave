# Description
This is a plugin for [pygate](https://github.com/allthingstalk/pygate): add support for the z-wave protocol to the gateway.

Notes: 

- this plugin depends on the [python open-zwave](https://github.com/OpenZWave/python-openzwave) implementation.
- the plugin requires an USB zwave controller stick to function. The open-zwave project maintains a [list of supported controllers](https://github.com/OpenZWave/open-zwave/wiki/Controller-Compatibility-List). The plugin also works with the default [sigma USB controller sticks](http://www.digikey.be/product-search/en/rf-if-and-rfid/rf-evaluation-and-development-kits-boards/3539644?k=&pkeyword=&pv183=5604&FV=fff40036%2Cfff802bc&mnonly=0&newproducts=0&ColumnSort=0&page=1&quantity=0&ptm=0&fid=0&pageSize=25). 

#installation


- Make certain that [pygate](https://github.com/allthingstalk/pygate) and all of it's dependencies have been installed first.
- install the python open-zwave library (for the RPI):
	- go to the home directory of the RPI
	- run: `sudo apt-get install -y git make`
	- run `git clone https://github.com/OpenZWave/python-openzwave`
	- run `cd python-openzwave`
	- run `sudo apt-get update`
	- run `sudo make repo-deps`
	- run `make update`
	- run `sudo make build`
	- run `sudo make install`
	- go back to the home directory  
- download the module
- install the module, 2 options are available:
	- run `python setup.py install` from within the plugin directory  
	- or copy the directory pygate_virtualdevices to the root directory of the pygate software (at the same level as pygate.py)  
and run `pip install -r requirements.txt` from within the pygate_virtualdevices directory.

#configure the plugin
This plugin needs some configuration parameters that have to be added to the file 'pygate.conf'. The following section has to be added:

    [zwave]
    port = /dev/ttyACM0
    loglevel = None
    config = /home/pi/python-openzwave/openzwave/config
    device_classes.xml path = /home/pi/python-openzwave/openzwave/config/device_classes.xml

- port: the USB port that contains the zwave stick
- loglevel: the leval at which the zwave library renders logging info
- config: the path to the config folder in the openzwave library
- device_classes.xml path: the path to the 'device_classes.xml' file in the openzwave folder.

The current settings should be correct for installation on a raspberry pi device.  
Depending on the system you have installed it on, the path used in the last 2 configs has to be updated.   
If there are multiple usb devices connected, you might also have to update the port.  

#activate the plugin
the plugin must be activated in the pygate software before it can be used. This can be done manually or through the pygate interface.

## manually
Edit the configuration file 'pygate.conf' (located in the config dir).
add 'zwave' to the config line 'modules' in the general section of the 'pygate.conf' config file. ex:  
    
	[general]  
    modules = main; zwave
When done, restart the gateway.

##pygate interface
Use the actuator 'plugins' and add 'zwave' to the list. After the command has been sent to the device, the gateway will reboot automatically.
