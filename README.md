# 📻 HAMNA Desktop

Sistema de Gestión de Audio para Radiodifusión — v1.0.0

## Requisitos

- **Windows 10/11**
- **Python 3.13** — [python.org/downloads](https://www.python.org/downloads/)
- `tkinter` incluido en Python estándar de Windows

---

## Instalación en 5 pasos

```bat
:: 1. Clonar / descomprimir el proyecto
cd C:\hamna_desktop

:: 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate

:: 3. Instalar dependencias
pip install -r requirements.txt

:: 4. (Opcional) Azure TTS
pip install azure-cognitiveservices-speech

:: 5. Ejecutar
python main.py
```

---

## Estructura del proyecto

```
hamna_desktop/
│
├── main.py                       ← Punto de entrada
├── main_window.py                ← Ventana principal + motor de transmisión
├── database.py                   ← Capa SQLite
├── settings.py                   ← Configuración JSON
├── ui_theme.py                   ← Tema oscuro + widgets base
│
├── modules/
│   ├── ptt/
│   │   ├── ptt_serial.py         ← PTT via RTS/DTR (pyserial)
│   │   ├── ptt_ami.py            ← PTT via Asterisk AMI
│   │   ├── ptt_api.py            ← PTT via HTTP REST
│   │   └── ptt_manager.py        ← Fachada unificada PTT
│   ├── tts/
│   │   └── tts_manager.py        ← pyttsx3 + Azure Cognitive Services
│   └── audio/
│       └── audio_player.py       ← Reproducción pygame + fallback
│
├── views/
│   ├── np_bar.py                 ← Barra "AL AIRE" permanente
│   ├── view_eventos.py           ← Vista Eventos + secciones CRUD
│   ├── view_programacion.py      ← Vista Programación + timeline
│   └── view_ajustes.py           ← Vista Ajustes (TTS + PTT + Audio)
│
├── forms/
│   ├── evento_form.py            ← Modal Nuevo/Editar Evento
│   ├── seccion_form.py           ← Modal Sección (TTS / Audio / Sonido)
│   └── prog_form.py              ← Modal Programar Evento
│
├── media/audios/                 ← Archivos de audio generados
├── hamna.db                      ← SQLite (se crea automáticamente)
├── settings.json                 ← Config guardada (se crea al guardar)
├── output_temp.mp3               ← Audio temporal TTS
├── hamna.log                     ← Log de la aplicación
└── requirements.txt
```

---

## Métodos PTT

### Serial RS-232 (RTS / DTR)
Activa el pin **RTS** o **DTR** del puerto serial para PTT.  
No requiere control de radio — solo activación de pin.

```
Ajustes → Control PTT → Serial RS-232
Puerto: COM1 (o el que corresponda)
Baudrate: 9600
Pin: RTS  ← recomendado
```

### AMI (Asterisk Manager Interface)
Envía `Action: Originate` al servidor Asterisk existente.

```
Ajustes → Control PTT → AMI
Host: 127.0.0.1  (tu servidor Asterisk)
Port: 5038
Username / Password: credenciales de manager.conf
Canal: SIP/radio
Contexto: ptt-control
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
Envía peticiones `GET` (o `POST`/`PUT`) al servidor existente.

```
Ajustes → Control PTT → API HTTP
URL Base:    http://192.168.1.37
Ruta ON:     /ptt_on
Ruta OFF:    /ptt_off
```

---

## Motor TTS

### pyttsx3 (offline — sin internet)
Usa las voces del sistema. En Windows instala voces en español desde:  
`Configuración → Hora e idioma → Voz → Agregar voces`

### Azure Cognitive Services (voces neuronales)
1. Crear recurso "Speech" en Azure Portal
2. Copiar la clave y la región
3. `Ajustes → Motor TTS → Azure Cognitive Services`

---

## Tipos de Sección

| Tipo | Descripción | Validación |
|------|-------------|------------|
| **TTS** | Texto → Audio con el motor configurado | — |
| **Audio** | Archivo .mp3 o .wav externo | — |
| **Sonido** | Archivo .mp3 o .wav | Máximo 3 segundos |

Los archivos se guardan en `media/audios/{id}_{nombre}.mp3`

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

- El log completo se guarda en `hamna.log`
- La base de datos se crea automáticamente en el primer inicio
- Los ajustes se guardan en `settings.json`
- PTT Serial: el driver USB-Serial debe estar instalado (ej. CH340, CP2102)
