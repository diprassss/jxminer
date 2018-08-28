import os, time, json
from systemd import journal

from entities.job import *
from entities.config import *
from entities.logger import *
from thread import Thread
from modules.utility import sendSlack

class systemdThread(Thread):

    def __init__(self, start):
        self.active = False
        self.job = False
        self.tick = 60
        self.journal = journal.Reader()
        self.config = Config()
        self.trackPhrases = [e.strip() for e in self.config.data.config.systemd.settings.reboot_phrases.split("\n")]
        self.init()
        if start:
            self.start()

    def init(self):
        self.job = Job(self.tick, self.update)


    def update(self, runner):
        if not self.journal:
            self.journal = journal.Reader()

        c = self.config.data.config
        self.journal.seek_realtime(time.time() - self.tick)
        try:
            for entry in self.journal:
                for testWord in self.trackPhrases:
                    if testWord in entry['MESSAGE']:
                        try:
                            sendSlack('%s is rebooting the system due to GPU crashed' % (c.machine.settings.box_name))
                            sendSlack(entry['MESSAGE'])
                            Logger.printLog('Notifying Slack for reboot schedule', 'info')
                            time.sleep(1)

                        finally:
                            Logger.printLog('Rebooting system due to GPU crashed', 'error')

                            ## Hard Reboot can corrupt data! ##
                            if c.machine.settings.hard_reboot:
                                # os.system('sync')
                                # time.sleep(5)
                                os.system('echo 1 > /proc/sys/kernel/sysrq && echo b > /proc/sysrq-trigger')

                            ## Soft safe reboot, This might not work on all machine ##
                            else:
                                os.system('reboot -f')
        except:
            pass



    def destroy(self):
        try:
            if not self.journal.closed:
                self.journal.close()

            if self.job:
                self.job.shutdown_flag.set()
        except:
            pass

        finally:
            self.active = False