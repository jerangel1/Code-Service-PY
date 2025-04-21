# Code Service PY

[![Licencia MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-v3.8-blue)](https://docs.docker.com/compose/)

**Code Service PY** es un proyecto gratuito diseñado para extraer códigos de suscripciones y enviarlos a través de una API. Este sistema facilita la autorización de códigos para diversas pasarelas, incluyendo Netflix, Disney+, HBO y otros servicios similares.

## 🚀 Funcionalidades Principales

* **Extracción de códigos de suscripción:** Soporte para múltiples servicios.
* **Envío mediante API:** Integración sencilla con otros sistemas.
* **Gestión de autorizaciones:** Específicamente diseñado para servicios de streaming como Netflix, Disney+, HBO, entre otros.
* **Soporte Multi-Plataforma:** Adaptabilidad para futuras pasarelas de suscripción.

## 📂 Estructura del Proyecto

## 🛠 Tecnologías Utilizadas

* **Python:** Desarrollo principal y lógica del negocio.
* **Shell:** Scripts para tareas de soporte y automatización.

## 📖 Instalación y Uso

Sigue estos pasos para configurar y ejecutar Code Service PY:

1.  **Clonar el repositorio:**

    ```bash
    git clone [https://github.com/jerangel1/Code-Service-PY.git](https://github.com/jerangel1/Code-Service-PY.git)
    cd Code-Service-PY
    ```

2.  **Instalar dependencias:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Configurar variables de entorno:**

    Crea un archivo `.env` en la raíz del proyecto con las siguientes variables. **Asegúrate de configurar también tu cuenta de Gmail y generar una contraseña de aplicación (ver instrucciones más abajo).**

    ```env
    ALLOWED_ORIGINS=* # Define los orígenes permitidos para CORS (ej: http://localhost:3000, [https://tu-dominio.com](https://tu-dominio.com))
    API_PORT=8000      # Puerto en el que se ejecutará la API
    GMAIL_APP_PASSWORD=tu_contraseña_de_aplicación_gmail
    POSTGRES_DATABASE=nombre_de_la_base_de_datos
    POSTGRES_HOST=servidor_de_postgres (ej: localhost)
    POSTGRES_PASSWORD=contraseña_de_postgres
    POSTGRES_PRISMA_URL="postgresql://user:password@host:port/database?schema=public" # URL de conexión para Prisma (si se usa)
    POSTGRES_URL="postgresql://user:password@host:port/database"                      # URL de conexión estándar de PostgreSQL
    POSTGRES_URL_NO_SSL="postgresql://user:password@host:port/database?sslmode=disable" # URL de conexión PostgreSQL sin SSL
    POSTGRES_URL_NON_POOLING="postgresql://user:password@host:port/database?pool=false" # URL de conexión PostgreSQL sin pooling
    POSTGRES_USER=usuario_de_postgres
    WORKERS=4          # Número de workers para la aplicación (si aplica)
    ```

    **Configuración de Gmail para IMAP y Contraseña de Aplicaciones:**

    Para que el servicio pueda acceder a tu cuenta de Gmail para verificar códigos (si es una funcionalidad del proyecto), necesitas habilitar IMAP y generar una contraseña de aplicación:

    * **Habilitar IMAP en Gmail:**
        1.  Ve a la configuración de Gmail en tu navegador.
        2.  Haz clic en la pestaña "Ver toda la configuración".
        3.  Selecciona la pestaña "Reenvío y correo POP/IMAP".
        4.  Asegúrate de que la opción "Habilitar IMAP" esté seleccionada.
        5.  Haz clic en "Guardar cambios".

    * **Generar una Contraseña de Aplicación:**
        1.  Ve a tu [Cuenta de Google](https://myaccount.google.com/).
        2.  En el menú de la izquierda, selecciona "Seguridad".
        3.  En "Cómo acceder a Google", busca "Contraseña de aplicaciones" y haz clic en ella. **Es posible que necesites tener activada la verificación en dos pasos para ver esta opción.**
        4.  En la lista desplegable "Seleccionar aplicación", elige "Otro" y escribe un nombre para tu aplicación (ej: CodeServicePY).
        5.  Haz clic en "Generar".
        6.  Google te proporcionará una contraseña de 16 dígitos. **Copia esta contraseña y úsala como valor para la variable `GMAIL_APP_PASSWORD` en tu archivo `.env`.**
        7.  Haz clic en "Listo".

4.  **Ejecutar el proyecto:**

    ```bash
    python main.py
    ```

5.  **Ejecutar pruebas:**

    ```bash
    pytest
    ```

## 🌐 API Endpoints

La API proporciona los siguientes endpoints para interactuar con el servicio:

| Método | Endpoint            | Descripción                                  |
| :----- | :------------------ | :------------------------------------------- |
| `POST` | `/api/obtener-codigo` | Obtiene un código de suscripción.            |
| `POST` | `/api/autorizar`     | Autoriza un código en una pasarela.          |
| `GET`  | `/api/status`        | Verifica el estado general del servicio.     |

## 🤝 Contribuciones

¡Agradecemos tu interés en contribuir a Code Service PY! Para colaborar, sigue estos pasos:

1.  Realiza un **fork** del repositorio en GitHub.
2.  Crea una **rama** para tu nueva funcionalidad o corrección (ejemplo: `git checkout -b feature/nueva-funcionalidad`).
3.  Realiza tus cambios y haz **commit** de ellos (ejemplo: `git commit -m 'Añade soporte para la pasarela XYZ'`).
4.  Sube tus cambios a tu fork (`git push origin feature/nueva-funcionalidad`).
5.  Crea un **pull request** detallado explicando tu contribución para que podamos revisarla.

## 📋 Roadmap

Este es un vistazo a las futuras mejoras y funcionalidades en las que estamos trabajando:

* Soporte para nuevas pasarelas de suscripción.
* Implementación de un dashboard para el monitoreo de códigos generados.
* Optimización del rendimiento en el proceso de extracción de códigos.

## 📄 Licencia

Este proyecto está licenciado bajo la [MIT License](https://opensource.org/licenses/MIT). Consulta el archivo `LICENSE` para obtener más detalles sobre los términos de la licencia.
