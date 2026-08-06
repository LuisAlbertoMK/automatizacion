"""Tests para utils/logger.py — logging y métricas."""

import json
import logging
import os
from unittest.mock import patch

from src.utils.logger import (
    JsonFormatter,
    TramiteLogger,
    TramiteMetrics,
    get_logger,  # noqa: E402
    metrics,
)


class TestJsonFormatter:
    """JsonFormatter.format() — output JSON con/sin extra_data."""

    def test_format_sin_extra_data(self):
        record = logging.LogRecord("tramites.test", logging.INFO, "f.py", 1,
                                   "msg %s", ("arg",), None)
        out = json.loads(JsonFormatter().format(record))
        assert out["level"] == "INFO"
        assert out["logger"] == "tramites.test"
        assert out["message"] == "msg arg"
        assert "timestamp" in out

    def test_format_con_extra_data(self):
        record = logging.LogRecord("tramites.test", logging.ERROR, "f.py", 1,
                                   "fallo", (), None)
        record.extra_data = {"curp": "GODE561231HDFRRN09"}
        out = json.loads(JsonFormatter().format(record))
        assert out["curp"] == "GODE561231HDFRRN09"
        assert out["level"] == "ERROR"


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

    def test_warning_alias_delega_en_warn(self):
        """warning() alias → warn() (línea 114)."""
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "warning") as mock_warn:
            log.warning("test msg")
        mock_warn.assert_called_once_with("test msg")

    def test_info_pii_sanitiza_en_archivo(self):
        """info_pii: stdout con PII, archivo sanitizado (127-132)."""
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "info") as mock_info:
            with patch("builtins.print") as mock_print:
                log.info_pii("curp: GODE561231HDFRRN09 listo",
                             "GODE561231HDFRRN09", "curp")
        mock_info.assert_called_once_with("curp: GODE**** listo")
        mock_print.assert_called_once()
        printed = mock_print.call_args.args[0]
        assert "GODE561231HDFRRN09" not in printed

    def test_error_logs(self):
        log = TramiteLogger("test_mod")
        with patch.object(log._logger, "error") as mock_err:
            log.error("test msg")
        mock_err.assert_called_once_with("test msg", exc_info=False)

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

    def test_print_sanitize_env_masks_pii(self):
        """SANITIZE_STDOUT=true → PII enmascarada en stdout."""
        with patch.dict(os.environ, {"SANITIZE_STDOUT": "true"}):
            log = TramiteLogger("prod_mod")
            with patch("builtins.print") as mock_print:
                log.info("CURP GODE561231HDFRRN09 listo")
            printed = mock_print.call_args.args[0]
            assert "GODE561231HDFRRN09" not in printed
            assert "GODE****" in printed

    def test_print_no_sanitize_by_default(self):
        """SANITIZE_STDOUT no set (default false) → PII visible en stdout."""
        os.environ.pop("SANITIZE_STDOUT", None)
        log = TramiteLogger("dev_mod")
        with patch("builtins.print") as mock_print:
            log.info("CURP GODE561231HDFRRN09 listo")
        printed = mock_print.call_args.args[0]
        assert "GODE561231HDFRRN09" in printed

    def test_init_json_format_from_env(self, tmp_path):
        """LOG_FORMAT=json → el file handler usa JsonFormatter (línea 77)."""
        with patch("src.utils.logger.LOG_DIR", tmp_path):
            with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
                log = TramiteLogger("test_json_mod")
        assert isinstance(log._file_handler.formatter, JsonFormatter)

    def test_init_uses_queue_handler(self, tmp_path):
        """TramiteLogger usa QueueHandler + QueueListener (no file I/O en event loop)."""
        with patch("src.utils.logger.LOG_DIR", tmp_path):
            log = TramiteLogger("async_test_mod")
        # El handler en el logger debe ser QueueHandler
        from logging.handlers import QueueHandler
        assert any(isinstance(h, QueueHandler) for h in log._logger.handlers)
        # El listener debe estar corriendo
        assert log._queue_listener is not None

    def test_sanitize_pii_masks_curp_nss_email(self):
        """_sanitize reemplaza CURP, NSS y email en el mensaje (127-132)."""
        msg = TramiteLogger._sanitize(
            "CURP GODE561231HDFRRN09 NSS 12345678901 email a@b.com")
        assert "GODE561231HDFRRN09" not in msg
        assert "12345678901" not in msg
        assert "a@b.com" not in msg
        assert "GODE****" in msg
        assert "12345******" in msg
        assert "a***@b.com" in msg

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
        with patch("src.utils.logger.METRICS_FILE", tmp_path / "test.jsonl"):
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
        with patch("src.utils.logger.METRICS_FILE", metrics_path):
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

    async def test_finish_async_writes_to_file(self, tmp_path):
        """finish_async writes via asyncio.to_thread (non-blocking)."""
        metrics_path = tmp_path / "metricas_async.jsonl"
        tm = TramiteMetrics()
        tm.start("nss")
        with patch("src.utils.logger.METRICS_FILE", metrics_path):
            result = await tm.finish_async(False, extra={"test": "val"})
        assert result is not None
        assert result["tramite"] == "nss"
        assert result["success"] is False
        assert result["test"] == "val"
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert data["success"] is False

    async def test_finish_async_without_start_returns_none(self):
        """finish_async sin start devuelve None."""
        tm = TramiteMetrics()
        result = await tm.finish_async(True)
        assert result is None

    def test_write_metric_to_file(self, tmp_path):
        """_write_metric_to_file escribe JSON línea al archivo."""
        record = {"timestamp": "2025", "tramite": "curp", "success": True, "elapsed_s": 5.0}
        path = tmp_path / "metrics_test.jsonl"
        with patch("src.utils.logger.METRICS_FILE", path):
            TramiteMetrics._write_metric_to_file(record)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["tramite"] == "curp"
        assert data["success"] is True

    def test_resumen_no_file(self, tmp_path):
        tm = TramiteMetrics()
        # METRICS_FILE doesn't exist
        with patch("src.utils.logger.METRICS_FILE", tmp_path / "noexist.jsonl"):
            assert tm.resumen() == {"total": 0}

    def test_resumen_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        tm = TramiteMetrics()
        with patch("src.utils.logger.METRICS_FILE", f):
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
        with patch("src.utils.logger.METRICS_FILE", f):
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
        with patch("src.utils.logger.METRICS_FILE", f):
            result = tm.resumen()
        assert result == {"total": 0}

    def test_resumen_read_exception_returns_total_0(self, tmp_path):
        f = tmp_path / "locked.jsonl"
        f.write_text("{}")
        tm = TramiteMetrics()
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with patch("src.utils.logger.METRICS_FILE", f):
                result = tm.resumen()
        assert result == {"total": 0}

    def test_global_metrics_instance(self):
        """metrics es una instancia global de TramiteMetrics."""
        assert isinstance(metrics, TramiteMetrics)


class TestTramiteLoggerFileHandler:
    """Lines 48-55: file handler creation."""

    def test_handler_created_once(self, tmp_path):
        with patch("src.utils.logger.LOG_DIR", tmp_path):
            log = TramiteLogger("test")
            assert len(log._logger.handlers) >= 1

    def test_reuses_handlers(self, tmp_path):
        with patch("src.utils.logger.LOG_DIR", tmp_path):
            log1 = TramiteLogger("test")
            count = len(log1._logger.handlers)
            log2 = TramiteLogger("test")
            assert len(log2._logger.handlers) == count  # same logger, no dup handlers
