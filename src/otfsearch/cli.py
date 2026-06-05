"""Command-line interface (a thin wrapper over the library functions)."""

from __future__ import annotations

import argparse

from . import settings


def _otf_pair(s: str):
    if "=" not in s:
        raise argparse.ArgumentTypeError("OTF must be WAVE=/path/to.otf")
    wave, path = s.split("=", 1)
    return int(wave), path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="otfsearch-cli", description="Local SIM reconstruction")
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("optimal", help="OTF search + reconstruction")
    o.add_argument("file")
    o.add_argument("--otf-dir", default=settings.OTF_DIR)
    o.add_argument("--channels", type=int, nargs="*")
    o.add_argument("--oilmin", type=int, default=settings.OIL_MIN)
    o.add_argument("--oilmax", type=int, default=settings.OIL_MAX)
    o.add_argument("--crop", type=int, default=settings.CROPSIZE)
    o.add_argument("--wiener", type=float, default=settings.WIENER)
    o.add_argument("--reg", action="store_true")
    o.add_argument("--max", action="store_true")
    o.add_argument("--regfile", default=None)
    o.add_argument("--ref", type=int, default=settings.REF_CHANNEL)

    s = sub.add_parser("single", help="reconstruct with specified OTFs")
    s.add_argument("file")
    s.add_argument("--otf", type=_otf_pair, action="append", default=[],
                   metavar="WAVE=PATH")
    s.add_argument("--channels", type=int, nargs="*")
    s.add_argument("--wiener", type=float, default=settings.WIENER)
    s.add_argument("--background", type=int, default=settings.BACKGROUND)
    s.add_argument("--time", type=int, default=None)
    s.add_argument("--reg", action="store_true")
    s.add_argument("--max", action="store_true")
    s.add_argument("--regfile", default=None)
    s.add_argument("--ref", type=int, default=settings.REF_CHANNEL)

    r = sub.add_parser("register", help="apply channel registration")
    r.add_argument("file")
    r.add_argument("--regfile", default=None)
    r.add_argument("--ref", type=int, default=settings.REF_CHANNEL)
    r.add_argument("--max", action="store_true")

    c = sub.add_parser("calibrate", help="compute registration from a bead image")
    c.add_argument("image")
    c.add_argument("--out-dir", default=settings.REGFILE_DIR)
    c.add_argument("--refs", type=int, nargs="*", default=None)

    w = sub.add_parser("wf", help="pseudo-widefield")
    w.add_argument("file")
    m = sub.add_parser("max", help="max-Z projection")
    m.add_argument("file")

    b = sub.add_parser("batch", help="batch a directory")
    b.add_argument("dir")
    b.add_argument("--mode", choices=["optimal", "single", "register"], default="optimal")
    b.add_argument("--otf-dir", default=settings.OTF_DIR)
    b.add_argument("--otf", type=_otf_pair, action="append", default=[])
    b.add_argument("--only-first", action="store_true")
    b.add_argument("--no-skip", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "optimal":
        from .search import make_best_reconstruction
        res = make_best_reconstruction(
            args.file, otf_dir=args.otf_dir, recon_waves=args.channels,
            oil_min=args.oilmin, oil_max=args.oilmax, cropsize=args.crop,
            wiener=args.wiener, do_reg=args.reg, do_max=args.max,
            reg_file=args.regfile, ref_channel=args.ref,
        )
        print("Best OTFs:", res["best_otfs"])
        for k, v in res.items():
            if isinstance(v, str):
                print(f"FILE READY - {k}: {v}")
    elif args.cmd == "single":
        from .reconstruct import postprocess, reconstruct_file
        otf_for = {wave: path for wave, path in args.otf}
        proc, logp = reconstruct_file(
            args.file, otf_for, recon_waves=args.channels, wiener=args.wiener,
            background=args.background, timepoints=args.time)
        print(f"FILE READY - reconstruction: {proc}")
        postprocess(proc, do_reg=args.reg, do_max=args.max, reg_file=args.regfile,
                    ref_channel=args.ref, on_log=print)
    elif args.cmd == "register":
        from .registration import apply_registration
        out, mx = apply_registration(args.file, reg_file=args.regfile,
                                     ref_channel=args.ref, do_max=args.max)
        print(f"FILE READY - registered: {out}")
        if mx:
            print(f"FILE READY - max: {mx}")
    elif args.cmd == "calibrate":
        from .registration import calibrate
        out = calibrate(args.image, out_dir=args.out_dir, refs=args.refs)
        print(f"FILE READY - registration: {out}")
    elif args.cmd == "wf":
        from .project import pseudo_widefield
        print(pseudo_widefield(args.file))
    elif args.cmd == "max":
        from .project import max_project
        print(max_project(args.file))
    elif args.cmd == "batch":
        from .batch import batch
        otf_for = {wave: path for wave, path in args.otf}
        batch(args.dir, args.mode, skip_processed=not args.no_skip,
              only_optimize_first=args.only_first,
              recon_kwargs={"otf_dir": args.otf_dir}, otf_for=otf_for, on_log=print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
