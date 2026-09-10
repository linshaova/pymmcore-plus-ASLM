from qtpy.QtWidgets import QFormLayout, QMainWindow, QDockWidget, QSpinBox, QWidget
from qtpy.QtCore import Qt
from pymmcore_widgets import PropertyWidget

from GUI_windows.Jog_panel import JogPanel
from GUI_windows.Acquisition_panel import AcquisitionPanel
from GUI_windows.debug_console import DebugConsole
from GUI_windows.Image_panel import ImageFrame
from GUI_windows.AcquisitionBridge import AcquisitionBridge
from GUI_windows.CalibrationAidsWidget import CalibrationAidsWidget


class ScanWidthWidget(QWidget):
    def __init__(self, core, device):
        super().__init__()
        self._core = core
        self._device = device
        self._spinbox = QSpinBox()
        self._spinbox.setRange(
            int(core.getPropertyLowerLimit(device, "ScanWidth")),
            int(core.getPropertyUpperLimit(device, "ScanWidth")),
        )
        self._spinbox.valueChanged.connect(self._set_scan_width)

        layout = QFormLayout(self)
        layout.addRow("ScanWidth", self._spinbox)
        core.events.propertyChanged.connect(self._on_property_changed)
        self.destroyed.connect(self._disconnect)
        self._refresh()

    def _refresh(self):
        self._spinbox.blockSignals(True)
        try:
            self._spinbox.setValue(
                int(float(self._core.getProperty(self._device, "ScanWidth")))
            )
            scan_mode = self._core.getProperty(self._device, "ScanMode")
            self._spinbox.setEnabled(scan_mode == "Scan Width")
        finally:
            self._spinbox.blockSignals(False)

    def _set_scan_width(self, value):
        try:
            self._core.setProperty(self._device, "ScanWidth", value)
        except (RuntimeError, ValueError):
            self._refresh()

    def _on_property_changed(self, device, property_name, value):
        if device == self._device and property_name in ("ScanMode", "ScanWidth"):
            self._refresh()

    def _disconnect(self):
        self._core.events.propertyChanged.disconnect(self._on_property_changed)


class MainWindow(QMainWindow):
    def __init__(self, core, DAQ, stage, MDA):
        super().__init__()
        self.setWindowTitle("Light Sheet Control")
        self.DAQ, self.stage, self.MDA = DAQ, stage, MDA

        self.image_frame = ImageFrame(core)
        self.setCentralWidget(self.image_frame)


        stage_dock = self._add_dock("Stage Jog", JogPanel(stage), Qt.LeftDockWidgetArea)
        self.acq_bridge = AcquisitionBridge(self.MDA)
        self.acquisition_panel = AcquisitionPanel(acquisition_controller=self.acq_bridge)
        acquisition_dock = self._add_dock("Acquisition", self.acquisition_panel, Qt.RightDockWidgetArea)

        self.acquisition_panel.acquisition_running_changed.connect(
            self.image_frame.set_acquisition_running
        )

        self._camera_device = core.getCameraDevice()
        camera_properties_panel = QWidget()
        camera_properties_layout = QFormLayout(camera_properties_panel)
        for property_name in (
            "Port",
            "Exposure",
            "TriggerMode",
            "ExposeOutMode",
            "ScanMode",
            "ScanDirection",
        ):
            camera_properties_layout.addRow(
                property_name,
                PropertyWidget(
                    self._camera_device,
                    property_name,
                    mmcore=core,
                ),
            )
        camera_properties_layout.addRow(ScanWidthWidget(core, self._camera_device))
        camera_prop_dock = self._add_dock(
            "Camera Properties", camera_properties_panel, Qt.LeftDockWidgetArea
        )
        calibration_aids_widget = CalibrationAidsWidget(DAQ)
        calibration_aids_widget.waveformToggled.connect(
            self.image_frame.set_waveform_mode
        )
        calibration_aids_dock = self._add_dock(
            "ASLM Calibration Aids", calibration_aids_widget, Qt.LeftDockWidgetArea
        )

        self.console = DebugConsole(stage=stage, DAQ=DAQ, MDA=MDA, mmc=core)
        console_dock = self._add_dock("Debug Console", self.console, Qt.RightDockWidgetArea)

        self.splitDockWidget(stage_dock, camera_prop_dock, Qt.Vertical)
        self.splitDockWidget(camera_prop_dock, calibration_aids_dock, Qt.Vertical)
        self.splitDockWidget(acquisition_dock, console_dock, Qt.Vertical)

    def _add_dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock
    
    def closeEvent(self, event):
        self.MDA.close()

        print("closeEvent: shutting down console")
        self.console.shutdown()
        print("closeEvent: console shut down")

        event.accept()

        import threading
        print("Alive threads before exit:")
        for t in threading.enumerate():
            print(f"  name={t.name!r}  daemon={t.daemon}  alive={t.is_alive()}  ident={t.ident}")

        import os
        os._exit(0)