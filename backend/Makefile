.PHONY: dev migrate downgrade test gen-keys lint

dev:
	docker-compose up -d db redis
	uvicorn app.main:app --reload --port 8000

migrate:
	alembic upgrade head

downgrade:
	alembic downgrade -1

autogenerate:
	alembic revision --autogenerate -m "$(msg)"

test:
	pytest -x -v

gen-keys:
	python -c "\
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; \
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption; \
import os; \
os.makedirs('.keys', exist_ok=True); \
pk = Ed25519PrivateKey.generate(); \
open('.keys/ed25519_private.pem','wb').write(pk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())); \
open('.keys/ed25519_public.pem','wb').write(pk.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)); \
print('Keys written to .keys/')"

lint:
	ruff check app tests
