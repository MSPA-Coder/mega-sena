from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Flask
from openpyxl import Workbook

from app import create_app


def css_source() -> str:
    """Carrega a folha agregadora e todos os modulos CSS da aplicacao."""
    static_dir = Path("app/static")
    files = [static_dir / "style.css", *sorted((static_dir / "css").glob("*.css"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def make_app() -> Flask:
    """Cria a aplicação de teste pela mesma factory usada em produção."""
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": "test",
            "AUTO_INITIALIZE_DATABASE": False,
        }
    )


def csrf_form_data(client, token_path: str, data: dict | None = None) -> dict:
    text = client.get(token_path).get_data(as_text=True)
    marker = 'name="_csrf_token" value="'
    start = text.index(marker) + len(marker)
    end = text.index('"', start)
    payload = dict(data or {})
    payload["_csrf_token"] = text[start:end]
    return payload


def workbook_bytes(rows: list[list[object]], bad_dimension: bool = False) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Concurso",
            "Data do Sorteio",
            "Bola1",
            "Bola2",
            "Bola3",
            "Bola4",
            "Bola5",
            "Bola6",
            "Ganhadores 6 acertos",
            "Ganhadores 5 acertos",
            "Ganhadores 4 acertos",
            "Rateio 6 acertos",
            "Rateio 5 acertos",
            "Rateio 4 acertos",
            "Acumulado 6 acertos",
        ]
    )
    for row in rows:
        sheet.append(row)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    if not bad_dimension:
        return stream

    patched = BytesIO()
    with ZipFile(stream, "r") as source, ZipFile(patched, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                content = content.replace(b'<dimension ref="A1:O3"/>', b'<dimension ref="A1:O1"/>')
            target.writestr(info, content)
    patched.seek(0)
    return patched
