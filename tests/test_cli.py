"""CLI: zakres dni i maskowanie rekordów do testów."""

from __future__ import annotations

from datetime import date

import pytest

from vulcan_client import cli

def test_zakres_z_jawnych_dat_i_z_dni():
    """--from/--to biją --back/--ahead; odwrócony zakres jest odrzucany."""
    p = cli.build_parser()
    a = p.parse_args(["parse", "lessons", "--from", "2026-10-05", "--to", "2026-10-06"])
    assert cli.zakres(a) == (date(2026, 10, 5), date(2026, 10, 6))

    b = p.parse_args(["fetch", "lessons", "--back", "2", "--ahead", "0"])
    od, do = cli.zakres(b)
    assert (date.today() - od).days == 2 and do == date.today()

    c = p.parse_args(["parse", "lessons", "--from", "2026-10-06", "--to", "2026-10-05"])
    with pytest.raises(SystemExit):
        cli.zakres(c)


def test_maskuj_nie_wypuszcza_tekstow():
    rec = {"Day": {"Date": "2026-10-05"}, "Name": "Kowalski", "Id": 7, "Ok": True, "Lista": ["Ocena 5"]}
    zamaskowany = cli.maskuj(rec, False)
    assert zamaskowany == {"Day": {"Date": "NNNN-NN-NN"}, "Name": "Aaaaaaaa", "Id": 7,
                           "Ok": True, "Lista": ["Aaaaa N"]}
    # --daty zostawia samą datę, resztę nadal maskuje
    assert cli.maskuj(rec, True)["Day"]["Date"] == "2026-10-05"
    assert cli.maskuj(rec, True)["Name"] == "Aaaaaaaa"
