__author__ = 'Jan Bogaerts'
__copyright__ = "Copyright 2015, AllThingsTalk"
__credits__ = []
__maintainer__ = "Jan Bogaerts"
__email__ = "jb@allthingstalk.com"
__status__ = "Prototype"  # "Development", or "Production"

import logging
from louie import dispatcher #, All
from openzwave.network import ZWaveNetwork
import threading
from time import sleep

import manager

logger = logging.getLogger('zwave')
_restarter = None               # keeps track of the currently running network restarter object. We only want 1 at a time.

def restartNetwork():
    if not _restarter:              # we only want 1 restarter object at a time. If the network already failed previously without recovering, then don't try to restart a new object.
        logger.info("restarting network")
        manager.network.stop()      # try to stop the full network first??
        restarter = RestartManager()
        restarter.run()

def _networkFailed():
    """handle event"""
    global _restarter
    _sendNetworkState('Failed')
    restartNetwork()

def _networkStarted():
    """handle event"""
    _sendNetworkState('Started')

def _networkReady():
    """handle event"""
    _sendNetworkState('Ready')

def _networkStopped():
    """handle event"""
    _sendNetworkState('Stopped')

def _networkResetted():
    """handle event"""
    _sendNetworkState('Resetted')

def _networkAwaked():
    """handle event"""
    _sendNetworkState('Awaked')

def _essentialsQueried():
    """handle event"""
    _sendDeviceState('Essentials queried')

def _awakeQueried():
    """handle event"""
    _sendDeviceState('Awake queried')

def _allQueried():
    """handle event"""
    _sendDeviceState('All queried')

def _allQueriedSomeDead():
    """handle event"""
    _sendDeviceState('All queried, some dead')

def _sendNetworkState(value):
    try:
        logger.info(value)
        #dump(value)
        manager.gateway.send(value, None, manager.networkStateId)
    except:
        logger.exception('failed to send network state: ' + value)

def _sendDeviceState(value):
    try:
        logger.info(value)
        #dump(value)
        manager.gateway.send(value, None, manager.deviceStateId)
    except:
        logger.exception('failed to send network state: ' + value )

def disconnectNetworkSignals():
    dispatcher.disconnect(_networkFailed, ZWaveNetwork.SIGNAL_NETWORK_FAILED)
    dispatcher.disconnect(_networkStarted, ZWaveNetwork.SIGNAL_NETWORK_STARTED)
    dispatcher.disconnect(_networkReady, ZWaveNetwork.SIGNAL_NETWORK_READY)
    dispatcher.disconnect(_networkStopped, ZWaveNetwork.SIGNAL_NETWORK_STOPPED)
    dispatcher.disconnect(_networkResetted, ZWaveNetwork.SIGNAL_NETWORK_RESETTED)
    dispatcher.disconnect(_networkAwaked, ZWaveNetwork.SIGNAL_NETWORK_AWAKED)

    dispatcher.disconnect(_essentialsQueried, ZWaveNetwork.SIGNAL_ESSENTIAL_NODE_QUERIES_COMPLETE)
    dispatcher.disconnect(_awakeQueried, ZWaveNetwork.SIGNAL_NODE_QUERIES_COMPLETE)
    dispatcher.disconnect(_allQueried, ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED)
    dispatcher.disconnect(_allQueriedSomeDead, ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED_SOME_DEAD)


def connectNetworkSignals():
    dispatcher.connect(_networkFailed, ZWaveNetwork.SIGNAL_NETWORK_FAILED)
    dispatcher.connect(_networkStarted, ZWaveNetwork.SIGNAL_NETWORK_STARTED)
    dispatcher.connect(_networkReady, ZWaveNetwork.SIGNAL_NETWORK_READY)
    dispatcher.connect(_networkStopped, ZWaveNetwork.SIGNAL_NETWORK_STOPPED)
    dispatcher.connect(_networkResetted, ZWaveNetwork.SIGNAL_NETWORK_RESETTED)
    dispatcher.connect(_networkAwaked, ZWaveNetwork.SIGNAL_NETWORK_AWAKED)

    #todo: possible issue here: these might have to be dicsonncected for a reset, like other node events
    dispatcher.connect(_essentialsQueried, ZWaveNetwork.SIGNAL_ESSENTIAL_NODE_QUERIES_COMPLETE)
    dispatcher.connect(_awakeQueried, ZWaveNetwork.SIGNAL_AWAKE_NODES_QUERIED)
    dispatcher.connect(_allQueried, ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED)
    dispatcher.connect(_allQueriedSomeDead, ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED_SOME_DEAD)


class RestartManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        """continuously try to restart the network until it succeeds."""
        global _restarter
        started = False
        while not started:
            try:
                manager.start()
                #wait a bit to allow the network to start again.
                sleep(10)
                if manager.network.state == manager.network.STATE_STARTED:
                    started = True
            except Exception:
                logger.error('error while trying to restart the zwave network')
        _restarter = None                   # when we have succesfully restarted the network, this object can die and if the network were to fail again, a new object can be created