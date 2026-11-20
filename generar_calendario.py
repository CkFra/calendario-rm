"""Genera docs/realmadrid.ics con los partidos del Real Madrid.

Fuente: API de football-data.org (plan gratuito: LaLiga y Champions).
El token se lee de la variable de entorno FOOTBALL_DATA_TOKEN.
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

EQUIPO_ID = 86  # Real Madrid en football-data.org
API = "https://api.football-data.org/v4/teams/{id}/matches?season={season}"
SALIDA = Path(__file__).parent / "docs" / "realmadrid.ics"
DURACION = timedelta(hours=2)

COMPETICIONES = {
    "PD": "LaLiga",
    "CL": "Champions",
    "CDR": "Copa del Rey",
    "SSC": "Supercopa",
    "CWC": "Mundial de Clubes",
}

FASES = {
    "LEAGUE_STAGE": "Fase liga",
    "PLAYOFFS": "Play-off",
    "LAST_16": "Octavos",
    "QUARTER_FINALS": "Cuartos",
    "SEMI_FINALS": "Semifinal",
    "FINAL": "Final",
}

ESTADOS_TERMINADO = {"FINISHED", "AWARDED"}


def temporada_actual(hoy: date) -> int:
    """La temporada empieza en julio: en nov-2026 es la 2026 (2026-27)."""
    return hoy.year if hoy.month >= 7 else hoy.year - 1


def descargar(token: str, season: int) -> list[dict]:
    url = API.format(id=EQUIPO_ID, season=season)
    req = urllib.request.Request(url, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["matches"]


def escapar(texto: str) -> str:
    return (
        texto.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def plegar(linea: str) -> str:
    """Corta líneas a 75 bytes como exige el estándar iCalendar."""
    datos = linea.encode("utf-8")
    if len(datos) <= 75:
        return linea
    trozos, actual = [], b""
    for caracter in linea:
        c = caracter.encode("utf-8")
        limite = 75 if not trozos else 74
        if len(actual) + len(c) > limite:
            trozos.append(actual.decode("utf-8"))
            actual = b""
        actual += c
    trozos.append(actual.decode("utf-8"))
    return "\r\n ".join(trozos)


def nombre(equipo: dict) -> str:
    return equipo.get("shortName") or equipo.get("name") or "Por determinar"


def etiqueta(partido: dict) -> str:
    comp = partido["competition"]
    texto = COMPETICIONES.get(comp.get("code"), comp.get("name", ""))
    fase = partido.get("stage")
    if fase == "REGULAR_SEASON" or (fase == "LEAGUE_STAGE" and partido.get("matchday")):
        if partido.get("matchday"):
            texto += f" J{partido['matchday']}"
    elif fase in FASES:
        texto += f" · {FASES[fase]}"
    return texto


def evento(partido: dict) -> list[str]:
    local, visitante = partido["homeTeam"], partido["awayTeam"]
    inicio = datetime.fromisoformat(partido["utcDate"].replace("Z", "+00:00"))
    actualizado = datetime.fromisoformat(partido["lastUpdated"].replace("Z", "+00:00"))
    sin_hora = partido["status"] == "SCHEDULED"  # fecha fijada, hora sin confirmar
    terminado = partido["status"] in ESTADOS_TERMINADO

    titulo = f"⚽ {nombre(local)} – {nombre(visitante)} · {etiqueta(partido)}"
    if sin_hora:
        titulo += " (hora por confirmar)"

    descripcion = [etiqueta(partido)]
    if terminado:
        marcador = partido["score"]["fullTime"]
        descripcion.append(f"Resultado: {marcador['home']}-{marcador['away']}")
    if partido["status"] == "POSTPONED":
        descripcion.append("Aplazado")

    lugar = partido.get("venue") or (
        "Santiago Bernabéu" if local.get("id") == EQUIPO_ID else ""
    )

    lineas = [
        "BEGIN:VEVENT",
        f"UID:fd-{partido['id']}@calendario-rm",
        f"DTSTAMP:{actualizado:%Y%m%dT%H%M%SZ}",
        f"LAST-MODIFIED:{actualizado:%Y%m%dT%H%M%SZ}",
        f"SUMMARY:{escapar(titulo)}",
        f"DESCRIPTION:{escapar(chr(10).join(descripcion))}",
    ]
    if sin_hora:
        dia = inicio.date()
        lineas += [
            f"DTSTART;VALUE=DATE:{dia:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dia + timedelta(days=1):%Y%m%d}",
            "TRANSP:TRANSPARENT",
        ]
    else:
        lineas += [
            f"DTSTART:{inicio:%Y%m%dT%H%M%SZ}",
            f"DTEND:{inicio + DURACION:%Y%m%dT%H%M%SZ}",
        ]
    if lugar:
        lineas.append(f"LOCATION:{escapar(lugar)}")
    if partido["status"] in {"POSTPONED", "CANCELLED"}:
        lineas.append("STATUS:CANCELLED")
    lineas.append("END:VEVENT")
    return lineas


def generar(partidos: list[dict]) -> str:
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CkFra//calendario-rm//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Real Madrid",
        "X-WR-TIMEZONE:Europe/Madrid",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for partido in sorted(partidos, key=lambda p: (p["utcDate"], p["id"])):
        lineas += evento(partido)
    lineas.append("END:VCALENDAR")
    return "\r\n".join(plegar(l) for l in lineas) + "\r\n"


def main() -> None:
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        sys.exit("Falta la variable FOOTBALL_DATA_TOKEN")
    partidos = descargar(token, temporada_actual(date.today()))
    if not partidos:
        sys.exit("La API no ha devuelto partidos; no toco el calendario")
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_bytes(generar(partidos).encode("utf-8"))
    print(f"{len(partidos)} partidos escritos en {SALIDA}")


if __name__ == "__main__":
    main()
