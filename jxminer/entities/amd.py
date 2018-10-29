import time

from modules.rocmsmi import *
from gpu import GPU

class AMD(GPU):

    """
        This is a class for GPU Type AMD

        Core Level Tuning
        - AMDGPUPRO Linux kernel driver is limited to selecting core level per level only, one need to modify and
          flash the GPU bios to fine tune the core frequency and its watt usage

        Memory Level Tuning
        - AMDGPUPRO Linux kernel driver is limited to selecting memory level per level only. It might not be useful
          to change memory level since mining operation usually will need to have the highest memory clocks available

        Power Level Tuning
        - This is not supported yet by this class

        Fan Level Tuning
        - AMDGPUPRO Linux kernel driver will use 0 - 255 as the value for fan speed, while this class expect
          percentage based from 0 - 100 and will convert the percentage value to the linux kernel value

    """

    def init(self):

        self.type = 'AMD'
        self.strictMode = False
        self.coreLevel = 100
        self.memoryLevel = 100
        self.powerLevel = False
        self.fanLevel = False
        self.fanSpeed = 0
        self.wattUsage = 0
        self.supportLevels = False
        self.machineIndex = 'card%s' % (self.index)

        if (setPerfLevel(self.machineIndex, 'manual')):
            self.maxCoreLevel = getMaxLevel(self.machineIndex, 'gpu')
            self.maxMemoryLevel = getMaxLevel(self.machineIndex, 'mem')
            self.supportLevels = int(self.maxCoreLevel) + int(self.maxMemoryLevel) > 0;

        self.detect()



    def detect(self):
        self.temperature = getSysfsValue(self.machineIndex, 'temp')
        self.fanSpeed = self.round(int(getSysfsValue(self.machineIndex, 'fan')) / 2.55)

        if self.fanLevel == False:
            self.fanLevel = self.fanSpeed

        if self.supportLevels:
            self.wattUsage = getSysfsValue(self.machineIndex, 'power')



    def reset(self):
        resetFans([self.machineIndex])
        if self.supportLevels:
            resetClocks([self.machineIndex])



    def tune(self, **kwargs):
        if kwargs.get('fan', False):
            self.setFanLevel(self.round(kwargs.get('fan')))

        if kwargs.get('core', False):
            self.setCoreLevel(self.round(kwargs.get('core')))

        if kwargs.get('memory', False):
            self.setMemoryLevel(self.round(kwargs.get('memory')))

        if kwargs.get('power', False):
            self.setPowerLevel(self.round(kwargs.get('power')))



    def setFanLevel(self, level):

        if level == self.fanSpeed:
            return

        setFanSpeed([self.machineIndex], self.round(level * 2.55))
        self.fanSpeed = level
        self.fanLevel = level



    def setCoreLevel(self, level):

        if not self.supportLevels or self.coreLevel == level:
            return

        s = self.strictMode
        m = self.maxCoreLevel
        d = self.round((level / (100 / (m + 1))))
        x = 0 if d < 0 else m if d > m else d
        levels = [ x ] if s else range(0, x)
        setClocks([self.machineIndex], 'gpu', levels)
        self.coreLevel = level



    def setMemoryLevel(self, level):

        if not self.supportLevels or self.memoryLevel == level:
            return

        s = self.strictMode
        m = self.maxMemoryLevel
        d = self.round( (level / (100 / (m + 1))))
        x = 0 if d < 0 else m if d > m else d
        levels = [ x ] if s else range(1, x)
        setClocks([self.machineIndex], 'mem', levels)
        self.memoryLevel = level



    def setPowerLevel(self, level):
        # Not supported yet
        pass