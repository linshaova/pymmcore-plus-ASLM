from contextlib import suppress

from qtpy.QtCore import QTimer, Qt, Signal
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from pymmcore_widgets import ImagePreview, LiveButton


class LiveButtonWithDAQ(LiveButton):
    """LiveButton that ensures the DAQ laser tasks are configured before live starts."""

    def __init__(self, *, parent=None, mmcore=None, daq=None):
        self._daq = daq
        self._live_voltage = None
        super().__init__(parent=parent, mmcore=mmcore)

    def _toggle_live_mode(self):
        if self._daq is not None:
            if self._mmc.isSequenceRunning():
                super()._toggle_live_mode()
                self._daq.stop_live_tasks()
                self._daq.stop_live_ao_voltage()
                return

            try:
                self._daq.start_live_tasks()
                if self._live_voltage is not None:
                    self._daq.set_live_ao_voltage(self._live_voltage.value())
            except Exception as exc:
                print(f"Could not start Live DAQ tasks: {exc}")
                return

        super()._toggle_live_mode()


class AdjustableImagePreview(ImagePreview):
    """ImagePreview with adjustable low and high display intensity levels."""

    imageRangeChanged = Signal(float, float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_image = None
        self._manual_clims = None

    def _update_image(self, image):
        self._last_image = image
        if self._manual_clims is None:
            self._clims = "auto"
        else:
            self._clims = self._manual_clims
        super()._update_image(image)
        if self._manual_clims is None:
            self.imageRangeChanged.emit(float(image.min()), float(image.max()))

    def set_display_range(self, low, high):
        if low >= high:
            return False
        self._manual_clims = (low, high)
        self.clims = self._manual_clims
        return True

    def use_auto_levels(self):
        self._manual_clims = None
        self._clims = "auto"
        if self._last_image is not None:
            self._update_image(self._last_image)


class SplitImagePreview(QWidget):
    """Display alternating rolling-shutter frames in two image viewers."""

    def __init__(self, core):
        super().__init__()
        self._core = core
        self._frame_index = 0
        self._enabled = False

        self.down_preview = AdjustableImagePreview(mmcore=core, use_with_mda=False)
        self.up_preview = AdjustableImagePreview(mmcore=core, use_with_mda=False)
        self._detach_default_updates(self.down_preview)
        self._detach_default_updates(self.up_preview)

        down_panel = self._make_panel("Down scan", self.down_preview)
        up_panel = self._make_panel("Up scan", self.up_preview)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(down_panel)
        layout.addWidget(up_panel)

        core.events.imageSnapped.connect(self._on_image_snapped)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(10)
        self._poll_timer.timeout.connect(self._poll_buffer)
        self.destroyed.connect(self._disconnect)

    @staticmethod
    def _make_panel(title, preview):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedHeight(22)
        layout.addWidget(label, 0)
        layout.addWidget(preview, 1)
        return panel

    @staticmethod
    def _detach_default_updates(preview):
        events = preview._mmc.events
        with suppress(RuntimeError, TypeError):
            events.imageSnapped.disconnect(preview._on_image_snapped)
        with suppress(RuntimeError, TypeError):
            events.continuousSequenceAcquisitionStarted.disconnect(
                preview._on_streaming_start
            )
        with suppress(RuntimeError, TypeError):
            events.sequenceAcquisitionStopped.disconnect(preview._on_streaming_stop)
        with suppress(RuntimeError, TypeError):
            events.exposureChanged.disconnect(preview._on_exposure_changed)
        with suppress(RuntimeError, TypeError):
            preview._mmc.mda.events.frameReady.disconnect(preview._on_frame_ready)
        preview.streaming_timer.stop()

    def _display_next(self, image):
        preview = self.down_preview if self._frame_index % 2 == 0 else self.up_preview
        preview._update_image(image)
        self._frame_index += 1

    def _poll_buffer(self):
        if not self._enabled or self._core.mda.is_running():
            return
        while self._core.getRemainingImageCount() > 0:
            self._display_next(self._core.popNextImage())

    def _on_image_snapped(self):
        if self._enabled and not self._core.mda.is_running():
            with suppress(RuntimeError, IndexError):
                self._display_next(self._core.getLastImage())

    def setEnabled(self, enabled):
        self._enabled = enabled
        if enabled:
            self._poll_timer.start()
        else:
            self._poll_timer.stop()
        super().setEnabled(enabled)

    def set_active(self, active):
        self.setEnabled(active)
        if active:
            self._frame_index = 0

    def _disconnect(self):
        self._poll_timer.stop()
        with suppress(RuntimeError, TypeError):
            self._core.events.imageSnapped.disconnect(self._on_image_snapped)


class ImageFrame(QWidget):
    """Image preview with snap/live controls stacked above it."""

    def __init__(self, core, daq=None):
        super().__init__()
        self._core = core
        self._daq = daq
        self._waveform_mode = False
        self._single_image_viewer = False
        self.normal_preview = AdjustableImagePreview(mmcore=core)
        self.split_preview = SplitImagePreview(core)
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.normal_preview)
        self.preview_stack.addWidget(self.split_preview)
        self.split_preview.set_active(False)
        # There's a pymmcore_widgets bug that clicking Snap button fails to obtain the image via mmc.snap()
        # self.snap_button = SnapButton(mmcore=core)
        self.live_button = LiveButtonWithDAQ(mmcore=core, daq=daq)
        self.live_voltage = QDoubleSpinBox()
        self.live_voltage.setRange(-2.0, 2.0)
        self.live_voltage.setDecimals(3)
        self.live_voltage.setSingleStep(0.001)
        self.live_voltage.setValue(0.0)
        self.live_voltage.setKeyboardTracking(False)
        self.live_button._live_voltage = self.live_voltage
        self.live_voltage.editingFinished.connect(self._apply_live_ao_voltage)

        self.low_intensity = self._make_intensity_input()
        self.high_intensity = self._make_intensity_input()
        self.low_intensity.setValue(0.0)
        self.high_intensity.setValue(1.0)
        self.low_intensity.setToolTip("Intensity displayed as black")
        self.high_intensity.setToolTip("Intensity displayed as white")
        self.low_intensity.valueChanged.connect(self._apply_intensity_range)
        self.high_intensity.valueChanged.connect(self._apply_intensity_range)
        self.auto_levels = QCheckBox("Auto")
        self.auto_levels.setChecked(True)
        self.auto_levels.setToolTip(
            "Automatically use each image's full intensity range"
        )
        self.auto_levels.toggled.connect(self._set_auto_levels)
        self.low_intensity.setEnabled(False)
        self.high_intensity.setEnabled(False)

        button_row = QHBoxLayout()
        # button_row.addWidget(self.snap_button)
        button_row.addWidget(self.live_button)
        button_row.addWidget(self._make_voltage_label("VC voltage"))
        button_row.addWidget(self.live_voltage)
        button_row.addStretch()  # pushes buttons left, avoids them stretching full-width

        display_row = QHBoxLayout()
        display_row.addWidget(QLabel("Low intensity"))
        display_row.addWidget(self.low_intensity)
        display_row.addWidget(QLabel("High intensity"))
        display_row.addWidget(self.high_intensity)
        display_row.addWidget(self.auto_levels)
        display_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addLayout(display_row)
        layout.addWidget(self.preview_stack)

        for preview in (
            self.normal_preview,
            self.split_preview.down_preview,
            self.split_preview.up_preview,
        ):
            preview.imageRangeChanged.connect(self._update_intensity_inputs)

    @staticmethod
    def _make_intensity_input():
        input_box = QDoubleSpinBox()
        input_box.setRange(-1e12, 1e12)
        input_box.setDecimals(3)
        input_box.setSingleStep(1.0)
        input_box.setKeyboardTracking(False)
        return input_box

    def _update_intensity_inputs(self, low, high):
        self.low_intensity.blockSignals(True)
        self.high_intensity.blockSignals(True)
        self.low_intensity.setValue(low)
        self.high_intensity.setValue(high if high > low else low + 1.0)
        self.low_intensity.blockSignals(False)
        self.high_intensity.blockSignals(False)

    def _apply_intensity_range(self, _value=None):
        if self.auto_levels.isChecked():
            return
        low = self.low_intensity.value()
        high = self.high_intensity.value()
        if low >= high:
            if self.sender() is self.low_intensity:
                high = low + 1.0
                self.high_intensity.setValue(high)
            else:
                low = high - 1.0
                self.low_intensity.setValue(low)
        for preview in (
            self.normal_preview,
            self.split_preview.down_preview,
            self.split_preview.up_preview,
        ):
            preview.set_display_range(low, high)

    def _set_auto_levels(self, enabled):
        self.low_intensity.setEnabled(not enabled)
        self.high_intensity.setEnabled(not enabled)
        if enabled:
            for preview in (
                self.normal_preview,
                self.split_preview.down_preview,
                self.split_preview.up_preview,
            ):
                preview.use_auto_levels()
        else:
            self._apply_intensity_range()

    @staticmethod
    def _make_voltage_label(text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        return label

    def _apply_live_ao_voltage(self):
        if self._daq is None or self.live_button is None:
            return
        if self._core.isSequenceRunning() and hasattr(self._daq, "set_live_ao_voltage"):
            self._daq.set_live_ao_voltage(self.live_voltage.value())

    def set_split_preview(self, enabled):
        self.preview_stack.setCurrentWidget(
            self.split_preview if enabled else self.normal_preview
        )
        self.split_preview.set_active(enabled)

    def set_waveform_mode(self, enabled):
        self._waveform_mode = enabled
        if enabled:
            if not self._core.isSequenceRunning():
                self._core.startContinuousSequenceAcquisition()
        elif self._core.isSequenceRunning():
            self._core.stopSequenceAcquisition()
        self.set_split_preview(enabled and not self._single_image_viewer)

    def set_single_image_viewer(self, enabled):
        self._single_image_viewer = enabled
        self.set_split_preview(self._waveform_mode and not enabled)

    def set_acquisition_running(self, running: bool):
        # 1) Make sure "Live" is off while you acquire
        if running:
            try:
                # MMCore API (common): stopSequenceAcquisition
                self._core.stopSequenceAcquisition()
            except Exception:
                pass

            # In case widgets maintain their own state/timers, prevent user interaction
            self.live_button.setEnabled(False)
            # self.snap_button.setEnabled(False)
            self.preview_stack.setEnabled(False)
        else:
            self.live_button.setEnabled(True)
            self.preview_stack.setEnabled(True)