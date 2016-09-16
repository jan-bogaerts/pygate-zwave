# main entry for the pyGate plugin that provides support for zwave devices

import json
import logging

from louie import dispatcher
from openzwave.network import ZWaveNetwork
from openzwave.option import ZWaveOption

import deviceEvents as events
import manager
import networkMonitor
from pygate_core import config

#_readyEvent = threading.Event()             # signaled when the zwave network has been fully started.


_hardResetId = 'hardReset'   #id of asset
_softResetId = 'softReset'   #id of asset
_assignRouteId = 'assignRoute'

logger = logging.getLogger('zwave')


def connectToGateway(moduleName):
    '''optional
        called when the system connects to the cloud.
    '''
    manager.init(moduleName)
    _setupZWave()


def syncDevices(existing, full=False):
    '''optional
       allows a module to synchronize it's device list.
       :param existing: the list of devices that are already known in the cloud for this module.
       :param full: when false, if device already exists, don't update, including assets. When true,
        update all, including assets
    '''
    #if _readyEvent.wait(10):                         # wait for a max amount of timeto get the network ready, otherwise we contintue
    #    manager.syncDevices(existing, Full)
    #else:
    #    logger.error('failed to start the network in time, continuing')
    manager.syncDevices(existing, full)


def syncGatewayAssets():
    '''
    optional. Allows a module to synchronize with the cloud, all the assets that should come at the level
    of the gateway.
    :param full: when false, if device already exists, don't update, including assets. When true,
    update all, including assets
    '''
    #don't need to wait for the zwave server to be fully ready, don't need to query it for this call.
    manager.gateway.addGatewayAsset(manager.discoveryStateId, 'zwave discovery state', 'add/remove devices to the network', True,  '{"type" :"string", "enum": ["off","include","exclude"]}')
    manager.gateway.addGatewayAsset(_hardResetId, 'zwave hard reset', 'reset the controller to factory default', True, 'boolean')
    manager.gateway.addGatewayAsset(_softResetId, 'zwave soft reset', 'reset the controller, but keep network configuration settings', True, 'boolean')
    manager.gateway.addGatewayAsset(_assignRouteId, 'zwave assign route', 'assign a network return route from a node to another one', True, '{"type":"object", "properties": {"from":{"type": "integer"}, "to":{"type": "integer"} } }')
    manager.gateway.addGatewayAsset(manager.controllerStateId, 'zwave controller state', 'the state of the controller', False, '{"type":"string", "enum": ["Normal", "Starting", "Cancel", "Error", "Waiting", "Sleeping", "InProgress", "Completed", "Failed", "NodeOk", "NodeFailed"] }')
    manager.gateway.addGatewayAsset(manager.networkStateId, 'zwave network state', 'Represents the state for the network', False, '{"type":"string", "enum": ["Starting", "Failed", "Started", "Ready", "Stopped", "Resetted", "Awaked"] }')
    manager.gateway.addGatewayAsset(manager.deviceStateId, 'zwave devices state', 'Represents the health of the device connectivity for the entire network', False, '{"type":"string", "enum": ["None queried", "Essentials queried", "Awake queried", "All queried", "All queried, some dead"] }')


def run():
    ''' optional
        main function of the plugin module'''
    #_readyEvent.wait()
    manager.gateway.send("off", None, manager.discoveryStateId)     # set init state at begin of run, not when gateway asset get defined, cause that also gets called at refresh, and we don't want to give init states for network and such, but keep currents states.
    manager.gateway.send("Starting", None, manager.controllerStateId)
    manager.gateway.send("Starting", None, manager.networkStateId)
    manager.gateway.send("None queried", None, manager.deviceStateId)
    events.connectSignals()
    networkMonitor.connectNetworkSignals()
    manager.start()

def stop():
    """"called when the application terminates.  Allows us to clean up the hardware correctly, so we cn be restarted without (cold) reboot"""
    logger.info("stopping zwave network")
    manager.network.stop()

def onDeviceActuate(device, actuator, value):
    '''called when an actuator command is received'''
    node = manager.network.nodes[int(device)]          # the device Id is received as a string, zwave needs ints...
    if node:
        if actuator == 'location':                      # location is a special case
            node.location = value
            events.sendOnDone = events.DataMessage(value, 'location', device)               # when the operation is done, we get an event from the controller, when this happened, update the cloud
        elif actuator == manager.refreshDeviceId:
            #todo: test if request_state really asks the device to refresh all command classes.
            manager.addDevice(node)  # update the node and it's values
            node.request_state()
        else:
            val = node.values[long(actuator)]
            if val:
                dataType = str(val.type)
                if dataType == 'Bool':
                    value = value.lower() == 'true'
                if dataType == "Button":
                    if value.lower() == 'true':
                        manager.network._manager.pressButton(val.value_id)
                    else:
                        manager.network._manager.releaseButton(val.value_id)
                elif dataType == 'Decimal':
                    value = float(value)
                elif dataType == 'Integer':
                    value = int(value)
                newValue = val.check_data(value)        #checks and possibly does some convertions
                if newValue != None:
                    val.data = newValue
                else:
                    logger.error('failed to set actuator: ' + actuator + " for device: " + device + ", unknown data type: " + dataType)
            else:
                logger.error("failed to set actuator: can't find actuator " + actuator + " for device " + node)
    else:
        logger.error("failed to  to set actuator: can't find device " + device)

def onActuate(actuator, value):
    '''callback for actuators on the gateway level'''
    if actuator == manager.discoveryStateId:               #change discovery state
        if value == 'include':
            events.sendAfterWaiting = events.DataMessage(value, actuator)
            manager._discoveryMode = "Include"
            manager.network.controller.add_node()
        elif value == 'exclude':
            manager._discoveryMode = "Exclude"
            events.sendAfterWaiting = events.DataMessage(value, actuator)
            manager.network.controller.remove_node()
        else:
            events.sendOnDone = events.DataMessage('off', actuator)
            manager.network.controller.cancel_command()
    elif actuator == _hardResetId:                  #reset controller
        _doHardReset()
    elif actuator == _softResetId:                  #reset controller
        logger.info("soft-resetting network")
        manager.network.controller.soft_reset()
    elif actuator == _assignRouteId:
        params = json.loads(value)
        logger.info("re-assigning route from: " + params['from'] + ", to: " + params['to'])
        manager.network.controller.begin_command_assign_return_route(params['from'], params['to'])
    else:
        logger.error("zwave: unknown gateway actuator command: " + actuator)


def _doHardReset():
    '''will send a hardware reset command to the controller.
    opzenzwave generates a lot of events during this operation, so louie signals
    (for nodes & value signals) have to be detached during this operation
    '''
    logger.info("resetting network")
    events.disconnectSignals()
    dispatcher.connect(_networkReset, ZWaveNetwork.SIGNAL_NETWORK_RESETTED)
    manager.network.controller.hard_reset()

def _networkReset():
    '''make certain that all the signals are reconnected.'''
    dispatcher.disconnect(_networkReset, ZWaveNetwork.SIGNAL_NETWORK_RESETTED)  # no longer need to monitor this?
    events.connectSignals()
    logger.info("network reset")

def _setupZWave():
    '''iniializes the zwave network driver'''
    options = _buildZWaveOptions()
    manager.network = ZWaveNetwork(options, log=None)

#def _waitForStartup():
#    '''
#    waits until the zwave network has been properly initialized (can take a while)
#    This is called from another thread, while the zwave is initializing, the rest can continue.
#    Once the zwave has been started up, a signal is set so that the main thread.
#    At some point, the main thread will do a call to syncGatewayAssets or syncDevices (or run).
#    These functions will wait until that signal has been set so that they are certain that the zwave
#    server has been init.
#    '''
#    manager.waitForAwake()
#    manager.waitForReady()
#    _readyEvent.set()


def _buildZWaveOptions():
    '''create the options object to start up the zwave server'''
    if not config.configs.has_option('zwave', 'port'):
        logger.error('zwave configuration missing: port')
        return
    if not config.configs.has_option('zwave', 'logLevel'):
        logger.error('zwave configuration missing: logLevel')
        return
    if not config.configs.has_option('zwave', 'config'):
        logger.error("zwave 'path to configuration files' missing: config")
        return

    port = config.configs.get('zwave', 'port')
    logger.info('zwave server on port: ' + port)
    logLevel = config.configs.get('zwave', 'logLevel')
    logger.info('zwave log level: ' + logLevel)

    options = ZWaveOption(port, config_path=config.configs.get('zwave', 'config'), user_path=".", cmd_line="")
    options.set_log_file("OZW_Log.log")
    options.set_append_log_file(False)
    options.set_console_output(True)
    options.set_save_log_level(logLevel)
    options.set_logging(False)
    options.lock()
    return options

