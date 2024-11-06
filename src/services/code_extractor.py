import email
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

class CodeExtractor:
    @staticmethod
    def extract_code_from_email(email_message) -> str:
        """Extrae el código de verificación del mensaje de correo."""
        try:
            # Obtener el cuerpo del mensaje
            body = CodeExtractor._get_email_body(email_message)
            if not body:
                return None

            # Patrones específicos de Netflix
            patterns = [
                r'código de acceso temporal.*?(\d{4,8})',  # Código de acceso temporal
                r'código.*?(\d{4,8})',                     # Código general
                r'code.*?(\d{4,8})',                      # Code en inglés
                r'verification code:?\s*(\d{4,8})',       # Código de verificación
                r'confirm.*?code:?\s*(\d{4,8})',          # Código de confirmación
                r'\b\d{6}\b',                             # Códigos de 6 dígitos (común en Netflix)
            ]

            # Primero buscar en el texto plano
            for pattern in patterns:
                matches = re.findall(pattern, body, re.IGNORECASE)
                if matches:
                    code = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    logger.info(f"✅ Código encontrado: {code}")
                    return code

            # Si no se encuentra, buscar en elementos HTML específicos
            soup = BeautifulSoup(body, 'html.parser')
            
            # Buscar en elementos con clases/IDs comunes de Netflix
            code_elements = soup.find_all(['div', 'span', 'p'], {
                'class': lambda x: x and any(word in str(x).lower() 
                    for word in ['code', 'codigo', 'verification', 'pin'])
            })

            for element in code_elements:
                text = element.get_text()
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if matches:
                        code = matches[0] if isinstance(matches[0], str) else matches[0][0]
                        logger.info(f"✅ Código encontrado en HTML: {code}")
                        return code

            logger.warning("⚠️ No se encontró ningún código")
            return None

        except Exception as e:
            logger.error(f"❌ Error extrayendo código: {str(e)}")
            return None

    @staticmethod
    def _get_email_body(email_message) -> str:
        """Extrae el cuerpo del mensaje de correo."""
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/html":
                        return part.get_payload(decode=True).decode()
                    elif content_type == "text/plain":
                        return part.get_payload(decode=True).decode()
            else:
                return email_message.get_payload(decode=True).decode()
        except Exception as e:
            logger.error(f"❌ Error obteniendo cuerpo del correo: {str(e)}")
            return None