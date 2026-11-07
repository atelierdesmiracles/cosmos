# Copyright (C) 2026 COSMOS contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Low-overhead, opt-in print progress journal for COSMOS.

This module records a recovery checkpoint only. It deliberately does NOT issue
motion, home axes, heat heaters, or restart a print after boot.
"""

import hashlib
import json
import os
import tempfile


JOURNAL_VERSION = 1
DEFAULT_INTERVAL = 10.0
DEFAULT_PATH = "/user-resource/power-resume/state.json"


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _seal(payload):
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _atomic_write(path, payload):
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    envelope = {"payload": payload, "sha256": _seal(payload)}
    fd, tmp_path = tempfile.mkstemp(prefix=".power-resume-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(envelope, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_journal(path):
    with open(path, "r", encoding="utf-8") as stream:
        envelope = json.load(stream)
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("invalid journal payload")
    if envelope.get("sha256") != _seal(payload):
        raise ValueError("journal checksum mismatch")
    if payload.get("version") != JOURNAL_VERSION:
        raise ValueError("unsupported journal version")
    return payload


class PowerResume:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.enabled = config.getboolean("enabled", False)
        self.interval = config.getfloat("interval", DEFAULT_INTERVAL,
                                        minval=5.0, maxval=120.0)
        self.path = config.get("journal_path", DEFAULT_PATH)
        if not os.path.isabs(self.path):
            raise config.error("journal_path must be an absolute path")
        self.last_position = -1
        self.last_write = 0.0
        self.last_error = None
        self.previous_checkpoint = None
        self.timer = None

        self.gcode.register_command("POWER_RESUME_STATUS",
                                    self.cmd_STATUS,
                                    desc="Show COSMOS power-resume journal status")
        self.gcode.register_command("POWER_RESUME_CLEAR",
                                    self.cmd_CLEAR,
                                    desc="Clear COSMOS power-resume journal")
        self.gcode.register_command("POWER_RESUME_CHECK",
                                    self.cmd_CHECK,
                                    desc="Validate the saved COSMOS recovery checkpoint")

        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("klippy:shutdown", self._handle_shutdown)

    def _handle_ready(self):
        if os.path.exists(self.path):
            try:
                self.previous_checkpoint = _read_journal(self.path)
                self.gcode.respond_info(
                    "COSMOS Power Resume: previous checkpoint found. "
                    "No motion or automatic resume will be performed."
                )
            except Exception as exc:
                self.last_error = str(exc)
                self.gcode.respond_info(
                    "COSMOS Power Resume: saved checkpoint is invalid: %s" % exc)
        if self.enabled:
            self.timer = self.reactor.register_timer(
                self._sample, self.reactor.monotonic() + self.interval)

    def _handle_shutdown(self):
        # A shutdown callback is best-effort only. The periodic journal is the
        # durable checkpoint; never assume this callback runs on power loss.
        try:
            self._sample(self.reactor.monotonic())
        except Exception:
            pass

    def _sample(self, eventtime):
        if not self.enabled:
            return self.reactor.NEVER
        try:
            vsd = self.printer.lookup_object("virtual_sdcard", None)
            if vsd is None or not getattr(vsd, "is_active", False):
                return eventtime + self.interval

            file_path = getattr(vsd, "file_path", None)
            position = int(getattr(vsd, "file_position", 0))
            if not file_path or position <= 0 or position == self.last_position:
                return eventtime + self.interval

            real_path = os.path.realpath(file_path)
            stat = os.stat(real_path)
            if not os.path.isfile(real_path):
                raise ValueError("active virtual SD file is not a regular file")

            gmove = self.printer.lookup_object("gcode_move")
            move_status = gmove.get_status(eventtime)
            toolhead = self.printer.lookup_object("toolhead")
            tool_status = toolhead.get_status(eventtime)
            extruder = self.printer.lookup_object("extruder", None)
            bed = self.printer.lookup_object("heater_bed", None)

            payload = {
                "version": JOURNAL_VERSION,
                "status": "printing",
                "file": real_path,
                "file_size": stat.st_size,
                "file_mtime_ns": getattr(stat, "st_mtime_ns",
                                          int(stat.st_mtime * 1000000000)),
                "file_position": position,
                "gcode_position": list(move_status.get("gcode_position", [])),
                "speed": float(move_status.get("speed", 0.0)),
                "speed_factor": float(move_status.get("speed_factor", 1.0)),
                "extrude_factor": float(move_status.get("extrude_factor", 1.0)),
                "absolute_coordinates": bool(
                    move_status.get("absolute_coordinates", True)),
                "absolute_extrude": bool(
                    move_status.get("absolute_extrude", True)),
                "homed_axes": str(tool_status.get("homed_axes", "")),
                "extruder_target": float(extruder.get_status(eventtime).get(
                    "target", 0.0)) if extruder is not None else 0.0,
                "bed_target": float(bed.get_status(eventtime).get(
                    "target", 0.0)) if bed is not None else 0.0,
                "updated_monotonic": float(eventtime),
            }
            _atomic_write(self.path, payload)
            self.last_position = position
            self.last_write = eventtime
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
            self.gcode.respond_info(
                "COSMOS Power Resume journal warning: %s" % exc)
        return eventtime + self.interval

    def _validate_checkpoint(self):
        payload = _read_journal(self.path)
        file_path = payload.get("file")
        if not file_path or not os.path.isfile(file_path):
            raise ValueError("original G-code file is missing")
        stat = os.stat(file_path)
        if stat.st_size != int(payload.get("file_size", -1)):
            raise ValueError("G-code file size changed since checkpoint")
        saved_mtime = int(payload.get("file_mtime_ns", -1))
        current_mtime = getattr(stat, "st_mtime_ns",
                                int(stat.st_mtime * 1000000000))
        if saved_mtime != current_mtime:
            raise ValueError("G-code file changed since checkpoint")
        position = int(payload.get("file_position", -1))
        if position < 0 or position >= stat.st_size:
            raise ValueError("saved file position is outside the G-code file")
        coords = payload.get("gcode_position")
        if not isinstance(coords, list) or len(coords) < 4:
            raise ValueError("saved G-code position is incomplete")
        return payload

    def cmd_STATUS(self, gcmd):
        try:
            payload = _read_journal(self.path)
            gcmd.respond_info(
                "COSMOS Power Resume: checkpoint=%s, file=%s, byte=%s, "
                "enabled=%s" % (
                    payload.get("status", "unknown"),
                    os.path.basename(payload.get("file", "unknown")),
                    payload.get("file_position", "unknown"),
                    self.enabled))
        except FileNotFoundError:
            gcmd.respond_info("COSMOS Power Resume: no checkpoint available")
        except Exception as exc:
            gcmd.respond_info("COSMOS Power Resume: invalid checkpoint: %s" % exc)

    def cmd_CHECK(self, gcmd):
        try:
            payload = self._validate_checkpoint()
            gcmd.respond_info(
                "COSMOS Power Resume: checkpoint valid for %s at byte %d. "
                "This command only validates metadata; it does not resume."
                % (os.path.basename(payload["file"]),
                   int(payload["file_position"])))
        except Exception as exc:
            gcmd.respond_info("COSMOS Power Resume: recovery not validated: %s" % exc)

    def cmd_CLEAR(self, gcmd):
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
            self.previous_checkpoint = None
            self.last_position = -1
            gcmd.respond_info("COSMOS Power Resume: checkpoint cleared")
        except Exception as exc:
            raise gcmd.error("Unable to clear Power Resume journal: %s" % exc)


def load_config(config):
    return PowerResume(config)
