"""Tests para utils/mail_reader.py — lector IMAP para correo IMSS."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.utils.mail_reader import MailReader


class TestMailReader:
    """Lines 33-42: __init__ con configuración IMAP."""

    def test_init_reads_env_vars(self):
        with patch.dict(os.environ, {
            "IMAP_SERVER": "test.imap.com",
            "IMAP_PORT": "143",
            "IMAP_EMAIL": "test@test.com",
            "IMAP_PASSWORD": "secret",
        }, clear=True):
            mr = MailReader()
        assert mr.server == "test.imap.com"
        assert mr.port == 143
        assert mr.email == "test@test.com"
        assert mr.password == "secret"

    def test_init_defaults(self):
        with patch.dict(os.environ, {
            "IMAP_EMAIL": "test@test.com",
            "IMAP_PASSWORD": "secret",
        }, clear=True):
            mr = MailReader()
        assert mr.server == "imap.gmail.com"
        assert mr.port == 993

    def test_init_raises_without_email(self):
        with patch.dict(os.environ, {}, clear=True):
            from src.exceptions import MailReaderError
            with pytest.raises(MailReaderError, match="IMAP_EMAIL"):
                MailReader()

    def test_init_raises_without_password(self):
        with patch.dict(os.environ, {"IMAP_EMAIL": "test@test.com"}, clear=True):
            from src.exceptions import MailReaderError
            with pytest.raises(MailReaderError, match="IMAP_PASSWORD"):
                MailReader()


class TestMailReaderWaitForEmail:
    """Lines 44-81: wait_for_imss_email."""

    @pytest.fixture
    def mail_reader(self):
        with patch.dict(os.environ, {
            "IMAP_EMAIL": "test@test.com",
            "IMAP_PASSWORD": "secret",
        }, clear=True):
            return MailReader()

    def test_wait_finds_email(self, mail_reader):
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.search.side_effect = [[5], [6], []]  # ALL → 5, UNSEEN → 6, timeout stop
        mock_client.fetch.return_value = {6: {b"RFC822": (
            b"From: noreply@imss.gob.mx\r\n"
            b"Subject: Tu NSS\r\n"
            b"\r\n"
            b"Tu NSS es 12345678901 visita https://example.com/verify"
        )}}

        with patch("src.utils.mail_reader.IMAPClient", return_value=mock_client):
            with patch("time.sleep"):  # speed up
                result = mail_reader.wait_for_imss_email(max_wait_sec=10, interval=1)

        assert result["nss"] == "12345678901"
        assert "noreply@imss.gob.mx" in result["from"]
        assert "Tu NSS" in result["subject"]
        assert result["verification_link"] == "https://example.com/verify"
        mock_client.login.assert_called_once()
        mock_client.select_folder.assert_called_once_with("INBOX")

    def test_wait_raises_timeout(self, mail_reader):
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.search.side_effect = [[1, 2, 3], []]
        mock_client.fetch.return_value = {}

        from src.exceptions import MailReaderError
        with patch("src.utils.mail_reader.IMAPClient", return_value=mock_client):
            with patch("time.sleep"):
                with pytest.raises(MailReaderError, match="No llegó correo"):
                    mail_reader.wait_for_imss_email(max_wait_sec=1, interval=1)

    def test_wait_finds_email_with_link(self, mail_reader):
        """HTML multipart email with verification link."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.search.side_effect = [[1, 2, 3], [4]]
        mock_client.fetch.return_value = {4: {b"RFC822": (
            b"From: serviciosdigitales@imss.gob.mx\r\n"
            b"Subject: Confirmaci\xc3\xb3n\r\n"
            b"Content-Type: multipart/alternative; boundary=boundary\r\n"
            b"\r\n"
            b"--boundary\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"Por favor confirma aqu\xc3\xad: https://imss.gob.mx/confirm?token=abc123\r\n"
            b"--boundary--\r\n"
        )}}

        with patch("src.utils.mail_reader.IMAPClient", return_value=mock_client):
            with patch("time.sleep"):
                result = mail_reader.wait_for_imss_email(max_wait_sec=10, interval=1)

        assert "confirm" in result["verification_link"].lower()
        assert "serviciosdigitales@imss.gob.mx" in result["from"]

    def test_wait_html_fallback_when_no_plain(self, mail_reader):
        """HTML-only email extracts body via regex."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.search.side_effect = [[1], [2]]
        mock_client.fetch.return_value = {2: {b"RFC822": (
            b"From: noreply@imss.gob.mx\r\n"
            b"Subject: NSS\r\n"
            b"Content-Type: multipart/alternative; boundary=boundary\r\n"
            b"\r\n"
            b"--boundary\r\n"
            b"Content-Type: text/html\r\n"
            b"\r\n"
            b"<html><body>Tu NSS es <b>98765432101</b></body></html>\r\n"
            b"--boundary--\r\n"
        )}}

        with patch("src.utils.mail_reader.IMAPClient", return_value=mock_client):
            with patch("time.sleep"):
                result = mail_reader.wait_for_imss_email(max_wait_sec=10, interval=1)

        assert result["nss"] == "98765432101"

    def test_wait_existing_uid_filter(self, mail_reader):
        """Only UIDs > start_uid are processed."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.search.side_effect = [
            [1, 2, 3],        # _get_latest_uid → 3
            [1, 2, 3, 4, 5],  # first search in loop
        ]
        # fetch for uid 5 (max of new_msgs [4, 5])
        mock_client.fetch.return_value = {5: {b"RFC822": (
            b"From: noreply@imss.gob.mx\r\n"
            b"Subject: NSS\r\n"
            b"\r\n"
            b"Tu NSS es 11111111111"
        )}}

        with patch("src.utils.mail_reader.IMAPClient", return_value=mock_client):
            with patch("time.sleep"):
                result = mail_reader.wait_for_imss_email(max_wait_sec=10, interval=1)

        assert result["nss"] == "11111111111"
        # Should have fetched uid 5, not 4
        mock_client.fetch.assert_called_once_with([5], ["RFC822"])


class TestMailReaderNonImssSender:
    """El reader busca correos de imss.gob.mx, otros remitentes se ignoran."""

    def test_parse_message_without_nss(self):
        """_parse_message sin NSS en el body."""
        import email

        from src.utils.mail_reader import MailReader

        msg = email.message_from_string(
            "Subject: Hola\r\n\r\nNo hay numero aqui"
        )
        result = MailReader._parse_message(None, msg)
        assert result["nss"] is None
        assert result["body"] == "No hay numero aqui"
        assert result["all_links"] == []

    def test_parse_message_non_multipart(self):
        """_parse_message con email no multipart."""
        import email

        from src.utils.mail_reader import MailReader

        msg = email.message_from_string(
            "Subject: Test\r\n\r\nTu NSS es 12345678901 correo@test.com"
        )
        result = MailReader._parse_message(None, msg)
        assert result["nss"] == "12345678901"
        assert "correo@test.com" in result["body"]

    def test_parse_message_verification_link(self):
        """_parse_message encuentra link de verificación."""
        import email

        from src.utils.mail_reader import MailReader

        msg = email.message_from_string(
            "Subject: Verifica\r\n\r\nLink: https://imss.gob.mx/verif?id=123"
        )
        result = MailReader._parse_message(None, msg)
        assert "verif" in result["verification_link"].lower()

    def test_parse_message_no_verification_link(self):
        """_parse_message sin link de verificación usa el primer link."""
        import email

        from src.utils.mail_reader import MailReader

        msg = email.message_from_string(
            "Subject: Info\r\n\r\nVisita https://imss.gob.mx para mas info"
        )
        result = MailReader._parse_message(None, msg)
        assert result["verification_link"] == "https://imss.gob.mx"
