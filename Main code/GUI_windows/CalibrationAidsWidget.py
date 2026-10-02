from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)
from qtpy.QtCore import Signal


class CalibrationAidsWidget(QWidget):
    waveformToggled = Signal(bool)
    singleImageViewerToggled = Signal(bool)

    def __init__(self, daq):
        super().__init__()
        self._daq = daq

        self.down_ramp_high_voltage = self._make_voltage_input(1.25)
        self.down_ramp_low_voltage = self._make_voltage_input(-1.0)
        self.up_ramp_high_voltage = self._make_voltage_input(1.25)
        self.up_ramp_low_voltage = self._make_voltage_input(-1.0)
        self.down_ramp_offset = self._make_voltage_input(0.0)
        self.up_ramp_offset = self._make_voltage_input(0.0)
        self.camera_trigger_frequency = QDoubleSpinBox()
        self.camera_trigger_frequency.setRange(0.001, 100000.0)
        self.camera_trigger_frequency.setDecimals(6)
        self.camera_trigger_frequency.setValue(10.0)
        self.camera_trigger_frequency.setSingleStep(0.1)

        self.start_waveform_button = QPushButton("Start waveform")
        self.start_waveform_button.setCheckable(True)
        self.start_waveform_button.toggled.connect(self._toggle_waveform)
        self.single_image_viewer = QCheckBox("Use one image viewer")
        self.single_image_viewer.toggled.connect(self.singleImageViewerToggled)

        layout = QFormLayout(self)
        layout.addRow("Down ramp high voltage", self.down_ramp_high_voltage)
        layout.addRow("Down ramp low voltage", self.down_ramp_low_voltage)
        layout.addRow("Down ramp offset", self._make_offset_control(self.down_ramp_offset))
        layout.addRow("Up ramp high voltage", self.up_ramp_high_voltage)
        layout.addRow("Up ramp low voltage", self.up_ramp_low_voltage)
        layout.addRow("Up ramp offset", self._make_offset_control(self.up_ramp_offset))
        layout.addRow("Camera trigger frequency", self.camera_trigger_frequency)
        layout.addRow(self.single_image_viewer)
        layout.addRow(self.start_waveform_button)

    @staticmethod
    def _make_voltage_input(value):
        input_box = QDoubleSpinBox()
        input_box.setRange(-2.0, 2.0)
        input_box.setDecimals(3)
        input_box.setValue(value)
        input_box.setSingleStep(0.001)
        return input_box

    @staticmethod
    def _make_offset_control(offset_spin):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        offset_label = QLabel("offset")
        row_layout.addWidget(offset_label)
        row_layout.addWidget(offset_spin)
        return row

    def stop_waveform(self):
        # Stop the waveform if it is running, exactly as if the button had been
        # clicked. Used by the acquisition panel, which has to take the DAQ over.
        if self.start_waveform_button.isChecked():
            self.start_waveform_button.setChecked(False)

    def _toggle_waveform(self, running):
        self.start_waveform_button.setText("Stop" if running else "Start waveform")
        try:
            if running:
                down_high = self.down_ramp_high_voltage.value() + self.down_ramp_offset.value()
                down_low = self.down_ramp_low_voltage.value() + self.down_ramp_offset.value()
                up_high = self.up_ramp_high_voltage.value() + self.up_ramp_offset.value()
                up_low = self.up_ramp_low_voltage.value() + self.up_ramp_offset.value()

                self.waveformToggled.emit(True)
                self._daq.start_calibration_waveform(
                    down_high,
                    down_low,
                    up_high,
                    up_low,
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
