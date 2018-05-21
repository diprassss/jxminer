import os, subprocess, psutil, time, re, pexpect, signal

from entities.pool import Pool
from modules.transfer import *
from modules.utility import which, getOption, printLog, findFile, explode, stripAnsi
from pprint import pprint

class Miner:

    """
        This is the base class for invoking miner instance
    """

    def __init__(self, Config):
        self.config = Config
        self.status = 'stop'
        self.checkKeywords = []
        self.buffers = []
        self.bufferStatus = dict()
        self.bufferStatus['diff'] = 0
        self.bufferStatus['hashrate'] = 0
        self.bufferStatus['shares'] = 0
        self.init()


    def init(self):
        pass


    def setupMiner(self, type):
        name = type + '_miner'
        self.type = type
        self.max_retries = 3
        self.machine = self.config['machine']
        self.coins = self.config['coins']
        self.coin = self.machine.get(name, 'coin')
        self.algo = self.coins.get(self.coin, 'algo')
        self.pool = Pool(self.machine.get(name, 'pool'), self.config)
        self.url = self.pool.getAddress(self.coin)
        self.raw_url = self.pool.getRawAddress(self.coin)
        self.raw_protocol = self.pool.getRawProtocol(self.coin)
        self.port = self.pool.getPort(self.coin)
        self.wallet = self.pool.getWallet(self.coin)
        self.password = self.pool.getPassword(self.coin)
        self.worker = self.machine.get('settings', 'box_name')
        self.email = self.machine.get('settings', 'email')
        self.environment = os.environ.copy()

        if 'gpu' in type and self.machine.getboolean(name, 'dual'):
            self.second_coin = self.machine.get(name, 'second_coin')
            self.second_algo = self.coins.get(self.second_coin, 'algo')
            self.second_pool = Pool(self.machine.get(name, 'second_pool'), self.config)
            self.second_url = self.second_pool.getAddress(self.second_coin)
            self.second_wallet = self.second_pool.getWallet(self.second_coin)

        if hasattr(self, 'miner'):
            self.miner_config = self.config[self.miner]
            self.miner_mode = self.algo
            print self.algo
            print self.miner_mode

            if hasattr(self, 'second_algo') and self.machine.getboolean(name, 'dual'):
                self.miner_mode = self.miner_mode + '|' + self.second_algo

            default = dict(self.miner_config.items('default'))
            try:
                extra = dict(self.miner_config.items(self.miner_mode))
            except Exception as e:
                print e
                extra = False
            print extra
            self.executable = getOption('executable', default, extra)
            print self.executable
            self.option = (
                str(getOption('options', default, extra))
                    .replace('\n', ' #-# ')
                    .replace('{raw_url}', self.raw_url)
                    .replace('{raw_protocol}', self.raw_protocol)
                    .replace('{port}', self.port)
                    .replace('{url}', self.url)
                    .replace('{wallet}', self.wallet)
                    .replace('{password}', self.password)
                    .replace('{worker}', self.worker)
            )

            if 'cpu' in type:
                self.option = (
                    self.option
                        .replace('{thread}', self.machine.get(name, 'thread'))
                        .replace('{priority}', self.machine.get(name, 'priority'))
                )

            if hasattr(self, 'second_coin'):
                self.option = (
                    self.option
                        .replace('{second_url}', self.second_url)
                        .replace('{second_wallet}', self.second_wallet)
                )

            if self.miner_config.has_section('remote') and self.miner_config.getboolean('remote', 'enable'):
                try:
                    self.remote_ip = self.miner_config.get('remote', 'ip')
                except:
                    self.remote_ip = '127.0.0.1'
                self.remote_port = self.miner_config.get('remote', 'port')
                self.remote_token = self.miner_config.get('remote', 'token')
                self.option = (
                    self.option
                        .replace('{remote_ip}', self.remote_ip)
                        .replace('{remote_port}', self.remote_port)
                        .replace('{remote_token}', self.remote_token)
                        .replace('{worker}', self.worker)
                )



    def setupEnvironment(self):
        env = os.environ.copy()
        #python env wants string instead of int!
        env['GPU_FORCE_64BIT_PTR'] = '1'
        env['GPU_MAX_HEAP_SIZE'] = '100'
        env['GPU_USE_SYNC_OBJECTS'] = '1'
        env['GPU_MAX_ALLOC_PERCENT'] = '100'
        env['GPU_SINGLE_ALLOC_PERCENT'] = '100'
        self.environment = env



    def start(self):
        self.status = 'stop'
        command = findFile(os.path.join('/usr', 'local'), self.executable)
        #command = [findFile(os.path.join('/usr', 'local'), self.executable)]
        args = []
        for arg in explode(self.option, ' #-# '):
            for single in explode(arg, ' '):
                args.append(single)

        try:
            self.process = pexpect.spawn(command, args, env=self.environment, timeout=None)
            #self.process = subprocess.Popen(command, env=self.environment, bufsize=-1, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            #self.process = subprocess.Popen(command, env=self.environment, bufsize=-1, stdin=subprocess.PIPE)
            self.proc = psutil.Process(self.process.pid)
            self.monitor()
            self.status = 'ready'
            status = 'success'

        except:
            status = 'error'

        finally:
            printLog('Initializing %s miner instance' % (self.miner), status)



    def stop(self):
        self.status = 'stop'
        try:
            self.process.terminate(True)
            self.process.wait()

            # Maybe redundant
            if psutil.pid_exists(self.process.pid):
                self.proc.terminate()
                self.proc.wait()

            # This is most probably redundant
            if psutil.pid_exists(self.process.pid):
                os.kill(self.process.pid, signal.SIGINT)

            status = 'success'

        except:
            status = 'error'

        finally:
            printLog('Stopping %s miner instance' % (self.miner), status)



    def check(self):
        if 'ready' in self.status:
            if hasattr(self, 'proc'):
                try:
                    psutil.pid_exists(self.process.pid)
                    self.proc.status() != psutil.STATUS_ZOMBIE
                    alive = True
                except:
                    alive = False
                finally:
                    if not alive:
                        self.stop()
                        time.sleep(5)
                        self.start()
                        self.max_retries = self.max_retries - 1
                        printLog('Restarting crashed %s miner instance' % (self.miner), 'info')
                    else:
                        self.max_retries = 3


            if self.max_retries < 0:
                printLog('Maximum retry of -#%s#- reached' % 3, 'info')
                return 'give_up'

            return 'running'


    def shutdown(self):
        self.status = 'stop'
        try:
            self.stop()
            status = 'success'
        except:
            status = 'error'
        finally:
            printLog('Shutting down %s miner' % (self.miner), status)



    def reboot(self):
        self.stop()
        self.start()



    def record(self, text):
        if len(self.buffers) > 10:
            self.buffers.pop(0)

        self.buffers.append(self.parse(text))



    def isHealthy(self, text):
        healthy = True
        for key in self.checkKeywords:
            healthy = key not in text
            if not healthy:
                break
        return healthy



    def monitor(self):
        p = self.process
        while True:
            try:
                output = p.readline()
                if not output:
                    break

                self.record(output.replace('\r\n', '\n').replace('\r', '\n'))

                if not self.isHealthy(output):
                    self.reboot()

            except:
                break



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
