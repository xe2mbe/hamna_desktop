# HAMNA Desktop

Amateur Radio (HAM) Net Automation (NA) System — v1.1.0

## Requisitos

- **Windows 10/11**
- **Python 3.13** — [python.org/downloads](https://www.python.org/downloads/)
- `tkinter` incluido en Python estándar de Windows

---

## Instalación

```bat
:: 1. Clonar el repositorio
git clone https://github.com/xe2mbe/hamna_desktop.git
cd hamna_desktop

:: 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate

:: 3. Instalar dependencias
pip install -r requirements.txt

:: 4. Configurar ajustes
copy settings.json.example settings.json
:: Editar settings.json con tus valores (clave Azure, puerto serial, etc.)

:: 5. Ejecutar
python main.py
```

---

## Estructura del proyecto

```
hamna_desktop/
│
├── main.py                       <- Punto de entrada
├── main_window.py                <- Ventana principal + motor de transmisión
├── database.py                   <- Capa SQLite
├── settings.py                   <- Configuración JSON
├── ui_theme.py                   <- Tema oscuro/claro + widgets base
├── i18n.py                       <- Internacionalización (español)
│
├── modules/
│   ├── ptt/
│   │   ├── ptt_serial.py         <- PTT via RTS/DTR (pyserial)
│   │   ├── ptt_ami.py            <- PTT via Asterisk AMI
│   │   ├── ptt_api.py            <- PTT via HTTP REST
│   │   └── ptt_manager.py        <- Fachada unificada PTT
│   ├── tts/
│   │   └── tts_manager.py        <- pyttsx3 + Azure TTS REST
│   └── audio/
│       └── audio_player.py       <- Reproducción pygame + fallback MCI
│
├── views/
│   ├── np_bar.py                 <- Barra "AL AIRE" permanente
│   ├── view_secciones.py         <- Vista Secciones (biblioteca)
│   ├── view_eventos.py           <- Vista Eventos + secciones CRUD
│   ├── view_programacion.py      <- Vista Programación + timeline
│   └── view_ajustes.py           <- Vista Ajustes (TTS + PTT + Audio)
│
├── forms/
│   ├── evento_form.py            <- Modal Nuevo/Editar Evento
│   ├── seccion_form.py           <- Modal Sección (TTS / Audio / Sonido)
│   ├── prog_form.py              <- Modal Programar Evento
│   └── audio_player_window.py    <- Ventana de preescucha
│
├── media/audios/                 <- Archivos de audio generados/importados
├── hamna.db                      <- SQLite (se crea automáticamente)
├── settings.json                 <- Config local (NO se sube al repo)
├── settings.json.example         <- Plantilla de configuración
└── requirements.txt
```

---

## Funcionalidades

### Secciones (biblioteca reutilizable)

Unidades de audio independientes del evento:

| Tipo | Descripción |
|------|-------------|
| **TTS** | Texto con variables → Audio sintetizado al momento |
| **Audio** | Archivo .mp3 o .wav externo |
| **Sonido** | Clip corto .mp3/.wav (máx. 3 seg.) |

Las secciones TTS pueden marcarse como **Regenerar antes** (`🔄`): el audio
se sintetiza automáticamente justo antes de reproducirse, reflejando siempre
la hora y fecha actuales.

### Eventos

Agrupan secciones en orden para una transmisión:

- **Número de edición**: campo opcional para numerar ediciones del evento
  (ej. "Boletín Informativo #42"). El asistente calcula el número por
  ocurrencia del día de la semana en el año a partir de una fecha elegida.
- **Contabilizable**: cada sección del evento puede marcarse como contabilizable
  o no. Esto controla qué cuentan `{num_secciones}` y `{dur_contabilizable}`.

### Variables TTS

Disponibles en cualquier texto de sección tipo TTS:

| Variable | Descripción |
|----------|-------------|
| `{fecha}` | Fecha actual (dd/mm/aaaa) |
| `{hora}` | Hora actual (HH:MM) |
| `{dia}` | Día de la semana en español |
| `{pausa_cada}` | Intervalo de pausa configurado |
| `{pausa_duracion}` | Duración de la pausa configurada |
| `{pausa_alerta}` | Tiempo de alerta antes de pausa |
| `{evento}` | Nombre del evento de referencia |
| `{num_secciones}` | Cantidad de secciones contabilizables del evento |
| `{duracion_total}` | Duración total de todas las secciones del evento |
| `{dur_contabilizable}` | Duración de secciones contabilizables del evento |

---

## Motor TTS

### pyttsx3 (offline)
Usa voces SAPI5 del sistema. Para agregar voces en español:
`Configuración → Hora e idioma → Voz → Agregar voces`

### Azure Cognitive Services (voces neuronales)
Integración vía REST API — no requiere SDK adicional.

1. Crear recurso "Speech" en [Azure Portal](https://portal.azure.com)
2. Copiar la clave y la región al `settings.json`
3. `Ajustes → Motor TTS → Azure Cognitive Services`

---

## Control PTT

### Serial RS-232 (RTS / DTR)
Activa el pin RTS o DTR del puerto serial.

```
Ajustes → Control PTT → Serial RS-232
Puerto: COM1   Baudrate: 9600   Pin: RTS
```

El driver USB-Serial debe estar instalado (ej. CH340, CP2102).

### AMI (Asterisk Manager Interface)
Envía `Action: Originate` al servidor Asterisk.

```
Ajustes → Control PTT → AMI
Host: 127.0.0.1  Port: 5038
Usuario/Contraseña: credenciales de manager.conf
Canal: SIP/radio   Contexto: ptt-control
```

**En Asterisk (`extensions.conf`):**
```
[ptt-control]
exten => ptt-on,1,NoOp(PTT ON)
exten => ptt-on,2,UserEvent(PTT,Status: ON)
exten => ptt-on,3,Hangup()

exten => ptt-off,1,NoOp(PTT OFF)
exten => ptt-off,2,UserEvent(PTT,Status: OFF)
exten => ptt-off,3,Hangup()
```

### API HTTP
Envía peticiones GET/POST/PUT a un endpoint externo.

```
Ajustes → Control PTT → API HTTP
URL Base: http://192.168.1.37   Ruta ON: /ptt_on   Ruta OFF: /ptt_off
```

---

## Empaquetado como .exe

```bat
pip install pyinstaller
pyinstaller --onefile --windowed --name "HAMNA Desktop" ^
    --add-data "media;media" main.py
:: El ejecutable queda en dist\HAMNA Desktop.exe
```

---

## Notas

- `settings.json` **no se incluye en el repositorio** — usar `settings.json.example` como plantilla
- La base de datos `hamna.db` se crea automáticamente en el primer inicio
- El log completo se guarda en `hamna.log`
