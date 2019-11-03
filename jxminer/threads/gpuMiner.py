from threads import Thread
from entities import *
from miners import *

class gpuMiner(Thread):


    def __init__(self, **kwargs):
        super(gpuMiner, self).__init__()
        self.setPauseTime(1)
        self.configure(**kwargs)


    def init(self):
        self.miners = []
        self.selectMiner()
        if self.args.get('start', False):
            self.start()


    def update(self, runner):
        if self.isActive():
            for miner in self.miners:
                miner.start()
        else:
            for miner in self.miners:
                if miner.check() == 'give_up':
                    self.destroy()
                    break


    def destroy(self):
        if self.isActive():
            for miner in self.miners:
                miner.shutdown()
            self.stop()

        Logger.printLog("Stopping gpu miner", 'success')



    def selectMiner(self):
        c         = self.config.data.config
        d         = self.config.data.dynamic
        coin      = c.machine.gpu_miner.coin
        algo      = c.coins[coin].algo.lower()
        doDual    = c.machine.gpu_miner.dual
        amd       = c.miner[algo].amd
        nvidia    = c.miner[algo].nvidia
        dual      = c.miner[algo].dual
        amdGPU    = d.server.GPU.amd
        nvidiaGPU = d.server.GPU.nvidia
        miners    = []

        # AMD miner
        if amdGPU > 0 and amd:
            miners.append(amd)

        # Nvidia miner
        if nvidiaGPU > 0 and nvidia and nvidia not in miners:
            miners.append(nvidia)

        # Dual Miner
        if doDual and dual and dual not in miners:
            miners.append(dual)

        for miner in miners:
            if miner in 'ccminer':
                self.config.load('miners', 'ccminer.ini', True)
                self.miners.append(CCMiner())

            elif miner in 'claymore':
                self.config.load('miners', 'claymore.ini', True)
                self.miners.append(Claymore())

            elif miner in 'ethminer':
                self.config.load('miners', 'ethminer.ini', True)
                self.miners.append(ETHMiner())

            elif miner in 'ewbf':
                self.config.load('miners', 'ewbf.ini', True)
                self.miners.append(EWBF())

            elif miner in 'sgminer':
                self.config.load('miners', 'sgminer.ini', True)
                self.miners.append(SGMiner())

            elif miner in 'amdxmrig':
                self.config.load('miners', 'amdxmrig.ini', True)
                self.miners.append(AmdXMRig())

            elif miner in 'nvidiaxmrig':
                self.config.load('miners', 'nvidiaxmrig.ini', True)
                self.miners.append(NvidiaXMRig())

            elif miner in 'castxmr':
                self.config.load('miners', 'castxmr.ini', True)
                self.miners.append(CastXmr())

            elif miner in 'cryptodredge':
                self.config.load('miners', 'cryptodredge.ini', True)
                self.miners.append(CryptoDredge())

            elif miner in 'phoenixminer':
                self.config.load('miners', 'phoenixminer.ini', True)
                self.miners.append(PhoenixMiner())

            elif miner in 'trex':
                self.config.load('miners', 'trex.ini', True)
                self.miners.append(TRex())

            elif miner in 'avermore':
                self.config.load('miners', 'avermore.ini', True)
                self.miners.append(Avermore())

            elif miner in 'teamredminer':
                self.config.load('miners', 'teamredminer.ini', True)
                self.miners.append(TeamRedMiner())

            elif miner in 'wildrig':
                self.config.load('miners', 'wildrig.ini', True)
                self.miners.append(WildRig())

            else:
                Logger.printLog('Refused to load invalid miner program type', 'error')
