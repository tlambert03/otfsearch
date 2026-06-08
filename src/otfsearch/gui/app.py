"""otfsearch Tkinter GUI (local, single-process).

A faithful re-implementation of the original 5-tab tool with *all* of the
networking removed: no SSH, no upload/download, no server state machine.  Long
tasks run on a worker thread and stream their log into the text area via a
thread-safe queue drained on the Tk main loop.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from functools import partial
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .. import filetypes, io_mrc, preflight, settings, userconfig


def _int_or_none(s: str):
    s = (s or "").strip()
    return int(s) if s.isdigit() else None


def _float_or(s: str, default: float) -> float:
    s = (s or "").strip()
    try:
        return float(s)
    except ValueError:
        return default


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.worker = None  # lazily created otfsearch.recon_worker.ReconWorker
        self.log_queue: queue.Queue = queue.Queue()
        self._busy = False
        self._cancel = threading.Event()

        root.title("CBMF SIM Reconstruction Tool")
        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass

        self._build_vars()
        self._build_layout()
        root.after(100, self._drain)
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ── variables ──
    def _build_vars(self):
        s = settings
        self.input_path = tk.StringVar()
        self.ref_channel = tk.IntVar(value=s.REF_CHANNEL)
        # the post-reconstruction steps are on by default (the common workflow);
        # the settings.DO_* values still drive the API/CLI defaults
        self.do_reg = tk.IntVar(value=1)
        self.do_max = tk.IntVar(value=1)
        self.do_wf = tk.IntVar(value=1)
        self.chan_vars = {w: tk.IntVar(value=0) for w in s.WAVES}

        self.maxage = tk.StringVar(value="" if s.MAX_AGE is None else str(s.MAX_AGE))
        self.maxnum = tk.StringVar(value="" if s.MAX_NUM is None else str(s.MAX_NUM))
        self.cropsize = tk.StringVar(value=str(s.CROPSIZE))
        self.oilmin = tk.StringVar(value=str(s.OIL_MIN))
        self.oilmax = tk.StringVar(value=str(s.OIL_MAX))
        self.wieneropt = tk.StringVar(value=str(s.WIENER))
        self.force_vars = {w: tk.IntVar(value=w) for w in s.WAVES}

        self.wienerspec = tk.StringVar(value=str(s.WIENER))
        self.background = tk.StringVar(value=str(s.BACKGROUND))
        self.timepoints = tk.StringVar(value="")
        self.otf_paths = {w: tk.StringVar(value="") for w in s.WAVES}

        self.regfile = tk.StringVar(value="")
        self.calib_image = tk.StringVar(value="")
        self.calib_refs = tk.StringVar(value="all")

        # library locations: seed from persisted user config, then settings.py;
        # persist any change so they survive across sessions, and mirror into the
        # settings module so downstream defaults (e.g. pick_reg_file) honor them.
        _saved = userconfig.load()
        self.otf_dir = tk.StringVar(value=_saved.get("otf_dir", s.OTF_DIR))
        self.regfile_dir = tk.StringVar(value=_saved.get("regfile_dir", s.REGFILE_DIR))
        self.otf_dir.trace_add("write", self._on_otf_dir)
        self.regfile_dir.trace_add("write", self._on_regfile_dir)
        settings.OTF_DIR = self.otf_dir.get()
        settings.REGFILE_DIR = self.regfile_dir.get()

        self.batch_dir = tk.StringVar(value="")
        self.only_optimize_first = tk.IntVar(value=1)
        self.skip_processed = tk.IntVar(value=1)
        self.status_txt = tk.StringVar(value="Ready")

    # ── layout ──
    def _build_layout(self):
        root = self.root
        top = tk.Frame(root)
        nb = ttk.Notebook(root)
        text_frame = tk.Frame(root, bg="gray", bd=2)
        status_frame = tk.Frame(root)
        top.pack(side="top", fill="both", padx=15, pady=5)
        nb.pack(side="top", fill="both", padx=15, pady=5)
        text_frame.pack(side="top", fill="both", padx=15, pady=5)
        status_frame.pack(side="top", fill="both")

        self._build_top(top)

        opt = ttk.Frame(nb, padding=8)
        spec = ttk.Frame(nb, padding=8)
        batch = ttk.Frame(nb, padding=8)
        reg = ttk.Frame(nb, padding=8)
        cfg = ttk.Frame(nb, padding=8)
        helpf = ttk.Frame(nb, padding=8)
        nb.add(opt, text="Optimized Reconstruction")
        nb.add(spec, text="Specify OTFs")
        nb.add(batch, text="Batch")
        nb.add(reg, text="Channel Registration")
        nb.add(cfg, text="Settings")
        nb.add(helpf, text="Help")
        self._build_optimized(opt)
        self._build_specify(spec)
        self._build_batch(batch)
        self._build_registration(reg)
        self._build_settings(cfg)
        self._build_help(helpf)

        self.text_area = ScrolledText(text_frame, height=14)
        self.text_area.pack(side="bottom", fill="both")
        tk.Label(status_frame, textvariable=self.status_txt, bd=1, relief="sunken",
                 anchor="w", bg="gray").pack(side="bottom", fill="x")

    def _build_top(self, f):
        tk.Label(f, text="Input File:").grid(row=0, sticky="e")
        tk.Entry(f, textvariable=self.input_path, width=48).grid(
            row=0, column=1, columnspan=6, sticky="w")
        tk.Button(f, text="Choose File", command=self.choose_file).grid(
            row=0, column=7, ipady=3, ipadx=7, sticky="ew")

        tk.Label(f, text="Use Channels:").grid(row=1, sticky="e")
        self.chan_boxes = {}
        for i, w in enumerate(settings.WAVES):
            cb = tk.Checkbutton(f, text=str(w), variable=self.chan_vars[w],
                                state="disabled")
            cb.grid(row=1, column=i + 1, sticky="w")
            self.chan_boxes[w] = cb
        tk.Button(f, text="Quit", command=self.quit).grid(
            row=1, column=7, ipady=3, ipadx=7, sticky="ew")

        tk.Label(f, text="Ref Channel:").grid(row=2, sticky="e")
        tk.OptionMenu(f, self.ref_channel, *settings.WAVES).grid(row=2, column=1, sticky="w")
        tk.Checkbutton(f, text="Do registration", variable=self.do_reg).grid(
            row=2, column=2, columnspan=2, sticky="w")
        tk.Checkbutton(f, text="Do max", variable=self.do_max).grid(row=2, column=4, sticky="w")
        tk.Checkbutton(f, text="Do pseudoWF", variable=self.do_wf).grid(
            row=2, column=5, columnspan=2, sticky="w")
        tk.Button(f, text="Cancel", command=self.cancel).grid(
            row=2, column=7, ipady=3, ipadx=7, sticky="ew")

    def _build_optimized(self, f):
        labels = ["Max OTF age (days):", "Max number OTFs:", "Crop Size (pix):",
                  "Min Oil RI:", "Max Oil RI:", "Wiener:"]
        vars_ = [self.maxage, self.maxnum, self.cropsize, self.oilmin, self.oilmax,
                 self.wieneropt]
        tk.Label(f, text="Limit OTFs used in search",
                 font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        for i, (lbl, var) in enumerate(zip(labels, vars_)):
            tk.Label(f, text=lbl).grid(row=i + 1, sticky="e")
            tk.Entry(f, textvariable=var).grid(row=i + 1, column=1)

        tk.Label(f, text="Force channel:OTF pairings",
                 font=("Helvetica", 12, "bold")).grid(row=0, column=2, columnspan=2,
                                                       sticky="w", padx=(20, 0))
        for i, w in enumerate(settings.WAVES):
            tk.Label(f, text=f"OTF for channel {w}:").grid(
                row=i + 1, column=2, sticky="e", padx=(40, 0))
            tk.OptionMenu(f, self.force_vars[w], *settings.WAVES).grid(
                row=i + 1, column=3, sticky="w")
        tk.Button(f, text="Run OTF Search", command=self.run_optimal).grid(
            row=8, column=0, columnspan=4, ipady=8, ipadx=8, pady=20)

    def _build_specify(self, f):
        tk.Label(f, text="Reconstruct with the OTFs/settings specified here",
                 font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=7, sticky="w")
        tk.Label(f, text="Wiener:").grid(row=1, column=0, sticky="e")
        tk.Entry(f, textvariable=self.wienerspec, width=9).grid(row=1, column=1)
        tk.Label(f, text="Background:").grid(row=1, column=2, sticky="e")
        tk.Entry(f, textvariable=self.background, width=9).grid(row=1, column=3)
        tk.Label(f, text="Timepoints:").grid(row=1, column=4, sticky="e")
        tk.Entry(f, textvariable=self.timepoints, width=9).grid(row=1, column=5)
        for i, w in enumerate(settings.WAVES):
            tk.Label(f, text=f"{w}nm OTF:").grid(row=i + 2, column=0, sticky="e")
            tk.Entry(f, textvariable=self.otf_paths[w]).grid(
                row=i + 2, column=1, columnspan=5, sticky="ew")
            tk.Button(f, text="Select OTF", command=partial(self.select_otf, w)).grid(
                row=i + 2, column=6, ipady=3, ipadx=10)
        tk.Button(f, text="Reconstruct", command=self.run_single).grid(
            row=9, column=0, columnspan=7, ipady=8, ipadx=8, pady=8)

    def _build_batch(self, f):
        tk.Label(f, text="Batch process a directory of files.",
                 font=("Helvetica", 13, "bold")).grid(row=0, columnspan=5, sticky="w")
        tk.Label(f, text="Directory:").grid(row=1, sticky="e")
        tk.Entry(f, textvariable=self.batch_dir).grid(
            row=1, column=1, columnspan=2, pady=8, sticky="ew")
        tk.Button(f, text="Choose Dir", command=self.choose_batch_dir).grid(
            row=1, column=3, ipady=3, ipadx=10, padx=2, sticky="w")
        tk.Button(f, text="Batch Optimized Reconstruction",
                  command=partial(self.run_batch, "optimal")).grid(
            row=2, column=1, ipady=6, sticky="ew")
        tk.Button(f, text="Batch Specified Reconstruction",
                  command=partial(self.run_batch, "single")).grid(
            row=2, column=2, ipady=6, sticky="ew")
        tk.Checkbutton(f, text="Only optimize first file (then reuse those OTFs)",
                       variable=self.only_optimize_first).grid(
            row=5, column=1, columnspan=3, sticky="w")
        tk.Checkbutton(f, text="Skip files already reconstructed",
                       variable=self.skip_processed).grid(row=6, column=1, columnspan=3, sticky="w")
        tk.Button(f, text="Batch register processed files",
                  command=partial(self.run_batch, "register")).grid(
            row=7, column=1, ipady=6, sticky="ew")

    def _build_registration(self, f):
        tk.Label(f, text="Apply registration to the current input file",
                 font=("Helvetica", 13, "bold")).grid(row=0, column=0, columnspan=5, sticky="w")
        tk.Label(f, text="Registration File:").grid(row=1, column=0, sticky="e")
        tk.Entry(f, textvariable=self.regfile).grid(row=1, column=1, columnspan=3, sticky="ew")
        tk.Button(f, text="Choose File", command=self.choose_regfile).grid(
            row=1, column=4, ipady=3, ipadx=10, sticky="ew")
        tk.Button(f, text="Register Input File", command=self.run_register).grid(
            row=2, column=1, ipady=3, ipadx=10, sticky="w")
        tk.Label(f, text="Ref Channel:").grid(row=2, column=2, sticky="e")
        tk.OptionMenu(f, self.ref_channel, *settings.WAVES).grid(row=2, column=3, sticky="w")

        tk.Label(f, text="Calibrate from a bead/grid image",
                 font=("Helvetica", 13, "bold")).grid(row=3, columnspan=5, sticky="w", pady=(20, 0))
        tk.Label(f, text="Calibration Image:").grid(row=4, column=0, sticky="e")
        tk.Entry(f, textvariable=self.calib_image).grid(row=4, column=1, columnspan=3, sticky="ew")
        tk.Button(f, text="Choose Image", command=self.choose_calib).grid(
            row=4, column=4, ipady=3, ipadx=10, sticky="ew")
        tk.Label(f, text="Reference to:").grid(row=5, column=2, sticky="e")
        opts = ["all"] + [str(w) for w in settings.WAVES]
        tk.OptionMenu(f, self.calib_refs, *opts).grid(row=5, column=3, sticky="w")
        tk.Button(f, text="Calibrate", command=self.run_calibrate).grid(
            row=5, column=4, ipady=3, ipadx=10, sticky="ew")

    def _build_settings(self, f):
        tk.Label(f, text="Library locations:", font=("Helvetica", 13, "bold")).grid(
            row=0, column=0, columnspan=5, sticky="w")
        tk.Label(f, text="OTF Directory:").grid(row=1, sticky="e")
        tk.Entry(f, textvariable=self.otf_dir, width=52).grid(
            row=1, column=1, columnspan=6, sticky="w")
        tk.Button(f, text="Browse…", command=self.choose_otf_dir).grid(
            row=1, column=7, padx=(6, 0), sticky="w")
        tk.Label(f, text="Reg-file Directory:").grid(row=2, sticky="e")
        tk.Entry(f, textvariable=self.regfile_dir, width=52).grid(
            row=2, column=1, columnspan=6, sticky="w")
        tk.Button(f, text="Browse…", command=self.choose_regfile_dir).grid(
            row=2, column=7, padx=(6, 0), sticky="w")
        tk.Label(f, text=f"(Default to settings.py; changes are saved to {userconfig.PATH} "
                         "and persist across sessions.)").grid(
            row=3, column=0, columnspan=8, sticky="w", pady=(10, 0))

    def _build_help(self, f):
        txt = ScrolledText(f, wrap="word", height=16)
        txt.pack(fill="both")
        txt.insert("insert",
                   "Choose a raw SIM .dv file, pick the channels to reconstruct, then:\n\n"
                   "  • Optimized Reconstruction — searches the OTF directory for the best\n"
                   "    OTF per channel, then reconstructs. Best OTFs auto-fill the\n"
                   "    'Specify OTFs' tab.\n"
                   "  • Specify OTFs — reconstruct with the OTFs/settings on that tab.\n"
                   "  • Channel Registration — apply or calibrate channel registration.\n"
                   "  • Batch — run the above over a whole directory.\n\n"
                   "Set the OTF and reg-file directories on the Settings tab.\n")
        txt.config(state="disabled")

    # ── worker plumbing ──
    def get_worker(self):
        if self.worker is None:
            msg = preflight.check_gpu_stack()
            if msg:
                raise RuntimeError(msg)
            from ..recon_worker import ReconWorker
            self.worker = ReconWorker()
        return self.worker

    def log(self, msg: str):
        self.log_queue.put(("log", str(msg)))

    def status(self, msg: str):
        self.log_queue.put(("status", str(msg)))

    def _drain(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self.text_area.insert(tk.END, payload + "\n")
                    self.text_area.see(tk.END)
                elif kind == "status":
                    self.status_txt.set(payload)
                elif kind == "bestotfs":
                    for k, v in payload.items():
                        w = int(k)
                        if w in self.otf_paths:
                            self.otf_paths[w].set(v)
                    self.status_txt.set("Best OTFs added to 'Specify OTFs' tab")
                elif kind == "done":
                    self._busy = False
                    self.status_txt.set("Done")
        except queue.Empty:
            pass
        self.root.after(150, self._drain)

    def _submit(self, target):
        if self._busy:
            messagebox.showinfo("Busy", "A task is already running. Please wait.")
            return
        self._busy = True
        self._cancel.clear()
        self.status_txt.set("Working ...")
        threading.Thread(target=self._wrap(target), daemon=True).start()

    def _wrap(self, target):
        def run():
            try:
                target()
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
            finally:
                self.log_queue.put(("done", None))
        return run

    # ── file choosers ──
    def choose_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("DeltaVision", ".dv"), ("MRC", ".mrc")])
        if path:
            self.set_input(path)

    def set_input(self, path: str):
        self.input_path.set(path)
        try:
            waves = io_mrc._hdr_waves(io_mrc.read_header(path))
            for w in settings.WAVES:
                if w in waves:
                    self.chan_boxes[w].config(state="normal")
                    self.chan_vars[w].set(1)
                else:
                    self.chan_vars[w].set(0)
                    self.chan_boxes[w].config(state="disabled")
            self.status_txt.set(f"Loaded {os.path.basename(path)}: channels {waves}")
        except Exception as e:  # noqa: BLE001
            self.status_txt.set(f"Could not read header: {e}")

    def choose_batch_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.batch_dir.set(d)

    def _on_otf_dir(self, *_):
        settings.OTF_DIR = self.otf_dir.get()
        userconfig.set_value("otf_dir", self.otf_dir.get())

    def _on_regfile_dir(self, *_):
        settings.REGFILE_DIR = self.regfile_dir.get()
        userconfig.set_value("regfile_dir", self.regfile_dir.get())

    def choose_otf_dir(self):
        d = filedialog.askdirectory(
            initialdir=self.otf_dir.get() or None, title="OTF directory")
        if d:
            self.otf_dir.set(d)

    def choose_regfile_dir(self):
        d = filedialog.askdirectory(
            initialdir=self.regfile_dir.get() or None, title="Reg-file directory")
        if d:
            self.regfile_dir.set(d)

    def select_otf(self, wave: int):
        path = filedialog.askopenfilename(
            initialdir=self.otf_dir.get() or None,
            filetypes=[("OTF", "*.otf")], title=f"OTF for channel {wave}")
        if path:
            self.otf_paths[wave].set(path)

    def choose_regfile(self):
        path = filedialog.askopenfilename(
            initialdir=self.regfile_dir.get() or None,
            filetypes=[("Registration JSON", "*.json")])
        if path:
            self.regfile.set(path)

    def choose_calib(self):
        path = filedialog.askopenfilename(filetypes=[("DeltaVision", ".dv")])
        if path:
            self.calib_image.set(path)

    # ── helpers ──
    def selected_channels(self):
        return [w for w in settings.WAVES if self.chan_vars[w].get() == 1]

    def _check_input(self):
        path = self.input_path.get()
        if not os.path.exists(path):
            messagebox.showinfo("Input error", "Input file does not exist")
            return None
        if not filetypes.is_raw_sim_file(path):
            if not messagebox.askyesno(
                    "Input warning", "File doesn't look like a raw SIM file. Continue?"):
                return None
        return path

    def _report(self, outputs: dict):
        for key, val in outputs.items():
            if val and isinstance(val, str):
                self.log(f"FILE READY - {key}: {val}")

    # ── actions ──
    def run_optimal(self):
        path = self._check_input()
        if not path:
            return
        waves = self.selected_channels()
        force = {w: int(self.force_vars[w].get())
                 for w in waves if int(self.force_vars[w].get()) != w}

        def task():
            from .. import search
            res = search.make_best_reconstruction(
                path, otf_dir=self.otf_dir.get(),
                recon_waves=waves or None, force_channels=force or None,
                oil_min=int(self.oilmin.get()), oil_max=int(self.oilmax.get()),
                cropsize=int(self.cropsize.get()),
                max_age=_int_or_none(self.maxage.get()),
                max_num=_int_or_none(self.maxnum.get()),
                wiener=_float_or(self.wieneropt.get(), settings.WIENER),
                do_reg=bool(self.do_reg.get()), do_max=bool(self.do_max.get()),
                reg_file=self.regfile.get() or None,
                ref_channel=int(self.ref_channel.get()),
                worker=self.get_worker(), on_log=self.log,
            )
            self.log_queue.put(("bestotfs", res["best_otfs"]))
            self._report(res)
            if self.do_wf.get():
                self._make_wf(path)
        self._submit(task)

    def run_single(self):
        path = self._check_input()
        if not path:
            return
        waves = self.selected_channels()
        otf_for = {w: self.otf_paths[w].get() for w in waves if self.otf_paths[w].get()}

        bg = _int_or_none(self.background.get())
        background = settings.BACKGROUND if bg is None else bg

        def task():
            from .. import reconstruct
            proc, logp = reconstruct.reconstruct_file(
                path, otf_for, recon_waves=waves or None,
                wiener=_float_or(self.wienerspec.get(), settings.WIENER),
                background=background,
                timepoints=_int_or_none(self.timepoints.get()),
                worker=self.get_worker(), on_log=self.log,
            )
            self.log(f"FILE READY - reconstruction: {proc}")
            if logp:
                self.log(f"FILE READY - log: {logp}")
            registered, mx = reconstruct.postprocess(
                proc, do_reg=bool(self.do_reg.get()), do_max=bool(self.do_max.get()),
                reg_file=self.regfile.get() or None,
                ref_channel=int(self.ref_channel.get()), on_log=self.log,
            )
            self._report({"registered": registered, "max": mx})
            if self.do_wf.get():
                self._make_wf(path)
        self._submit(task)

    def run_register(self):
        path = self.input_path.get()
        if not os.path.exists(path):
            messagebox.showinfo("Input error", "Input file does not exist")
            return

        def task():
            from .. import registration
            out, mx = registration.apply_registration(
                path, reg_file=self.regfile.get() or None,
                ref_channel=int(self.ref_channel.get()),
                do_max=bool(self.do_max.get()),
            )
            self._report({"registered": out, "max": mx})
        self._submit(task)

    def run_calibrate(self):
        path = self.calib_image.get()
        if not os.path.exists(path):
            messagebox.showinfo("Input error", "Calibration image does not exist")
            return
        refs = None if self.calib_refs.get() == "all" else [int(self.calib_refs.get())]

        def task():
            from .. import registration
            out = registration.calibrate(
                path, out_dir=self.regfile_dir.get() or None, refs=refs)
            self.log(f"FILE READY - registration: {out}")
            self.regfile.set(out)
        self._submit(task)

    def run_batch(self, mode: str):
        directory = self.batch_dir.get()
        if not directory:
            messagebox.showinfo("No directory", "Choose a batch directory first")
            return
        waves = self.selected_channels()
        recon_kwargs = dict(
            otf_dir=self.otf_dir.get(), recon_waves=waves or None,
            oil_min=int(self.oilmin.get()), oil_max=int(self.oilmax.get()),
            cropsize=int(self.cropsize.get()),
            max_age=_int_or_none(self.maxage.get()), max_num=_int_or_none(self.maxnum.get()),
            wiener=_float_or(self.wieneropt.get(), settings.WIENER),
            do_reg=bool(self.do_reg.get()), do_max=bool(self.do_max.get()),
            reg_file=self.regfile.get() or None, ref_channel=int(self.ref_channel.get()),
        )
        otf_for = {w: self.otf_paths[w].get() for w in waves if self.otf_paths[w].get()}
        reg_kwargs = dict(reg_file=self.regfile.get() or None,
                          ref_channel=int(self.ref_channel.get()),
                          do_max=bool(self.do_max.get()))

        def task():
            from .. import batch as batchmod
            worker = self.get_worker() if mode in ("optimal", "single") else None
            batchmod.batch(
                directory, mode,
                skip_processed=bool(self.skip_processed.get()),
                only_optimize_first=bool(self.only_optimize_first.get()),
                recon_kwargs=recon_kwargs, reg_kwargs=reg_kwargs,
                otf_for=otf_for, on_log=self.log, worker=worker,
            )
        self._submit(task)

    def _make_wf(self, path: str):
        try:
            from .. import project
            self.log(f"FILE READY - pseudoWF: {project.pseudo_widefield(path)}")
        except Exception as e:  # noqa: BLE001
            self.log(f"pseudo-widefield failed: {e}")

    def cancel(self):
        self._cancel.set()
        self.status_txt.set("Cancel requested (current reconstruction will finish)")

    def quit(self):
        try:
            if self.worker is not None:
                self.worker.close()
        except Exception:  # noqa: BLE001
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
