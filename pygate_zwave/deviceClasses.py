__author__ = 'Jan Bogaerts'
__copyright__ = "Copyright 2015, AllThingsTalk"
__credits__ = []
__maintainer__ = "Jan Bogaerts"
__email__ = "jb@allthingstalk.com"
__status__ = "Prototype"  # "Development", or "Production"

#provies support for the xml file tat contains extra features


import logging
import os.path
import xml.etree.ElementTree

from core import config

_devClasses = {}
logger = logging.getLogger('zwave')

def _loadFile():
    """loads the xml file in memory.
    The file is part of the openzwave distribution"""
    if not config.configs.has_option('zwave', 'device_classes.xml path'):
        logger.error('zwave path to configuration files missing: config')
        return

    file = config.configs.get('zwave', 'device_classes.xml path')
    if os.path.isfile(file):
        global _devClasses
        data = xml.etree.ElementTree.parse(file).getroot()
        for generic in data.iter('{http://code.google.com/p/open-zwave/}Generic'):      # load the data in an easy to access dictionary
            specific = {}
            if 'command_classes' in generic.attrib:
                specific['cc'] = [int(x, 16) for x in generic.attrib['command_classes'].split(',')]
            else:
                specific['cc'] = []
            children = {}
            specific['specific'] = children
            for child in generic:
                if 'command_classes' in child.attrib:
                    children[int(child.attrib['key'], 16)] = [int(x, 16) for x in child.attrib['command_classes'].split(',')]
            _devClasses[int(generic.attrib['key'], 16)] = specific
    else:
        logger.error('invalid path to device_classes.xml: ' + file + ". Please check the config parameter [zwave] 'device_classes.xml path'")

def getPrimaryCCFor(generic, specific):
    '''get the primary command class(es) for a device with the specified generic and specific device class values'''
    try:
        if not _devClasses:
            _loadFile()
        if _devClasses:
            if generic in _devClasses:
                generic = _devClasses[generic]
                if specific in generic['specific']:
                    specific = generic['specific'][specific]
                    return specific
                return generic['cc']
    except:
        logger.exception("failed to convert device_classes.xml, can't detect primary and secondary assets")
    return None

