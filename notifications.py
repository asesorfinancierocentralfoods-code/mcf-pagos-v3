
import datetime

def enviar_notificacion(tipo, uuid, mensaje, destinatario_rfc, canal="App"):
    # Simulado - guarda en BD en implementación real
    print(f"[{canal}] {tipo} para {destinatario_rfc}: {mensaje[:100]}")
    return True

def enviar_whatsapp(telefono, mensaje):
    # Placeholder Twilio
    # from twilio.rest import Client
    print(f"WhatsApp a {telefono}: {mensaje[:80]}")
    return True

def enviar_email(destinatario, asunto, cuerpo, adjunto=None):
    print(f"Email a {destinatario}: {asunto}")
    return True
