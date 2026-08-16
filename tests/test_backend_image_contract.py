"""Контракт сборки backend-образа без запуска Docker build."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backend_image_installs_bundled_russian_root_ca():
    """Сертификат должен попадать в системное CA-хранилище образа."""
    dockerfile = (ROOT / 'Dockerfile.backend').read_text(encoding='utf-8')
    certificate = (ROOT / 'certs' / 'russian-trusted-root-ca.pem').read_text(
        encoding='ascii'
    )

    assert 'BEGIN CERTIFICATE' in certificate
    assert (
        'COPY certs/russian-trusted-root-ca.pem '
        '/usr/local/share/ca-certificates/russian-trusted-root-ca.crt'
    ) in dockerfile
    assert 'update-ca-certificates' in dockerfile
