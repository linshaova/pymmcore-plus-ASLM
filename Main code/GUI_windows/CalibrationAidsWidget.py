from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)
from qtpy.QtCore import Signal


class CalibrationAidsWidget(QWidget):
    waveformToggled = Signal(bool)

    def __init__(self, daq):
        super().__init__()
        self._daq = daq

        self.down_ramp_high_voltage = self._make_voltage_input(1.25)
        self.down_ramp_low_voltage = self._make_voltage_input(-1.0)
        self.up_ramp_high_voltage = self._make_voltage_input(1.25)
        self.up_ramp_low_voltage = self._make_voltage_input(-1.0)
        self.camera_trigger_frequency = QDoubleSpinBox()
        self.camera_trigger_frequency.setRange(0.001, 100000.0)
        self.camera_trigger_frequency.setDecimals(6)
        self.camera_trigger_frequency.setValue(10.0)
        self.camera_trigger_frequency.setSingleStep(0.1)

        self.start_waveform_button = QPushButton("Start waveform")
        self.start_waveform_button.setCheckable(True)
        self.start_waveform_button.toggled.connect(self._toggle_waveform)

        layout = QFormLayout(self)
        layout.addRow("Down ramp high voltage", self.down_ramp_high_voltage)
        layout.addRow("Down ramp low voltage", self.down_ramp_low_voltage)
        layout.addRow("Up ramp high voltage", self.up_ramp_high_voltage)
        layout.addRow("Up ramp low voltage", self.up_ramp_low_voltage)
        layout.addRow("Camera trigger frequency", self.camera_trigger_frequency)
        layout.addRow(self.start_waveform_button)

    @staticmethod
    def _make_voltage_input(value):
        input_box = QDoubleSpinBox()
        input_box.setRange(-1000000.0, 1000000.0)
        input_box.setDecimals(6)
        input_box.setValue(value)
        input_box.setSingleStep(0.001)
        return input_box

    def _toggle_waveform(self, running):
        self.start_waveform_button.setText("Stop" if running else "Start waveform")
        try:
            if running:
                self.waveformToggled.emit(True)
                self._daq.start_calibration_waveform(
                    self.down_ramp_high_voltage.value(),
                    self.down_ramp_low_voltage.value(),
                    self.up_ramp_high_voltage.value(),
                    self.up_ramp_low_voltage.value(),
                    self.camera_trigger_frequency.value(),
                )
            else:
                self._daq.stop_calibration_waveform()
                self.waveformToggled.emit(False)
        except (OSError, ValueError, RuntimeError) as error:
            if running:
                self.waveformToggled.emit(False)
            self.start_waveform_button.blockSignals(True)
            self.start_waveform_button.setChecked(False)
            self.start_waveform_button.blockSignals(False)
            self.start_waveform_button.setText("Start waveform")
            QMessageBox.critical(self, "Waveform error", str(error))
            return
