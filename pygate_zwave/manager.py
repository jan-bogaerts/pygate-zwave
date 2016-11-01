__author__ = 'Jan Bogaerts'
__copyright__ = "Copyright 2015, AllThingsTalk"
__credits__ = []
__maintainer__ = "Jan Bogaerts"
__email__ = "jb@allthingstalk.com"
__status__ = "Prototype"  # "Development", or "Production"

import logging

import deviceClasses
from pygate_core.gateway import Gateway

logger = logging.getLogger('zwave')

gateway = None                             # provides access to the cloud
network = None                             # provides access to the zwave network

_CC_Battery = 0x80
_CC_Wakeup = 0x84
_CC_MultiLevelSwitch = 0x26
controllerStateId = 'controllerState'
discoveryStateId = 'discoverState'   #id of asset
networkStateId = 'networkState'
deviceStateId = 'deviceState'
refreshDeviceId = 'refreshDevice'
_discoveryMode = "Off"                      # the current discovery mode that the system is in, so we can determine when to add/refresh devices.

def init(moduleName):
    """initialize all objext"""
    global gateway
    gateway = Gateway(moduleName)

def start():
    network.start()
    logger.info(gateway._moduleName + ' running')

def syncDevices(existing, Full):
    for key, node in network.nodes.iteritems():
        if str(node.node_id) != '1':                    # for some reason, this compare doesn't work without convertion.
            found = next((x for x in existing if x['id'].encode('ascii','ignore') == str(node.node_id)), None)
            if not found:
                addDevice(node, 'create')
            else:
                existing.remove(found)              # so we know at the end which ones have to be removed.
                if Full:                            # don't refresh upon startup, this only slows it down, no need.
                    addDevice(node, 'update')        # this will also refresh it
    for dev in existing:                        # all the items that remain in the 'existing' list, are no longer devices in this network, so remove them
        gateway.deleteDevice(dev['id'])


def addDevice(node, mode = None):
    """adds the specified node to the cloud as a device. Also adds all the assets.
    :param node: the device details
    :param createDevice: when true, addDevice will be called. when false, only the assets will be updated/created
    This is for prevention of overwriting the name.
    """
    try:
        if node.product_name:                       #newly included devices arent queried fully yet, so create with dummy info, update later
            name = node.product_name
        else:
            name = 'unknown'
        if mode == "create":                              # for an update, we don't need to do anyhthing for the device, only the assets
            gateway.addDevice(node.node_id, name, node.type)
        elif mode == 'update':
            gateway.addDevice(node.node_id, None, node.type)            # when updating, don't overwrite the title of the device.
        items = dict(node.values)                                         # take a copy of the list cause if the network is still refreshing/loading, the list could get updated while in the loop
        gateway.addAsset('location', node.node_id, 'location', 'the physical location of the device', True, 'string', 'Config')
        for key, val in items.iteritems():
            try:
                if val.command_class:                # if not related to a command class, then all other fields are 'none' as well, can't t much with them.
                    # and not str(val.genre).lower() == 'system':    # old: System values are not interesting, it's about frames and such (possibly for future debugging...)
                    addAsset(node, val)
                    buildValueId(val)
            except:
                logger.exception('failed to sync device ' + str(node.node_id) + ' for module ' + gateway._moduleName + ', asset: ' + str(key) + '.')
        #if _CC_Battery in node.command_classes:
        #    gateway.addAsset('failed', node.node_id, 'failed', 'true when the battery device is no longer responding and the controller has labeled it as a failed device.', False, 'boolean', 'Secondary')
        gateway.addAsset('failed', node.node_id, 'failed', 'true when the device is no longer responding and the controller has labeled it as a failed device.', False, 'boolean', 'Secondary')
        # todo: potential issue: upon startup, there might not yet be an mqtt connection, send may fail
        gateway.send(node.is_failed, node.node_id, 'failed')
        gateway.addAsset(refreshDeviceId, node.node_id, 'refresh', 'Refresh all the assets and their values', True, 'boolean', 'Undefined')
        gateway.addAsset('manufacturer_name', node.node_id, 'manufacturer name', 'The name of the manufacturer', False, 'string', 'Undefined')
        gateway.addAsset('product_name', node.node_id, 'product name', 'The name of the product', False, 'string', 'Undefined')
        gateway.addAsset('query_state', node.node_id, 'query state', 'details on the progress of the currently running discovery process for this device.', False, '{"type": "object"}', 'Undefined')
        #todo: potential issue: upon startup, there might not yet be an mqtt connection, send may fail
        gateway.send(node.manufacturer_name, node.node_id, 'manufacturer_name')
        gateway.send(node.product_name, node.node_id, 'product_name')
    except:
        logger.exception('error while adding device: ' + str(node))


def addAsset(node, value):
    lbl = value.label.encode('ascii', 'ignore').replace('"', '\\"')        # make certain that we don't upload any illegal chars, also has to be ascii
    hlp = value.help.encode('ascii', 'ignore').replace('"', '\\"')         # make certain that we don't upload any illegal chars, also has to be ascii
    gateway.addAsset(getAssetName(value), node.node_id, lbl, hlp, not value.is_read_only, _getAssetType(node, value), _getStyle(node, value))
    # dont send the data yet, we have a seperate event for this

def getAssetName(value):
    """
    builds the asset name (local id) for a value. This consists out of command class and some extra details.
    :param value: a zwave value
    :return:
    """
    return "{}_{}_{}".format(value.command_class, value.index, value.instance)

def getValueFromName(name, device):
    """
    searches for hte value object in the device, based on the asset name.
    :param name: the name of the asset (command class,...)
    :param device: the device object that contains a list of the values.
    :return:
    """
    parts = name.split("_")
    if len(parts) != 3:
        raise Exception("invalid asset name, requires 3 parts: commandclass '_' index '_' instance")
    found = [device.values[x] for x in device.get_values(class_id=int(parts[0])) if device.values[x].index == int(parts[1]) and device.values[x].instance == int(parts[2])]
    if len(found) >= 1:
        return found[0]
    else:
        raise Exception("unknown asset: " + name)


def _getAssetType(node, val):
    '''extract the asset type from the command class'''

    logger.info("node type: " + val.type)            # for debugging
    dataType = str(val.type)

    type = '{"type": '
    if dataType == 'Bool' or dataType == 'Button':
        type += '"boolean"'
    elif dataType == 'Decimal':
        type += '"number"'
    elif dataType == 'Integer' or dataType == "Byte" or dataType == 'Int' or dataType == "Short":
        type += '"integer"'
    else:
        type = '{"type": "string"'                              #small hack for now.

    if dataType == 'Decimal' or dataType == 'Integer' or dataType == "Byte" or dataType == 'Int' or dataType == "Short":
        if (val.max or val.min) and val.max != val.min:
            type = addMinMax(type, node, val)
    if val.units:
        type += ', "unit": "' + val.units + '"'
    if val.data_items and isinstance(val.data_items, set):
        type += ', "enum": [' + ', '.join(['"' + y + '"' for y in val.data_items]) + ']'
    result = type + "}"
    return result

def addMinMax(type, node, val):
    if val.command_class in [_CC_MultiLevelSwitch, _CC_Battery]:
        return type + ', "maximum": 100, "minimum": 0'
    elif val.command_class == _CC_Wakeup:
        return type + ', "maximum": 16777215, "minimum": 0'
    else:
        if val.min == 4294934528 and val.min > val.max:         # for cc 115, 112
            min = 0
        else:
            min = val.min
        return type + ', "maximum": ' + str(val.max) + ', "minimum": ' + str(min)

def _getStyle(node, val):
    '''check the value type, if it is the primary cc for the device, set is primary, if it is battery...'''
    if str(val.genre) == 'Config':
        return 'Config'
    elif val.command_class == _CC_Battery:
        return 'Battery'
    else:
        primaryCCs = deviceClasses.getPrimaryCCFor(node.generic, node.specific)
        if primaryCCs:                              # if the dev class has a list of cc's than we can determine primary or secondary, otherwise, it's unknown.
            if val.command_class in primaryCCs:
                return 'Primary'
            return 'Secondary'
    return "Undefined"                  # if we get here, we don't know, so it is undefined.




###################
#test

def getValueTypeInt(valueStr):
    if valueStr == "Bool": return 0
    elif valueStr == "Byte": return 1
    elif valueStr == "Decimal":
        return 2
    elif valueStr == "Int":
        return 3
    elif valueStr == "List":
        return 4
    elif valueStr == "Schedule":
        return 5
    elif valueStr == "Short":
        return 6
    elif valueStr == "String":
        return 7
    elif valueStr == "Button":
        return 8
    elif valueStr == "Raw":
        return 9
    elif valueStr == "Max":
        return 9

def getGenreInt(genre):
    if genre == "Basic": return 0
    elif genre == "User": return 1
    elif genre == "Config":
        return 2
    elif genre == "System":
        return 3
    elif genre == "Count":
        return 4

def buildValueId(value):
    """create a value Id"""
    node = value.node

    m_id = ( node.node_id << 24) | (getGenreInt(value.genre) << 22) | (value.command_class << 14) | (value.index << 4) | getValueTypeInt(value.type);
    return m_id
