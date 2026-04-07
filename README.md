# ⚽ Barça Calendar Bot

Un bot automatizado en Python que descarga el calendario oficial de partidos del FC Barcelona y lo sincroniza con tu Google Calendar. Además, se ejecuta diariamente mediante GitHub Actions, manteniendo un registro de actividad y sumando contribuciones ("commits verdes") en tu perfil de GitHub.

## 🌟 Características

- **Sincronización Automática:** Descarga el archivo `.ics` del FC Barcelona y añade/actualiza los eventos en Google Calendar de forma fluida.
- **Predicción de Victoria Actualizada:** Consulta las probabilidades de victoria del Barça para cada partido futuro utilizando el sistema [ClubElo](http://clubelo.com). La lógica ha sido optimizada para actualizar automáticamente la descripción de los eventos existentes en tu calendario.
- **Calendario Siempre Limpio:** El bot implementa una función de filtrado y limpieza automática:
  - **Solo Futuro:** Solo se sincronizan los partidos que aún no han comenzado.
  - **Auto-Limpieza:** Se eliminan automáticamente del calendario los partidos ya finalizados, asegurando una vista despejada y centrada en los próximos encuentros.
- **Automatización Constante:** Utiliza GitHub Actions para ejecutarse 3 veces al día (Mañana, Mediodía y Tarde/Noche) sin intervención manual.
- **Contribuciones en GitHub:** Genera un commit automático en el archivo `log_partidos.md` tras cada ejecución exitosa, manteniendo activa tu gráfica de contribuciones.
- **Fácil Despliegue:** Preparado para funcionar directamente en GitHub Actions usando Secrets.
- **Arquitectura Modular:** Código organizado en módulos separados para mantenibilidad y pruebas.

## 🚀 Requisitos

- Python 3.12 o superior (para ejecución local).
- Una cuenta de Google Cloud Platform (GCP) con la API de Google Calendar habilitada.
- Credenciales OAuth 2.0 de Google (`credentials.json`).

## ⚙️ Configuración y Uso Local

1. **Clonar el repositorio y preparar el entorno:**
   ```bash
   git clone <tu-repositorio>
   cd barca-calendar-bot
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   pip install -e .  # Instala el paquete en modo editable
   ```

2. **Obtener las credenciales de Google API:**
   - Ve a la [Consola de Google Cloud](https://console.cloud.google.com/).
   - Crea un nuevo proyecto y habilita la **Google Calendar API**.
   - Configura la Pantalla de Consentimiento de OAuth (añade tu correo como usuario de prueba).
   - Crea credenciales de tipo **ID de cliente de OAuth** (Aplicación de escritorio).
   - Descarga el archivo JSON de credenciales y guárdalo en la raíz del proyecto con el nombre `credentials.json`.

3. **Generar el Token de Acceso:**
   Ejecuta el script para generar el token inicial. Se abrirá una ventana en tu navegador para que autorices a la aplicación:
   ```bash
   python generar_token.py
   ```
   Esto creará un archivo `token.json` que contiene tu token de acceso y de refresco.

4. **Ejecutar el Bot:**
   ```bash
   python bot_barca.py
   ```
   El script descargará el calendario, sincronizará los eventos con tu Google Calendar y añadirá una línea al archivo `log_partidos.md`.

## 🧪 Ejecutar Tests

El proyecto incluye una suite de pruebas para verificar la funcionalidad:

```bash
# Ejecutar todos los tests
pytest

# Ejecutar tests específicos
pytest tests/calendar_cleaner/
pytest tests/win_probability_fix/
```

## ☁️ Configuración en GitHub Actions

Para que el bot se ejecute automáticamente todos los días en la nube:

1. Asegúrate de haber generado el archivo `token.json` localmente (ver paso anterior).
2. Abre el archivo `token.json` y copia todo su contenido.
3. Ve a tu repositorio en GitHub > **Settings** > **Secrets and variables** > **Actions**.
4. Crea un nuevo secreto llamado `GOOGLE_TOKEN_JSON` y pega el contenido de `token.json` como valor.
5. ¡Listo! El bot se ejecutará automáticamente según el cronograma definido en `.github/workflows/run_bot.yml`.

**Nota sobre compatibilidad:** El workflow está configurado para usar Node.js 24 (mediante la variable de entorno `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`) y la acción `actions/setup-python@v5` para evitar advertencias de deprecación de Node.js 20. Esto asegura que el bot seguirá funcionando después de que Node.js 20 sea eliminado de los runners de GitHub Actions en septiembre de 2026.

## 📁 Estructura del Proyecto

```
├── bot_barca.py              # Script principal
├── generar_token.py          # Autenticación OAuth inicial
├── pyproject.toml            # Configuración del paquete Python
├── requirements.txt          # Dependencias (legacy)
├── README.md                 # Este archivo
├── 00_REQUIREMENTS.md        # Requisitos detallados del proyecto
├── AUDIT_REPORT.md           # Auditoría de código y mejoras
├── PLAN.md                   # Plan de desarrollo
├── log_partidos.md           # Registro automático de ejecuciones
├── .github/workflows/
│   └── run_bot.yml           # Workflow de GitHub Actions
├── src/
│   ├── calendar_cleaner/     # Módulo de limpieza de calendario
│   │   ├── __init__.py
│   │   ├── cleaner.py
│   │   └── models.py
│   ├── win_probability_fix/  # Módulo de probabilidades ClubElo
│   │   ├── __init__.py
│   │   ├── clubelo_client.py
│   │   └── models.py
│   ├── shared/               # Utilidades compartidas
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging_config.py
│   └── __init__.py
└── tests/                    # Suite de pruebas
    ├── calendar_cleaner/
    │   └── test_cleaner.py
    ├── win_probability_fix/
    │   └── test_probability.py
    └── __init__.py
```

## 📦 Gestión de Dependencias

El proyecto utiliza `pyproject.toml` para la gestión moderna de paquetes Python. Las dependencias principales incluyen:

- `requests` y `httpx` para peticiones HTTP
- `icalendar` para procesar calendarios ICS
- `google-api-python-client` para la API de Google Calendar
- `beautifulsoup4` y `lxml` para parsing HTML
- `pydantic` para validación de datos
- `pytest` para testing

## 📝 Notas Adicionales

- El bot utiliza el `iCalUID` de los eventos para evitar duplicados y permitir actualizaciones de datos (como el porcentaje de victoria) en eventos ya creados.
- La limpieza automática elimina eventos cuya hora de finalización sea anterior a la hora actual de ejecución del bot.
- El sistema de probabilidades de ClubElo se cachea para reducir peticiones HTTP y mejorar el rendimiento.
- El código ha sido refactorizado para seguir principios de diseño SOLID y facilitar el mantenimiento.

## 🔄 Historial de Cambios

- **v3.0.0**: Refactorización completa con arquitectura modular, tests y gestión moderna de paquetes.
- **v2.0.0**: Añadida funcionalidad de limpieza automática y probabilidades de victoria.
- **v1.0.0**: Sincronización básica del calendario.

---

*Força Barça! 🔴🔵*
