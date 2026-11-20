# Calendario del Real Madrid

Calendario `.ics` con los partidos del Real Madrid (LaLiga, Champions, Copa, Supercopa y amistosos), actualizado solo cada 6 horas con GitHub Actions y publicado con GitHub Pages.

- **Suscribirse:** `https://ckfra.github.io/calendario-rm/realmadrid.ics`
- **Fuente:** API interna de ESPN (sin clave, no oficial).
- **Formato:** título `🏟️ BAR - FC Barcelona` (en casa) o `✈️ ATM - Atlético de Madrid` (fuera o campo neutral); en la info, competición, resultado y goleadores con minuto.
- **Nombres en español:** `nombres_es.json`. Los equipos nuevos se añaden solos con el nombre de ESPN; para traducirlos, editar su `nombre` y `abr`.
- **Lanzarlo a mano:** pestaña *Actions* → *Actualizar calendario* → *Run workflow*.

Los partidos sin hora confirmada salen como evento de día completo con «Hora por confirmar» en la info.
