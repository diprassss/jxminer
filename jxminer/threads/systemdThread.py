import os, time, json
from systemd import journal
from slackclient import SlackClient

from entities.job import *
from thread import Thread
from modules.utility import printLog, sendSlack

class systemdThread(Thread):

    def __init__(self, start, Config):
        self.active = False
        self.job = False
        self.tick = 60
        self.journal = journal.Reader()
        self.config = Config
        self.trackPhrases = [e.strip() for e in self.config['systemd'].get('settings', 'reboot_phrases').split("\n")]
        self.init()
        if start:
            self.start()

    def init(self):
        self.job = Job(self.tick, self.update)


    def update(self, runner):
        if not self.journal:
            self.journal = journal.Reader()

        self.journal.seek_realtime(time.time() - self.tick)
        try:
            for entry in self.journal:
                for testWord in self.trackPhrases:
                    if testWord in entry['MESSAGE']:
                        # Hard reboot, normal reboot sometimes hangs halfway
                        try:
                            sendSlack('%s is rebooting the system due to GPU crashed' % (self.config['machine'].get('settings', 'box_name')))
                            printLog('Notifying Slack for reboot schedule', 'info')
                            time.sleep(1)
                        finally:
                            printLog('Rebooting system due to GPU crashed', 'error')
                            os.system('echo 1 > /proc/sys/kernel/sysrq && echo b > /proc/sysrq-trigger')
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