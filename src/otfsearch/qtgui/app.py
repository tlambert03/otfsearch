"""otfsearch PyQt6 GUI.

One window with two layouts that swap in place (sharing the same log, worker, and
status):

  • Basic     — two operations, no options: reconstruct a single file, or batch a
                directory. Optimized (OTF-search) reconstruction, all channels, with
                registration / max-Z / pseudo-widefield.
  • Advanced  — full controls across tabs (Optimized / Specify / Batch /
                Registration / Settings / Help).

Switch with the Mode menu. Both layouts drive the same backend
(``search``/``reconstruct``/``registration``/``batch``); long tasks run on a
``QThread`` (``Job``) whose ``log`` signal streams output to the shared log. Widget
state is read on the UI thread before each job, so there is no cross-thread access.
"""

from __future__ import annotations

import os
import sys
from functools import partial

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSplitter, QStackedWidget, QTabWidget, QVBoxLayout,
    QWidget,
)

from .. import filetypes, io_mrc, preflight, settings, userconfig


def _int_or_none(s: str):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


def _float_or(s: str, default: float) -> float:
    try:
        return float((s or "").strip())
    except ValueError:
        return default


class Job(QThread):
    """Runs one callable off the UI thread, streaming output through signals."""

    log = pyqtSignal(str)
    best = pyqtSignal(dict)        # best-OTF dict -> fill the Specify tab
    calibrated = pyqtSignal(str)   # new reg-file path from a calibration
    result = pyqtSignal(str)       # "" on success, else the error message

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self._fn(self)
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"ERROR: {e}")
            self.result.emit(str(e))
            return
        self.result.emit("")


class MainWindow(QMainWindow):
    def __init__(self, mode: str = "basic"):
        super().__init__()
        self.setWindowTitle("otfsearch")
        self.resize(960, 760)
        self.worker = None   # lazily-created recon_worker.ReconWorker
        self.job: Job | None = None
        self._run_buttons: list[QPushButton] = []

        self._build_menu()

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_basic_page())     # index 0
        self.stack.addWidget(self._build_advanced_page())  # index 1

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.stack)
        split.addWidget(self._build_log())
        split.setStretchFactor(1, 1)
        split.setSizes([360, 380])
        central = QWidget()
        QVBoxLayout(central).addWidget(split)
        self.setCentralWidget(central)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(160)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage("Ready")

        # mirror persisted library dirs into settings (so downstream defaults
        # such as pick_reg_file honor them)
        settings.OTF_DIR = self.otf_dir_edit.text()
        settings.REGFILE_DIR = self.regdir_edit.text()
        self.set_mode(mode)

    # ── menu / mode switch ──────────────────────────────────────────────────
    def _build_menu(self):
        modemenu = self.menuBar().addMenu("Mode")
        self.act_basic = QAction("Basic", self, checkable=True)
        self.act_adv = QAction("Advanced", self, checkable=True)
        grp = QActionGroup(self)
        grp.addAction(self.act_basic)
        grp.addAction(self.act_adv)
        self.act_basic.triggered.connect(lambda: self.set_mode("basic"))
        self.act_adv.triggered.connect(lambda: self.set_mode("advanced"))
        modemenu.addAction(self.act_basic)
        modemenu.addAction(self.act_adv)

        libs = self.menuBar().addMenu("Libraries")
        a1 = QAction("Set OTF library…", self)
        a1.triggered.connect(self.set_otf_lib)
        libs.addAction(a1)
        a2 = QAction("Set reg-file directory…", self)
        a2.triggered.connect(self.set_reg_dir)
        libs.addAction(a2)

    def set_mode(self, mode: str):
        self.stack.setCurrentIndex(0 if mode == "basic" else 1)
        self.act_basic.setChecked(mode == "basic")
        self.act_adv.setChecked(mode == "advanced")

    # ── basic page ──────────────────────────────────────────────────────────
    def _build_basic_page(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(
            "Optimized SIM reconstruction: searches the OTF library, reconstructs\n"
            "all channels, then registers, max-projects, and makes a pseudo-widefield."))
        self.btn_single = QPushButton("Reconstruct a single file…")
        self.btn_single.setMinimumHeight(54)
        self.btn_single.clicked.connect(self.do_single)
        self.btn_batch = QPushButton("Batch process a directory…")
        self.btn_batch.setMinimumHeight(54)
        self.btn_batch.clicked.connect(self.do_batch)
        self._run_buttons += [self.btn_single, self.btn_batch]
        v.addWidget(self.btn_single)
        v.addWidget(self.btn_batch)
        v.addStretch(1)
        return w

    # ── advanced page ───────────────────────────────────────────────────────
    def _build_advanced_page(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._build_top())
        tabs = QTabWidget()
        tabs.addTab(self._build_optimized(), "Optimized")
        tabs.addTab(self._build_specify(), "Specify OTFs")
        tabs.addTab(self._build_batch(), "Batch")
        tabs.addTab(self._build_registration(), "Registration")
        tabs.addTab(self._build_settings(), "Settings")
        tabs.addTab(self._build_help(), "Help")
        v.addWidget(tabs, 1)
        return w

    def _build_top(self) -> QWidget:
        box = QGroupBox("Input")
        v = QVBoxLayout(box)
        row1 = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("raw SIM .dv file")
        btn = QPushButton("Choose file…")
        btn.clicked.connect(self.choose_file)
        row1.addWidget(QLabel("Input file:"))
        row1.addWidget(self.input_edit, 1)
        row1.addWidget(btn)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Channels:"))
        self.chan_checks: dict[int, QCheckBox] = {}
        for ww in settings.WAVES:
            cb = QCheckBox(str(ww))
            cb.setEnabled(False)
            self.chan_checks[ww] = cb
            row2.addWidget(cb)
        row2.addSpacing(20)
        row2.addWidget(QLabel("Reference:"))
        self.ref_combo = QComboBox()
        for ww in settings.WAVES:
            self.ref_combo.addItem(str(ww), ww)
        self.ref_combo.setCurrentText(str(settings.REF_CHANNEL))
        row2.addWidget(self.ref_combo)
        row2.addStretch(1)
        v.addLayout(row2)

        row3 = QHBoxLayout()
        # on by default (the common workflow); settings.DO_* still drive API/CLI
        self.reg_check = QCheckBox("Channel registration")
        self.reg_check.setChecked(True)
        self.max_check = QCheckBox("Max-Z projection")
        self.max_check.setChecked(True)
        self.wf_check = QCheckBox("Pseudo-widefield")
        self.wf_check.setChecked(True)
        row3.addWidget(QLabel("After reconstruction:"))
        row3.addWidget(self.reg_check)
        row3.addWidget(self.max_check)
        row3.addWidget(self.wf_check)
        row3.addStretch(1)
        v.addLayout(row3)
        return box

    def _build_optimized(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        limits = QGroupBox("Limit OTFs used in the search")
        form = QFormLayout(limits)
        self.maxage = QLineEdit("" if settings.MAX_AGE is None else str(settings.MAX_AGE))
        self.maxnum = QLineEdit("" if settings.MAX_NUM is None else str(settings.MAX_NUM))
        self.cropsize = QLineEdit(str(settings.CROPSIZE))
        self.oilmin = QLineEdit(str(settings.OIL_MIN))
        self.oilmax = QLineEdit(str(settings.OIL_MAX))
        self.wieneropt = QLineEdit(str(settings.WIENER))
        form.addRow("Max OTF age (days):", self.maxage)
        form.addRow("Max number of OTFs:", self.maxnum)
        form.addRow("Crop size (px):", self.cropsize)
        form.addRow("Min oil RI:", self.oilmin)
        form.addRow("Max oil RI:", self.oilmax)
        form.addRow("Wiener:", self.wieneropt)
        h.addWidget(limits)

        force = QGroupBox("Force channel → OTF wavelength (advanced)")
        fform = QFormLayout(force)
        self.force_combos: dict[int, QComboBox] = {}
        for ww in settings.WAVES:
            combo = QComboBox()
            for x in settings.WAVES:
                combo.addItem(str(x), x)
            combo.setCurrentText(str(ww))
            self.force_combos[ww] = combo
            fform.addRow(f"channel {ww}:", combo)
        h.addWidget(force)

        right = QVBoxLayout()
        right.addStretch(1)
        run = QPushButton("Run OTF Search")
        run.clicked.connect(self.run_optimal)
        self._run_buttons.append(run)
        right.addWidget(run)
        right.addStretch(1)
        h.addLayout(right)
        return w

    def _build_specify(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        params = QHBoxLayout()
        self.wienerspec = QLineEdit(str(settings.WIENER))
        self.background = QLineEdit(str(settings.BACKGROUND))
        self.timepoints = QLineEdit("")
        for lbl, ed in (("Wiener:", self.wienerspec), ("Background:", self.background),
                        ("Timepoints:", self.timepoints)):
            params.addWidget(QLabel(lbl))
            ed.setMaximumWidth(90)
            params.addWidget(ed)
        params.addStretch(1)
        v.addLayout(params)

        form = QFormLayout()
        self.otf_edits: dict[int, QLineEdit] = {}
        for ww in settings.WAVES:
            ed = QLineEdit()
            self.otf_edits[ww] = ed
            b = QPushButton("Select…")
            b.clicked.connect(partial(self.select_otf, ww))
            rr = QHBoxLayout()
            rr.addWidget(ed, 1)
            rr.addWidget(b)
            holder = QWidget()
            holder.setLayout(rr)
            form.addRow(f"{ww} nm OTF:", holder)
        v.addLayout(form)

        run = QPushButton("Reconstruct")
        run.clicked.connect(self.run_single)
        self._run_buttons.append(run)
        v.addWidget(run)
        v.addStretch(1)
        return w

    def _build_batch(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        row = QHBoxLayout()
        self.batch_edit = QLineEdit()
        self.batch_edit.setPlaceholderText("directory of raw .dv files")
        b = QPushButton("Choose directory…")
        b.clicked.connect(self.choose_batch_dir)
        row.addWidget(QLabel("Directory:"))
        row.addWidget(self.batch_edit, 1)
        row.addWidget(b)
        v.addLayout(row)

        self.only_first = QCheckBox("Only optimize the first file, then reuse those OTFs")
        self.only_first.setChecked(True)
        self.skip_done = QCheckBox("Skip files already reconstructed")
        self.skip_done.setChecked(True)
        v.addWidget(self.only_first)
        v.addWidget(self.skip_done)

        btns = QHBoxLayout()
        for text, mode in (("Batch optimized", "optimal"),
                           ("Batch specified", "single"),
                           ("Batch register", "register")):
            b = QPushButton(text)
            b.clicked.connect(partial(self.run_batch, mode))
            self._run_buttons.append(b)
            btns.addWidget(b)
        v.addLayout(btns)
        v.addStretch(1)
        return w

    def _build_registration(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        apply_box = QGroupBox("Apply registration to the current input file")
        av = QVBoxLayout(apply_box)
        row = QHBoxLayout()
        self.regfile_edit = QLineEdit()
        self.regfile_edit.setPlaceholderText("registration .json")
        b = QPushButton("Choose…")
        b.clicked.connect(self.choose_regfile)
        row.addWidget(QLabel("Registration file:"))
        row.addWidget(self.regfile_edit, 1)
        row.addWidget(b)
        av.addLayout(row)
        rb = QPushButton("Register input file")
        rb.clicked.connect(self.run_register)
        self._run_buttons.append(rb)
        av.addWidget(rb)
        v.addWidget(apply_box)

        cal_box = QGroupBox("Calibrate from a bead / grid image")
        cv = QVBoxLayout(cal_box)
        row2 = QHBoxLayout()
        self.calib_edit = QLineEdit()
        self.calib_edit.setPlaceholderText("bead/grid .dv")
        b2 = QPushButton("Choose…")
        b2.clicked.connect(self.choose_calib)
        row2.addWidget(QLabel("Calibration image:"))
        row2.addWidget(self.calib_edit, 1)
        row2.addWidget(b2)
        cv.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Reference to:"))
        self.calib_refs = QComboBox()
        self.calib_refs.addItem("all", None)
        for ww in settings.WAVES:
            self.calib_refs.addItem(str(ww), ww)
        row3.addWidget(self.calib_refs)
        cb = QPushButton("Calibrate")
        cb.clicked.connect(self.run_calibrate)
        self._run_buttons.append(cb)
        row3.addWidget(cb)
        row3.addStretch(1)
        cv.addLayout(row3)
        v.addWidget(cal_box)
        v.addStretch(1)
        return w

    def _build_settings(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        saved = userconfig.load()
        self.otf_dir_edit = QLineEdit(saved.get("otf_dir", settings.OTF_DIR))
        self.regdir_edit = QLineEdit(saved.get("regfile_dir", settings.REGFILE_DIR))
        self.otf_dir_edit.textChanged.connect(self._on_otf_dir)
        self.regdir_edit.textChanged.connect(self._on_regfile_dir)
        form.addRow("OTF directory:", self._dir_row(self.otf_dir_edit))
        form.addRow("Reg-file directory:", self._dir_row(self.regdir_edit))
        note = QLabel(f"Default to settings.py; changes are saved to {userconfig.PATH} "
                      "and persist across sessions.")
        note.setWordWrap(True)
        form.addRow(note)
        return w

    def _build_help(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(
            "Mode → Basic gives two buttons (single file / batch directory) that run\n"
            "the standard optimized reconstruction. Mode → Advanced (this view) exposes\n"
            "all parameters.\n\n"
            "Choose a raw SIM .dv file (channels are detected automatically), then:\n"
            "  Optimized     search the OTF directory for the best OTF per channel.\n"
            "  Specify OTFs  reconstruct with the OTFs/parameters set on that tab.\n"
            "  Batch         run optimized/specified/register over a directory.\n"
            "  Registration  apply a reg file, or calibrate one from a bead grid.\n\n"
            "Set the OTF and reg-file directories on the Settings tab (or the Libraries\n"
            "menu). Requires an NVIDIA GPU + CUDA-12 driver and cudasirecon on PATH."
        )
        v.addWidget(txt)
        return w

    def _build_log(self) -> QWidget:
        box = QGroupBox("Log")
        v = QVBoxLayout(box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setFont(QFont("Consolas" if os.name == "nt" else "Monospace", 9))
        v.addWidget(self.log_view)
        return box

    def _dir_row(self, edit: QLineEdit) -> QWidget:
        b = QPushButton("Browse…")
        b.clicked.connect(lambda: self._browse_dir(edit))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(b)
        holder = QWidget()
        holder.setLayout(row)
        return holder

    # ── file/dir choosers + library config ──────────────────────────────────
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose raw SIM file", "", "DeltaVision/MRC (*.dv *.mrc)")
        if path:
            self.set_input(path)

    def set_input(self, path: str):
        self.input_edit.setText(path)
        try:
            waves = io_mrc._hdr_waves(io_mrc.read_header(path))
            for w, cb in self.chan_checks.items():
                present = w in waves
                cb.setEnabled(present)
                cb.setChecked(present)
            self.statusBar().showMessage(
                f"Loaded {os.path.basename(path)}: channels {waves}")
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"Could not read header: {e}")

    def choose_batch_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Batch directory")
        if d:
            self.batch_edit.setText(d)

    def select_otf(self, wave: int):
        path, _ = QFileDialog.getOpenFileName(
            self, f"OTF for channel {wave}", self.otf_dir_edit.text(), "OTF (*.otf)")
        if path:
            self.otf_edits[wave].setText(path)

    def choose_regfile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Registration file", self.regdir_edit.text(), "Registration (*.json)")
        if path:
            self.regfile_edit.setText(path)

    def choose_calib(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Calibration image", "", "DeltaVision (*.dv)")
        if path:
            self.calib_edit.setText(path)

    def _browse_dir(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Select directory", edit.text())
        if d:
            edit.setText(d)

    def set_otf_lib(self):
        d = QFileDialog.getExistingDirectory(self, "OTF library directory", settings.OTF_DIR)
        if d:
            self.otf_dir_edit.setText(d)   # textChanged -> settings + persist

    def set_reg_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Reg-file directory", settings.REGFILE_DIR)
        if d:
            self.regdir_edit.setText(d)

    def _on_otf_dir(self, text: str):
        settings.OTF_DIR = text
        userconfig.set_value("otf_dir", text)

    def _on_regfile_dir(self, text: str):
        settings.REGFILE_DIR = text
        userconfig.set_value("regfile_dir", text)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _selected_channels(self):
        return [w for w, cb in self.chan_checks.items() if cb.isChecked()]

    def _checked_input(self):
        path = self.input_edit.text()
        if not os.path.exists(path):
            QMessageBox.information(self, "Input error", "Input file does not exist.")
            return None
        if not filetypes.is_raw_sim_file(path):
            if QMessageBox.question(
                    self, "Input warning",
                    "File doesn't look like a raw SIM file. Continue?") \
                    != QMessageBox.StandardButton.Yes:
                return None
        return path

    def _ensure_otf_dir(self) -> bool:
        if settings.OTF_DIR and os.path.isdir(settings.OTF_DIR):
            return True
        d = QFileDialog.getExistingDirectory(self, "Select your OTF library directory")
        if not d:
            return False
        self.otf_dir_edit.setText(d)
        return True

    def get_worker(self):
        if self.worker is None:
            msg = preflight.check_gpu_stack()
            if msg:
                raise RuntimeError(msg)
            from ..recon_worker import ReconWorker
            self.worker = ReconWorker()
        return self.worker

    # ── basic actions ───────────────────────────────────────────────────────
    def do_single(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose raw SIM file", "", "DeltaVision/MRC (*.dv *.mrc)")
        if not path:
            return
        if not filetypes.is_raw_sim_file(path) and QMessageBox.question(
                self, "Input warning",
                "File doesn't look like a raw SIM file. Continue?") \
                != QMessageBox.StandardButton.Yes:
            return
        if not self._ensure_otf_dir():
            return
        try:
            worker = self.get_worker()
        except RuntimeError as e:
            QMessageBox.critical(self, "GPU engine", str(e))
            return
        ref = settings.REF_CHANNEL

        def fn(job):
            from .. import search, reconstruct, project
            res = search.make_best_reconstruction(
                path, otf_dir=settings.OTF_DIR, recon_waves=None,
                do_reg=False, do_max=True, ref_channel=ref,
                worker=worker, on_log=job.log.emit)
            for k in ("reconstruction", "max", "scores_csv", "log"):
                if res.get(k):
                    job.log.emit(f"FILE READY - {k}: {res[k]}")
            proc = res.get("reconstruction")
            if proc:
                try:
                    registered, _ = reconstruct.postprocess(
                        proc, do_reg=True, do_max=False, ref_channel=ref,
                        on_log=job.log.emit)
                    if registered:
                        job.log.emit(f"FILE READY - registered: {registered}")
                except Exception as e:  # noqa: BLE001
                    job.log.emit(f"registration skipped: {e}")
            try:
                job.log.emit(f"FILE READY - pseudoWF: {project.pseudo_widefield(path)}")
            except Exception as e:  # noqa: BLE001
                job.log.emit(f"pseudo-widefield failed: {e}")
        self._submit(fn)

    def do_batch(self):
        directory = QFileDialog.getExistingDirectory(self, "Directory of raw .dv files")
        if not directory:
            return
        if not self._ensure_otf_dir():
            return
        try:
            worker = self.get_worker()
        except RuntimeError as e:
            QMessageBox.critical(self, "GPU engine", str(e))
            return
        recon_kwargs = dict(otf_dir=settings.OTF_DIR, recon_waves=None,
                            ref_channel=settings.REF_CHANNEL, do_reg=False, do_max=False)

        def fn(job):
            from .. import batch as batchmod
            batchmod.batch(
                directory, "optimal", skip_processed=True, only_optimize_first=True,
                recon_kwargs=recon_kwargs, on_log=job.log.emit, worker=worker)
        self._submit(fn)

    # ── advanced actions ────────────────────────────────────────────────────
    def run_optimal(self):
        path = self._checked_input()
        if not path:
            return
        try:
            worker = self.get_worker()
        except RuntimeError as e:
            QMessageBox.critical(self, "GPU engine", str(e))
            return
        waves = self._selected_channels()
        force = {w: self.force_combos[w].currentData()
                 for w in waves if self.force_combos[w].currentData() != w}
        kw = dict(
            otf_dir=self.otf_dir_edit.text(), recon_waves=waves or None,
            force_channels=force or None,
            oil_min=int(self.oilmin.text()), oil_max=int(self.oilmax.text()),
            cropsize=int(self.cropsize.text()),
            max_age=_int_or_none(self.maxage.text()),
            max_num=_int_or_none(self.maxnum.text()),
            wiener=_float_or(self.wieneropt.text(), settings.WIENER),
            do_reg=self.reg_check.isChecked(), do_max=self.max_check.isChecked(),
            reg_file=self.regfile_edit.text() or None,
            ref_channel=int(self.ref_combo.currentText()),
        )
        do_wf = self.wf_check.isChecked()

        def fn(job):
            from .. import search
            res = search.make_best_reconstruction(
                path, worker=worker, on_log=job.log.emit, **kw)
            job.best.emit(res.get("best_otfs", {}))
            for k, val in res.items():
                if isinstance(val, str) and val:
                    job.log.emit(f"FILE READY - {k}: {val}")
            if do_wf:
                self._emit_wf(job, path)
        self._submit(fn)

    def run_single(self):
        path = self._checked_input()
        if not path:
            return
        try:
            worker = self.get_worker()
        except RuntimeError as e:
            QMessageBox.critical(self, "GPU engine", str(e))
            return
        waves = self._selected_channels()
        otf_for = {w: self.otf_edits[w].text() for w in waves if self.otf_edits[w].text()}
        bg = _int_or_none(self.background.text())
        kw = dict(
            recon_waves=waves or None,
            wiener=_float_or(self.wienerspec.text(), settings.WIENER),
            background=settings.BACKGROUND if bg is None else bg,
            timepoints=_int_or_none(self.timepoints.text()),
        )
        post = dict(do_reg=self.reg_check.isChecked(), do_max=self.max_check.isChecked(),
                    reg_file=self.regfile_edit.text() or None,
                    ref_channel=int(self.ref_combo.currentText()))
        do_wf = self.wf_check.isChecked()

        def fn(job):
            from .. import reconstruct
            proc, logp = reconstruct.reconstruct_file(
                path, otf_for, worker=worker, on_log=job.log.emit, **kw)
            job.log.emit(f"FILE READY - reconstruction: {proc}")
            if logp:
                job.log.emit(f"FILE READY - log: {logp}")
            registered, mx = reconstruct.postprocess(proc, on_log=job.log.emit, **post)
            for tag, val in (("registered", registered), ("max", mx)):
                if val:
                    job.log.emit(f"FILE READY - {tag}: {val}")
            if do_wf:
                self._emit_wf(job, path)
        self._submit(fn)

    def run_register(self):
        path = self.input_edit.text()
        if not os.path.exists(path):
            QMessageBox.information(self, "Input error", "Input file does not exist.")
            return
        reg_file = self.regfile_edit.text() or None
        ref = int(self.ref_combo.currentText())
        do_max = self.max_check.isChecked()

        def fn(job):
            from .. import registration
            out, mx = registration.apply_registration(
                path, reg_file=reg_file, ref_channel=ref, do_max=do_max)
            for tag, val in (("registered", out), ("max", mx)):
                if val:
                    job.log.emit(f"FILE READY - {tag}: {val}")
        self._submit(fn)

    def run_calibrate(self):
        path = self.calib_edit.text()
        if not os.path.exists(path):
            QMessageBox.information(self, "Input error", "Calibration image does not exist.")
            return
        refs = self.calib_refs.currentData()
        refs = None if refs is None else [refs]
        out_dir = self.regdir_edit.text() or None

        def fn(job):
            from .. import registration
            out = registration.calibrate(path, out_dir=out_dir, refs=refs)
            job.log.emit(f"FILE READY - registration: {out}")
            job.calibrated.emit(out)
        self._submit(fn)

    def run_batch(self, mode: str):
        directory = self.batch_edit.text()
        if not directory:
            QMessageBox.information(self, "No directory", "Choose a batch directory first.")
            return
        try:
            worker = self.get_worker() if mode in ("optimal", "single") else None
        except RuntimeError as e:
            QMessageBox.critical(self, "GPU engine", str(e))
            return
        waves = self._selected_channels()
        ref = int(self.ref_combo.currentText())
        recon_kwargs = dict(
            otf_dir=self.otf_dir_edit.text(), recon_waves=waves or None,
            oil_min=int(self.oilmin.text()), oil_max=int(self.oilmax.text()),
            cropsize=int(self.cropsize.text()),
            max_age=_int_or_none(self.maxage.text()), max_num=_int_or_none(self.maxnum.text()),
            wiener=_float_or(self.wieneropt.text(), settings.WIENER),
            do_reg=self.reg_check.isChecked(), do_max=self.max_check.isChecked(),
            reg_file=self.regfile_edit.text() or None, ref_channel=ref)
        otf_for = {w: self.otf_edits[w].text() for w in waves if self.otf_edits[w].text()}
        reg_kwargs = dict(reg_file=self.regfile_edit.text() or None,
                          ref_channel=ref, do_max=self.max_check.isChecked())
        skip = self.skip_done.isChecked()
        only_first = self.only_first.isChecked()

        def fn(job):
            from .. import batch as batchmod
            batchmod.batch(
                directory, mode, skip_processed=skip, only_optimize_first=only_first,
                recon_kwargs=recon_kwargs, reg_kwargs=reg_kwargs, otf_for=otf_for,
                on_log=job.log.emit, worker=worker)
        self._submit(fn)

    def _emit_wf(self, job, path: str):
        try:
            from .. import project
            job.log.emit(f"FILE READY - pseudoWF: {project.pseudo_widefield(path)}")
        except Exception as e:  # noqa: BLE001
            job.log.emit(f"pseudo-widefield failed: {e}")

    # ── job plumbing (shared) ───────────────────────────────────────────────
    def _submit(self, fn):
        if self.job is not None and self.job.isRunning():
            QMessageBox.information(self, "Busy", "A task is already running.")
            return
        self.job = Job(fn)
        self.job.log.connect(self._append_log)
        self.job.best.connect(self._fill_best)
        self.job.calibrated.connect(self.regfile_edit.setText)
        self.job.result.connect(self._job_done)
        self._set_busy(True)
        self.job.start()

    def _append_log(self, line: str):
        self.log_view.appendPlainText(line.rstrip("\n"))

    def _fill_best(self, best: dict):
        for k, v in best.items():
            w = int(k)
            if w in self.otf_edits:
                self.otf_edits[w].setText(str(v))
        self.statusBar().showMessage("Best OTFs added to the Specify tab")

    def _job_done(self, err: str):
        self._set_busy(False)
        self.statusBar().showMessage("Error — see log" if err else "Done", 6000)

    def _set_busy(self, busy: bool):
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0 if busy else 1)
        for b in self._run_buttons:
            b.setEnabled(not busy)
        if busy:
            self.statusBar().showMessage("Working…")

    def closeEvent(self, event):
        try:
            if self.worker is not None:
                self.worker.close()
        except Exception:  # noqa: BLE001
            pass
        event.accept()


def _launch(mode: str):
    app = QApplication(sys.argv)
    win = MainWindow(mode=mode)
    win.show()
    sys.exit(app.exec())


def main():            # otfsearch-qt : basic layout
    _launch("basic")


def main_advanced():   # otfsearch-qt-advanced : advanced layout
    _launch("advanced")


if __name__ == "__main__":
    main()
