from contextlib import suppress

from qtpy.QtCore import QTimer, Qt
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from pymmcore_widgets import ImagePreview, LiveButton


class SplitImagePreview(QWidget):
    """Display alternating rolling-shutter frames in two image viewers."""

    def __init__(self, core):
        super().__init__()
        self._core = core
        self._frame_index = 0
        self._enabled = False

        self.down_preview = ImagePreview(mmcore=core, use_with_mda=False)
        self.up_preview = ImagePreview(mmcore=core, use_with_mda=False)
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

    def __init__(self, core):
        super().__init__()
        self._core = core
        self.normal_preview = ImagePreview(mmcore=core)
        self.split_preview = SplitImagePreview(core)
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.normal_preview)
        self.preview_stack.addWidget(self.split_preview)
        self.split_preview.set_active(False)
        # There's a pymmcore_widgets bug that clicking Snap button fails to obtain the image via mmc.snap()
        # self.snap_button = SnapButton(mmcore=core)
        self.live_button = LiveButton(mmcore=core)

        button_row = QHBoxLayout()
        # button_row.addWidget(self.snap_button)
        button_row.addWidget(self.live_button)
        button_row.addStretch()  # pushes buttons left, avoids them stretching full-width

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self.preview_stack)

    def set_split_preview(self, enabled):
        self.preview_stack.setCurrentWidget(
            self.split_preview if enabled else self.normal_preview
        )
        self.split_preview.set_active(enabled)

    def set_waveform_mode(self, enabled):
        if enabled:
            if not self._core.isSequenceRunning():
                self._core.startContinuousSequenceAcquisition()
        elif self._core.isSequenceRunning():
            self._core.stopSequenceAcquisition()
        self.set_split_preview(enabled)

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