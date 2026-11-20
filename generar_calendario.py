"""Genera docs/realmadrid.ics con los partidos del Real Madrid.

Fuente: API interna de ESPN (sin clave). Incluye LaLiga, Champions, Copa,
Supercopa y amistosos. Los nombres en español salen de nombres_es.json; los
equipos nuevos se añaden solos con el nombre de ESPN para traducirlos a mano.
"""

import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "docs" / "realmadrid.ics"
NOMBRES = RAIZ / "nombres_es.json"

EQUIPO_ID = "86"  # Real Madrid en ESPN
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
DURACION = timedelta(hours=2)

COMPETICIONES = {
    "esp.1": "LaLiga",
    "uefa.champions": "Champions League",
    "esp.copa_del_rey": "Copa del Rey",
    "esp.super_cup": "Supercopa de España",
    "club.friendly": "Amistoso",
    "fifa.cwc": "Mundial de Clubes",
    "uefa.super_cup": "Supercopa de Europa",
    "fifa.intercontinental_cup": "Copa Intercontinental",
}

FASES = {
    "League Phase": "Fase liga",
    "Knockout Round Playoffs": "Play-off",
    "Round of 32": "Dieciseisavos",
    "Round of 16": "Octavos",
    "Quarterfinals": "Cuartos",
    "Semifinals": "Semifinal",
    "Final": "Final",
}


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def descargar() -> list[dict]:
    """Partidos jugados y próximos, sin duplicados."""
    partidos = {}
    for extra in ("", "?fixture=true"):
        datos = get(f"{BASE}/all/teams/{EQUIPO_ID}/schedule{extra}")
        for ev in datos.get("events", []):
            partidos[ev["id"]] = ev
    return list(partidos.values())


def goles(ev: dict) -> list[str]:
    """Goleadores con minuto, desde el resumen del partido."""
    liga = ev["league"]["slug"]
    resumen = get(f"{BASE}/{liga}/summary?event={ev['id']}")
    detalles = resumen["header"]["competitions"][0].get("details", [])
    lineas = []
    for d in detalles:
        if not d.get("scoringPlay"):
            continue
        minuto = d.get("clock", {}).get("displayValue", "")
        jugador = (d.get("participants") or [{}])[0].get("athlete", {}).get("displayName", "?")
        equipo = d.get("team", {}).get("abbreviation", "")
        nota = " (p.)" if d.get("penaltyKick") else " (p.p.)" if d.get("ownGoal") else ""
        lineas.append(f"⚽ {minuto} {jugador}{nota} ({equipo})")
    return lineas


class Nombres:
    def __init__(self) -> None:
        self.tabla = json.loads(NOMBRES.read_text(encoding="utf-8"))
        self.cambiado = False

    def de(self, equipo: dict) -> tuple[str, str]:
        clave = str(equipo["id"])
        if clave not in self.tabla:  # equipo nuevo: lo apunto con el nombre de ESPN
            self.tabla[clave] = {
                "espn": equipo.get("displayName", ""),
                "nombre": equipo.get("displayName", ""),
                "abr": equipo.get("abbreviation", ""),
            }
            self.cambiado = True
        fila = self.tabla[clave]
        return fila["nombre"], fila["abr"]

    def guardar(self) -> None:
        if self.cambiado:
            NOMBRES.write_text(
                json.dumps(self.tabla, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )


def escapar(texto: str) -> str:
    return (
        texto.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def plegar(linea: str) -> str:
    """Corta líneas a 75 bytes como exige el estándar iCalendar."""
    if len(linea.encode("utf-8")) <= 75:
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


def tanteo(equipo: dict) -> str:
    score = equipo.get("score", "?")
    return score.get("displayValue", "?") if isinstance(score, dict) else str(score)


def competicion(ev: dict) -> str:
    liga = ev["league"]
    texto = COMPETICIONES.get(liga.get("slug"), liga.get("name", ""))
    fase = FASES.get(ev.get("seasonType", {}).get("name", ""))
    return f"{texto} · {fase}" if fase else texto


def evento(ev: dict, nombres: Nombres) -> list[str]:
    comp = ev["competitions"][0]
    equipos = {c["homeAway"]: c for c in comp["competitors"]}
    local, visitante = equipos["home"], equipos["away"]
    en_casa = local["team"]["id"] == EQUIPO_ID and not comp.get("neutralSite")
    rival = visitante if local["team"]["id"] == EQUIPO_ID else local
    nombre_rival, abr_rival = nombres.de(rival["team"])

    estado = comp["status"]["type"]
    terminado = estado.get("completed") and estado.get("name") not in {
        "STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_ABANDONED"
    }
    con_hora = ev.get("timeValid", comp.get("timeValid", True))
    inicio = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))

    titulo = f"{'🏟️' if en_casa else '✈️'} {abr_rival} - {nombre_rival}"

    descripcion = [competicion(ev)]
    if not con_hora and not terminado:
        descripcion.append("Hora por confirmar")
    if estado.get("name") == "STATUS_POSTPONED":
        descripcion.append("Aplazado")
    if terminado:
        nl, _ = nombres.de(local["team"])
        nv, _ = nombres.de(visitante["team"])
        marcador = f"Resultado: {nl} {tanteo(local)}-{tanteo(visitante)} {nv}"
        if local.get("shootoutScore") is not None:
            marcador += f" (penaltis {local['shootoutScore']}-{visitante['shootoutScore']})"
        descripcion.append(marcador)
        try:
            descripcion += goles(ev)
        except Exception as error:  # si falla el resumen, el calendario sigue
            print(f"Sin goleadores para {ev['id']}: {error}")

    venue = comp.get("venue", {})
    lugar = venue.get("fullName", "")
    ciudad = (venue.get("address") or {}).get("city")
    if lugar and ciudad:
        lugar += f", {ciudad}"

    sello = f"{inicio:%Y%m%dT%H%M%SZ}"
    lineas = [
        "BEGIN:VEVENT",
        f"UID:espn-{ev['id']}@calendario-rm",
        f"DTSTAMP:{sello}",
        f"SUMMARY:{escapar(titulo)}",
        f"DESCRIPTION:{escapar(chr(10).join(descripcion))}",
    ]
    if con_hora:
        lineas += [
            f"DTSTART:{inicio:%Y%m%dT%H%M%SZ}",
            f"DTEND:{inicio + DURACION:%Y%m%dT%H%M%SZ}",
        ]
    else:
        dia = inicio.date()
        lineas += [
            f"DTSTART;VALUE=DATE:{dia:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dia + timedelta(days=1):%Y%m%d}",
            "TRANSP:TRANSPARENT",
        ]
    if lugar:
        lineas.append(f"LOCATION:{escapar(lugar)}")
    if estado.get("name") in {"STATUS_POSTPONED", "STATUS_CANCELED"}:
        lineas.append("STATUS:CANCELLED")
    lineas.append("END:VEVENT")
    return lineas


def generar(partidos: list[dict], nombres: Nombres) -> str:
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
    for ev in sorted(partidos, key=lambda e: (e["date"], e["id"])):
        lineas += evento(ev, nombres)
    lineas.append("END:VCALENDAR")
    return "\r\n".join(plegar(l) for l in lineas) + "\r\n"


def main() -> None:
    partidos = descargar()
    if not partidos:
        raise SystemExit("ESPN no ha devuelto partidos; no toco el calendario")
    nombres = Nombres()
    texto = generar(partidos, nombres)
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_bytes(texto.encode("utf-8"))
    nombres.guardar()
    print(f"{len(partidos)} partidos escritos en {SALIDA}")


if __name__ == "__main__":
    main()
