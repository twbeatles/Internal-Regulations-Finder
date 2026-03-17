# -*- coding: utf-8 -*-
from __future__ import annotations

from regfinder.runtime import get_op_logger


def test_get_op_logger_can_log_without_keyerror(caplog):
    log = get_op_logger("TEST-OP")

    with caplog.at_level("INFO", logger="RegSearch"):
        log.info("hello")

    assert any("hello" in record.message for record in caplog.records)
    assert any(getattr(record, "op_id", "") == "TEST-OP" for record in caplog.records)
