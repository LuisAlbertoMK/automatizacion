"""Tests para utils/logger.py — logging y métricas."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.logger import TramiteLogger, TramiteMetrics, get_logger, metrics  # noqa: E402


class TestTramiteLogger:
    """Lines 25-81: TramiteLogger básico."""

    def test_init_creates_logger(self):
        log = TramiteLogger("test_mod")
        assert log.modulo == "test_mod"
        assert log._logger is not None
        assert log._logger.name == "tramites.test_mod"

    def test_init_not_verbose_by_default(self):
        log = TramiteLogger("test_mod")
        assert log.verbose is False

    def test_init_verbose_param(self):
        log = TramiteLogger("test_mod", verbose=True)
        assert log.verbose is True

    def test_init_verbose_from_env(self):
        with patch.dict(os.environ, {"VERBOSE": "true"}):
            log = TramiteLogger("test_mod")
        assert log.verbose is True

    def test_info_logs(self):
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "info") as mock_info:
            log.info("test msg")
        mock_info.assert_called_once_with("test msg")

    def test_success_logs(self):
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "info") as mock_info:
            log.success("test msg")
        mock_info.assert_called_once_with("SUCCESS: test msg")

    def test_warn_logs(self):
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "warning") as mock_warn:
            log.warn("test msg")
        mock_warn.assert_called_once_with("test msg")

    def test_error_logs(self):
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "error") as mock_err:
            log.error("test msg")
        mock_err.assert_called_once_with("test msg")

    def test_debug_not_verbose_skips_print(self):
        log = TramiteLogger("test_mod", verbose=False)
        with patch.object(log._logger, "debug") as mock_debug:
            log.debug("test msg")
        mock_debug.assert_called_once_with("test msg")

    def test_debug_verbose_prints(self):
        log = TramiteLogger("test_mod", verbose=True)
        with patch.object(log._logger, "debug") as mock_debug:
            log.debug("test msg")
        mock_debug.assert_called_once_with("test msg")

    def test_get_logger_creates_instance(self):
        log = get_logger("test")
        assert isinstance(log, TramiteLogger)
        assert log.modulo == "test"

    def test_info_prints_colored_message(self):
        log = TramiteLogger("test_mod")
        with patch("builtins.print") as mock_print:
            log.info("hello")
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "[test_mod]" in args[0]
        assert "hello" in args[0]

    def test_error_prints_colored_message(self):
        log = TramiteLogger("test_mod")
        with patch("builtins.print") as mock_print:
            log.error("error!")
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "[ERR]" in args[0] or "[test_mod]" in args[0]


class TestTramiteMetrics:
    """Lines 84-152: TramiteMetrics y resumen."""

    def test_start_sets_tramite(self):
        tm = TramiteMetrics()
        tm.start("curp")
        assert tm._tramite == "curp"
        assert tm._start is not None

    def test_finish_without_start_returns_none(self):
        tm = TramiteMetrics()
        result = tm.finish(True)
        assert result is None

    def test_finish_success(self, tmp_path):
        tm = TramiteMetrics()
        tm.start("curp")
        tm._start -= 1  # 1 second ago
        with patch("utils.logger.METRICS_FILE", tmp_path / "test.jsonl"):
            result = tm.finish(True, extra={"test": "val"})
        assert result is not None
        assert result["tramite"] == "curp"
        assert result["success"] is True
        assert result["test"] == "val"
        assert result["elapsed_s"] >= 0.9

    def test_finish_writes_to_file(self, tmp_path):
        metrics_path = tmp_path / "metricas.jsonl"
        tm = TramiteMetrics()
        tm.start("nss")
        with patch("utils.logger.METRICS_FILE", metrics_path):
            tm.finish(False)
        assert metrics_path.read_text(encoding="utf-8") != ""
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert data["success"] is False
        assert data["tramite"] == "nss"

    def test_finish_exception_does_not_crash(self, tmp_path):
        tm = TramiteMetrics()
        tm.start("curp")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            result = tm.finish(True)
        assert result is not None  # record still returned

    def test_resumen_no_file(self, tmp_path):
        tm = TramiteMetrics()
        # METRICS_FILE doesn't exist
        with patch("utils.logger.METRICS_FILE", tmp_path / "noexist.jsonl"):
            assert tm.resumen() == {"total": 0}

    def test_resumen_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        tm = TramiteMetrics()
        with patch("utils.logger.METRICS_FILE", f):
            assert tm.resumen() == {"total": 0}

    def test_resumen_with_data(self, tmp_path):
        f = tmp_path / "data.jsonl"
        records = [
            {"timestamp": "2025-01-01", "tramite": "curp", "success": True, "elapsed_s": 10},
            {"timestamp": "2025-01-01", "tramite": "curp", "success": False, "elapsed_s": 30},
            {"timestamp": "2025-01-01", "tramite": "nss", "success": True, "elapsed_s": 20},
        ]
        f.write_text("\n".join(json.dumps(r) for r in records))
        tm = TramiteMetrics()
        with patch("utils.logger.METRICS_FILE", f):
            result = tm.resumen()
        assert result["total"] == 3
        assert result["exitosos"] == 2
        assert result["tasa_exito"] == "67%"
        assert result["por_tipo"]["curp"]["total"] == 2
        assert result["por_tipo"]["nss"]["total"] == 1
        assert result["por_tipo"]["curp"]["ok"] == 1

    def test_resumen_empty_records_after_parse(self, tmp_path):
        """Corrupted lines are skipped, resulting in empty records."""
        f = tmp_path / "bad.jsonl"
        f.write_text("not json\n{also not\n")
        tm = TramiteMetrics()
        with patch("utils.logger.METRICS_FILE", f):
            result = tm.resumen()
        assert result == {"total": 0}

    def test_resumen_read_exception_returns_total_0(self, tmp_path):
        f = tmp_path / "locked.jsonl"
        f.write_text("{}")
        tm = TramiteMetrics()
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with patch("utils.logger.METRICS_FILE", f):
                result = tm.resumen()
        assert result == {"total": 0}

    def test_global_metrics_instance(self):
        """metrics es una instancia global de TramiteMetrics."""
        assert isinstance(metrics, TramiteMetrics)


class TestTramiteLoggerFileHandler:
    """Lines 48-55: file handler creation."""

    def test_handler_created_once(self, tmp_path):
        with patch("utils.logger.LOG_DIR", tmp_path):
            log = TramiteLogger("test")
            assert len(log._logger.handlers) >= 1

    def test_reuses_handlers(self, tmp_path):
        with patch("utils.logger.LOG_DIR", tmp_path):
            log1 = TramiteLogger("test")
            count = len(log1._logger.handlers)
            log2 = TramiteLogger("test")
            assert len(log2._logger.handlers) == count  # same logger, no dup handlers
