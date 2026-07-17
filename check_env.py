from app.settings import load_settings

settings = load_settings()

print("EDGEHUB_ENABLED:", settings.edgehub_enabled)
print("EDGEHUB_NODE_ID:", settings.edgehub_node_id)
print("EDGEHUB_DEVICE_ID:", settings.edgehub_device_id)

token = settings.edgehub_sas_token

print("TOKEN STARTS OK:", token.startswith("SharedAccessSignature"))
print("TOKEN HAS sr=:", "sr=" in token)
print("TOKEN HAS sig=:", "sig=" in token)
print("TOKEN HAS se=:", "se=" in token)
print("TOKEN HAS skn=:", "skn=" in token)
print("TOKEN LENGTH:", len(token))

print("TOKEN PREVIEW:", token[:80] + "...")