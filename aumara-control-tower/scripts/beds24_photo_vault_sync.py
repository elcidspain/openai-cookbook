#!/usr/bin/env python3
"""Temporary wrapper: open Booking availability (restore photo vault sync after)."""
import runpy
import pathlib
runpy.run_path(str(pathlib.Path(__file__).with_name("beds24_open_booking_availability.py")), run_name="__main__")