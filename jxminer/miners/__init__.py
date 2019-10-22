import os, subprocess, psutil, time, re, pexpect, signal
from abc import ABCMeta, abstractmethod
from entities import *
from modules import *
from pprint import pprint

class Miner:

    """
        This is the base class for all of the miner instance
    """

    def __init__(self):
        self.config = Config()
        self.status = 'stop'
        self.checkKeywords = []
        self.buffers = []
        self.bufferStatus = dict()
        self.bufferStatus['diff'] = 0
        self.bufferStatus['hashrate'] = 0
        self.bufferStatus['shares'] = 0
        self.hasFee = False
        self.init()


    @abstractmethod
    def init(self):
        pass


    def processFeePayload(self, FeeRemoval, arg1, payload):
        pass


    def setupMiner(self, type):
        c                   = self.config.data.config
        name                = type + '_miner'
        self.type           = type
        self.max_retries    = 3
        self.machine        = c.machine
        self.coins          = c.coins
        self.coin           = c.machine[name].coin
        self.algo           = c.coins[self.coin].algo
        self.worker         = c.machine.settings.worker
        self.email          = c.machine.settings.email
        self.wd_hashrate    = c.machine[name].minimum_hashrate
        self.environment    = os.environ.copy()

        self.pool           = Pool(c.machine[name].pool)
        self.url            = self.pool.getAddress(self.coin)
        self.raw_url        = self.pool.getRawAddress(self.coin)
        self.raw_protocol   = self.pool.getRawProtocol(self.coin)
        self.port           = self.pool.getPort(self.coin)
        self.wallet         = self.pool.getWallet(self.coin)
        self.password       = self.pool.getPassword(self.coin)

        if 'gpu' in type and c.machine[name].dual:
            self.second_coin    = c.machine[name].second_coin
            self.second_algo    = self.coins[self.second_coin].algo
            self.second_pool    = Pool(self.machine[name].second_pool)
            self.second_url     = self.second_pool.getAddress(self.second_coin)
            self.second_wallet  = self.second_pool.getWallet(self.second_coin)

        if hasattr(self, 'miner'):
            self.miner_config   = self.config.data.miners[self.miner]
            self.miner_mode     = self.algo

            if hasattr(self, 'second_algo') and self.machine[name].dual:
                self.miner_mode = self.miner_mode + '|' + self.second_algo

            default = self.miner_config.settings
            try:
                extra = self.miner_config[self.miner_mode.lower()]
            # Put exception notice here later
            except:
                extra = False

            self.checkKeywords = UtilGetOption('check_keywords', default, extra)
            if self.checkKeywords:
                try:
                    self.checkKeywords = UtilExplode(self.checkKeywords)
                except Exception as e:
                    Logger.printLog(str(e), 'error')
            else:
                self.checkKeywords = []

            self.executable = UtilGetOption('executable', default, extra)
            self.option = (
                str(UtilGetOption('options', default, extra))
                    .replace('\n',              ' #-# ')
                    .replace('{raw_url}',       self.raw_url)
                    .replace('{raw_protocol}',  self.raw_protocol)
                    .replace('{port}',          self.port)
                    .replace('{url}',           self.url)
                    .replace('{wallet}',        self.wallet)
                    .replace('{password}',      self.password)
                    .replace('{worker}',        self.worker)
            )

            if 'cpu' in type:
                self.option = (
                    self.option
                        .replace('{thread}',    self.machine[name].thread)
                        .replace('{priority}',  self.machine[name].priority)
                )

            if hasattr(self, 'second_coin'):
                self.option = (
                    self.option
                        .replace('{second_url}',    self.second_url)
                        .replace('{second_wallet}', self.second_wallet)
                )



    def setupEnvironment(self):
        env = os.environ.copy()
        # python env wants string instead of int!
        env['GPU_FORCE_64BIT_PTR'] = '1'
        env['GPU_MAX_HEAP_SIZE'] = '100'
        env['GPU_USE_SYNC_OBJECTS'] = '1'
        env['GPU_MAX_ALLOC_PERCENT'] = '100'
        env['GPU_SINGLE_ALLOC_PERCENT'] = '100'
        self.environment = env



    def start(self):
        c       = self.config.data.config
        path    = c.machine.settings.executable_location or os.path.join('/usr', 'local')
        command = UtilFindFile(path, self.executable)

        if self.status == 'stop' and command:
            self.process = pexpect.spawn(
                command,
                self.setupArgs(UtilExplode(self.option.replace(' #-# ', ' '), ' ')),
                env=self.environment,
                timeout=None,
                cwd=os.path.dirname(command)
            )
            self.proc = psutil.Process(self.process.pid)
            self.status = 'ready'

            Logger.printLog('Initializing %s miner instance at %s' % (self.miner, command), 'success')

            self.monitor()



    def stop(self):
        if self.status == 'ready':
            self.process.terminate(True)
            self.process.wait()

            # Maybe redundant
            if psutil.pid_exists(self.process.pid):
                self.proc.terminate()
                self.proc.wait()

            # This is most probably redundant
            if psutil.pid_exists(self.process.pid):
                os.kill(self.process.pid, signal.SIGINT)

            self.status = 'stop'
            Logger.printLog('Stopping %s miner instance' % (self.miner), 'success')



    def check(self):
        if self.status == 'ready':
            if hasattr(self, 'proc'):
                if psutil.pid_exists(self.process.pid) and self.proc.status() != psutil.STATUS_ZOMBIE:
                    self.max_retries = 3

                else:
                    self.reboot()
                    self.max_retries = self.max_retries - 1
                    Logger.printLog('Restarting crashed %s miner instance' % (self.miner), 'info')

            if self.max_retries < 0:
                Logger.printLog('Maximum retry of -#%s#- reached' % 3, 'info')
                return 'give_up'

            return 'running'



    def shutdown(self):
        try:
            self.stop()
            status = 'success'
        except:
            status = 'error'
        finally:
            Logger.printLog('Shutting down %s miner' % (self.miner), status)



    def reboot(self):
        self.stop()
        time.sleep(5)
        self.start()



    def record(self, text):
        if len(self.buffers) > 10:
            self.buffers.pop(0)

        self.buffers.append(self.parse(text))



    def isHealthy(self, text):
        healthy = True
        for key in self.checkKeywords:
            if key in text:
                healthy = False
                break

        return healthy



    def monitor(self):
        p = self.process
        while True:
            output = p.readline()
            if output:
                self.record(output.replace('\r\n', '\n').replace('\r', '\n'))
                if not self.isHealthy(output):
                    self.minerSickAction()
                    break

            time.sleep(1)



    def minerSickAction(self):
        self.reboot()



    def parse(self, text):
        return text



    def display(self, lines = 'all'):
        result = None
        if self.buffers:
            if lines == 'all':
                result = self.buffers

            elif lines == 'last':
                result = self.buffers[-1]

            elif lines == 'first':
                result = self.buffers[0]

        return result



    def getStatus(self):
        return self.bufferStatus



    def hasDevFee(self):
        return self.hasFee


    def setupArgs(self, args):
        return args



# Registering all available miner instances
from amdxmrig import *
from avermore import *
from castxmr import *
from ccminer import *
from claymore import *
from cpuminer import *
from cpuxmrig import *
from cryptodredge import *
from ethminer import *
from ewbf import *
from nvidiaxmrig import *
from phoenixminer import *
from sgminer import *
from teamredminer import *
from trex import *
from wildrig import *
