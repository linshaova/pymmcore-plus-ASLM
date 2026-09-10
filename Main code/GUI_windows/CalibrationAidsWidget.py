from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qtpy.QtCore import Signal


class CalibrationAidsWidget(QWidget):
    waveformToggled = Signal(bool)

    def __init__(self, daq):
        super().__init__()
        self._daq = daq

        self.waveform_path = QLineEdit()
        self.waveform_path.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._select_waveform_file)

        waveform_row = QWidget()
        waveform_layout = QVBoxLayout(waveform_row)
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        waveform_layout.addWidget(self.waveform_path)
        waveform_layout.addWidget(browse_button)

        self.down_voltage_offset = self._make_offset_input()
        self.up_voltage_offset = self._make_offset_input()
        self.camera_trigger_frequency = QDoubleSpinBox()
        self.camera_trigger_frequency.setRange(0.001, 100000.0)
        self.camera_trigger_frequency.setDecimals(6)
        self.camera_trigger_frequency.setValue(10.0)
        self.camera_trigger_frequency.setSingleStep(0.1)

        self.start_waveform_button = QPushButton("Start waveform")
        self.start_waveform_button.setCheckable(True)
        self.start_waveform_button.toggled.connect(self._toggle_waveform)

        layout = QFormLayout(self)
        layout.addRow("Input waveform file", waveform_row)
        layout.addRow("Down voltage offset", self.down_voltage_offset)
        layout.addRow("Up voltage offset", self.up_voltage_offset)
        layout.addRow("Camera trigger frequency", self.camera_trigger_frequency)
        layout.addRow(self.start_waveform_button)

    @staticmethod
    def _make_offset_input():
        input_box = QDoubleSpinBox()
        input_box.setRange(-1000000.0, 1000000.0)
        input_box.setDecimals(6)
        input_box.setSingleStep(0.001)
        return input_box

    def _select_waveform_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input waveform file",
            "",
            "Waveform files (*.txt *.csv *.dat);;All files (*)",
        )
        if path:
            self.waveform_path.setText(path)

    def _toggle_waveform(self, running):
        try:
            if running:
                if not self.waveform_path.text():
                    raise ValueError("Select an input waveform file first.")
                self.waveformToggled.emit(True)
                self._daq.start_calibration_waveform(
                    self.waveform_path.text(),
                    self.down_voltage_offset.value(),
                    self.up_voltage_offset.value(),
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
            QMessageBox.critical(self, "Waveform error", str(error))
            return

        self.start_waveform_button.setText(
            "Stop waveform" if running else "Start waveform"
        )
