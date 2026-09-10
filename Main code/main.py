
from logging import config
import sys
import os
os.environ["QT_API"] = "pyside6"

from qtpy.QtWidgets import QApplication
from Functions.VoiceCoil_nidaqmx import VoiceCoil_nidaqmx
from Functions.Acquisition import Acquisition
from Functions.stages_movement import stages_movement
from Main_window import MainWindow
def setup_classes(configs=None):
    DAQ = VoiceCoil_nidaqmx(configs)
    print('DAQ class initialized. Name: DAQ')
    stage = stages_movement(configs)
    print('stage class initialized. Name: stage')
    MDA = Acquisition(stage, DAQ, configs)
    print('Acquisition class initialized: Name: MDA')
    mmc = MDA.mmc
    print('Micromanager core initialized: Name: mmc')
    return DAQ, stage, MDA, mmc

def run(configs=None):
    DAQ, stage, MDA, mmc = setup_classes(configs)
    app = QApplication(sys.argv) 
    window = MainWindow(mmc, DAQ, stage, MDA)
    window.showMaximized()
    print("about to start event loop")
    result = app.exec()
    print("app.exec() returned:", result)
    sys.exit(result)                  

if __name__ == '__main__':
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        print(f"Using configuration file: {config_file}")
        import yaml
        allconfigs = yaml.safe_load(open(config_file))
    run(allconfigs)
